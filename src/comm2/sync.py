"""Sincronizacion: trama, frecuencia, temporizacion y fase.

Cadena de adquisicion implementada (orden justificado en docs/arquitectura.md):

  1. Schmidl & Cox sobre el preambulo de dos mitades identicas
     -> deteccion de rafaga + estimacion gruesa de CFO.
     Es no coherente y funciona *antes* de recuperar temporizacion, por eso
     va primero.
  2. Correccion del CFO grueso.
  3. Recuperacion de temporizacion por lazo de Gardner (TED no asistido por
     decision, con interpolador de Lagrange cubico y filtro de lazo PI).
     Gardner se elige frente a Mueller & Muller porque no es dirigido por
     decision y tolera CFO residual, a costa de necesitar 2 muestras/simbolo.
  4. Sincronizacion fina de trama por correlacion con el preambulo conocido.
  5. Estimacion fina de CFO asistida por datos sobre la secuencia de
     entrenamiento (pendiente de fase).
  6. PLL dirigido por decision tras el ecualizador para el jitter de fase.

Referencias:
  T. M. Schmidl y D. C. Cox, "Robust frequency and timing synchronization for
    OFDM", IEEE Trans. Commun., 45(12), 1997.
  F. M. Gardner, "A BPSK/QPSK timing-error detector for sampled receivers",
    IEEE Trans. Commun., 34(5), pp. 423-429, 1986.
  K. Mueller y M. Muller, "Timing recovery in digital synchronous data
    receivers", IEEE Trans. Commun., 24(5), pp. 516-531, 1976.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .modulation import Modulation


# ---------------------------------------------------------------------------
# 1) Deteccion de rafaga y CFO grueso (Schmidl & Cox)
# ---------------------------------------------------------------------------


@dataclass
class SCResult:
    start: int              # indice de inicio del preambulo (muestras)
    metric: np.ndarray      # metrica M(d) completa
    cfo_hz: float           # estimacion gruesa de offset de frecuencia
    peak_value: float


def schmidl_cox(r: np.ndarray, half_len_samples: int, fs: float) -> SCResult:
    """Sincronizacion de trama y CFO con preambulo de dos mitades identicas.

        P(d) = sum_{m} r*[d+m] r[d+m+L]
        Ra(d) = sum_{m} |r[d+m]|^2,   Rb(d) = sum_{m} |r[d+m+L]|^2
        M(d) = |P(d)|^2 / (Ra(d) Rb(d))

    La formulacion original de Schmidl-Cox normaliza solo con Rb (la energia de
    la segunda ventana), lo que en recepcion continua de OFDM es equivalente.
    En recepcion por rafagas NO lo es: en el flanco final de la rafaga la
    primera ventana aun contiene senal mientras la segunda solo tiene ruido, de
    modo que M(d) puede superar la unidad y generar un maximo espurio a miles de
    muestras del preambulo. Normalizando con sqrt(Ra*Rb) la metrica queda
    acotada por 1 (desigualdad de Cauchy-Schwarz) y el maximo espurio desaparece.

    La fase de P en el pico da el CFO:  f = arg{P} * fs / (2 pi L).
    Rango de adquisicion: |f| < fs / (2 L).
    """
    L = int(half_len_samples)
    n = r.size - 2 * L
    if n <= 0:
        raise ValueError("senal mas corta que el preambulo")

    # Correlacion e integracion mediante suma acumulada (O(N))
    prod = np.conj(r[:-L]) * r[L:]
    energy = np.abs(r) ** 2
    cp = np.concatenate([[0], np.cumsum(prod)])
    ce = np.concatenate([[0], np.cumsum(energy)])
    P = cp[L:L + n] - cp[:n]
    Ra = ce[L:L + n] - ce[:n]                  # energia de la primera ventana
    Rb = ce[2 * L:2 * L + n] - ce[L:L + n]     # energia de la segunda ventana
    with np.errstate(divide="ignore", invalid="ignore"):
        M = np.abs(P) ** 2 / (Ra * Rb)
    M[~np.isfinite(M)] = 0.0

    # A Eb/N0 bajo, M(d) es muy ruidosa y su argmax puede caer sobre un pico
    # espurio. Se promedia con una ventana corta (L/8) antes de buscar el
    # maximo: reduce la varianza sin ensanchar apreciablemente el vertice.
    win = max(3, L // 8)
    Ms = np.convolve(M, np.ones(win) / win, mode="same")

    # Centro de la meseta: intervalo CONTIGUO alrededor del pico sobre el 90 %
    # del maximo (tomar todas las muestras sobre el umbral, aunque esten lejos,
    # sesgaria la estimacion decenas de simbolos).
    peak = int(np.argmax(Ms))
    thr = 0.9 * Ms[peak]
    lo = hi = peak
    while lo > 0 and Ms[lo - 1] >= thr:
        lo -= 1
    while hi < Ms.size - 1 and Ms[hi + 1] >= thr:
        hi += 1
    start = (lo + hi) // 2

    cfo = float(np.angle(P[start]) * fs / (2 * np.pi * L))
    return SCResult(start=start, metric=M, cfo_hz=cfo, peak_value=float(M[peak]))


def max_cfo_acquisition(half_len_samples: int, fs: float) -> float:
    """Rango de adquisicion sin ambiguedad del estimador Schmidl-Cox [Hz]."""
    return fs / (2.0 * half_len_samples)


# ---------------------------------------------------------------------------
# 2) Recuperacion de temporizacion: lazo de Gardner
# ---------------------------------------------------------------------------


def _cubic_lagrange(x: np.ndarray, m: int, mu: float) -> complex:
    """Interpolacion de Lagrange cubica entre x[m] y x[m+1]."""
    c_m1 = -mu * (mu - 1) * (mu - 2) / 6.0
    c_0 = (mu + 1) * (mu - 1) * (mu - 2) / 2.0
    c_1 = -(mu + 1) * mu * (mu - 2) / 2.0
    c_2 = (mu + 1) * mu * (mu - 1) / 6.0
    return (c_m1 * x[m - 1] + c_0 * x[m] + c_1 * x[m + 1] + c_2 * x[m + 2])


def loop_gains(bn_t: float, zeta: float = 0.707, k_det: float = 2.0,
               k_nco: float = 1.0, n_per_update: int = 1) -> tuple[float, float]:
    """Ganancias proporcional/integral de un lazo de 2do orden.

    bn_t : ancho de banda de ruido del lazo normalizado (Bn*T)
    zeta : amortiguamiento
    k_det: ganancia del detector, k_nco: ganancia del NCO
    """
    theta = 2 * np.pi * bn_t / (n_per_update * (zeta + 1.0 / (4 * zeta)))
    d = 1 + 2 * zeta * theta + theta ** 2
    kp = (4 * zeta * theta / d) / (k_det * k_nco)
    ki = (4 * theta ** 2 / d) / (k_det * k_nco)
    return kp, ki


@dataclass
class TimingResult:
    symbols: np.ndarray      # una muestra por simbolo
    mu_track: np.ndarray     # evolucion del error fraccional (para graficar)
    err_track: np.ndarray    # senal de error del TED
    sample_index: np.ndarray # posicion (fraccional) de cada simbolo en la entrada


def gardner_timing_recovery(x: np.ndarray, sps: int, loop_bw: float = 0.01,
                            zeta: float = 0.707, start: float = 0.0,
                            k_det: float = 2.0) -> TimingResult:
    """Lazo de recuperacion de temporizacion de Gardner.

    Trabaja con 2 interpolaciones por simbolo (instante de simbolo y punto
    medio). El error del TED es

        e[k] = Re{ y*_mid[k] ( y[k] - y[k-1] ) }

    que es cero cuando se muestrea en el maximo del pulso y no requiere
    conocer los simbolos (no dirigido por decision).
    """
    half = sps / 2.0
    kp, ki = loop_gains(loop_bw, zeta, k_det=k_det, n_per_update=sps)

    pos = float(start) + 2.0                 # margen para el interpolador cubico
    integ = 0.0
    v = 0.0
    syms, mus, errs, idxs = [], [], [], []
    prev_sym = None
    mid = None
    is_symbol = True                          # el primer strobe es de simbolo

    n_max = x.size - 3
    while pos < n_max:
        m = int(np.floor(pos))
        mu = pos - m
        y = _cubic_lagrange(x, m, mu)

        if is_symbol:
            if prev_sym is not None and mid is not None:
                e = (mid.real * (y.real - prev_sym.real)
                     + mid.imag * (y.imag - prev_sym.imag))
                integ += ki * e
                v = kp * e + integ
                errs.append(e)
            else:
                errs.append(0.0)
            syms.append(y)
            mus.append(mu)
            idxs.append(pos)
            prev_sym = y
        else:
            mid = y

        is_symbol = not is_symbol
        # La correccion del NCO se limita a +-50 % del paso nominal. Sin este
        # limite, un transitorio grande (offset de frecuencia elevado, SNR muy
        # baja) puede hacer que v supere la unidad, el paso se vuelva nulo o
        # negativo y el lazo deje de avanzar: el bucle no termina nunca.
        v = min(max(v, -0.5), 0.5)
        pos += half - v * half                # el NCO corrige medio simbolo

    return TimingResult(symbols=np.asarray(syms), mu_track=np.asarray(mus),
                        err_track=np.asarray(errs), sample_index=np.asarray(idxs))


def fixed_downsample(x: np.ndarray, sps: int, offset: int = 0) -> np.ndarray:
    """Diezmado fijo (sin lazo), usado como referencia/ablacion."""
    return x[offset::sps]


# ---------------------------------------------------------------------------
# 3) Sincronizacion fina de trama a nivel de simbolo
# ---------------------------------------------------------------------------


def fine_frame_sync(sym: np.ndarray, template: np.ndarray,
                    search: int | None = None) -> tuple[int, float, np.ndarray]:
    """Correlacion cruzada normalizada con una plantilla conocida.

    Importante: el preambulo [ZC ZC] tiene dos mitades identicas, por lo que su
    autocorrelacion aperiodica presenta un lobulo lateral de altura 0.5 en el
    desplazamiento +-L. Con multitrayectoria el pico principal puede caer por
    debajo de ese lobulo y el sincronizador engancha 64 simbolos tarde. Por eso
    `link.run_link` pasa como plantilla el preambulo *extendido* con una parte
    de la secuencia de entrenamiento (aperiodica), que elimina la ambiguedad.

    Devuelve (indice de inicio, correlacion normalizada, curva de correlacion).
    """
    L = template.size
    n = sym.size - L
    if n <= 0:
        return 0, 0.0, np.zeros(1)
    limit = int(n if search is None else min(n, search))

    # correlacion deslizante vectorizada
    idx = np.arange(limit)[:, None] + np.arange(L)[None, :]
    seg = sym[idx]                                  # (limit, L)
    num = np.abs(seg @ np.conj(template))
    den = np.linalg.norm(seg, axis=1) * np.linalg.norm(template)
    corr = num / (den + 1e-12)
    d = int(np.argmax(corr))
    return d, float(corr[d]), corr


# ---------------------------------------------------------------------------
# 4) CFO fino asistido por datos
# ---------------------------------------------------------------------------


def fine_cfo_data_aided(rx_sym: np.ndarray, ref_sym: np.ndarray, rs: float,
                        block: int = 16) -> float:
    """Estimacion fina de CFO sobre simbolos conocidos (Luise & Reggiannini).

    Se elimina la modulacion, z[i] = r[i] a*[i], y se promedian bloques de
    `block` simbolos. Un estimador de un solo retardo,
    f = arg{sum z[i+1] z*[i]} Rs / (2 pi B), tiene un factor de escala enorme
    (Rs / 2 pi B ~ 1.2 kHz/rad) y con ISI multitrayectoria los terminos cruzados
    lo hacen inservible. El estimador de Luise-Reggiannini promedia N
    autocorrelaciones de retardo creciente y reduce la varianza en un orden de
    magnitud:

        R(m) = 1/(K-m) sum_i z[i+m] z*[i]
        f = arg{ sum_{m=1..N} R(m) } * Rs / (pi (N+1) B)

    Referencia: M. Luise y R. Reggiannini, "Carrier frequency recovery in
    all-digital modems for burst-mode transmissions", IEEE Trans. Commun.,
    43(2/3/4), pp. 1169-1178, 1995.
    """
    z = rx_sym * np.conj(ref_sym)
    nb = z.size // block
    if nb < 4:
        return 0.0
    zb = z[:nb * block].reshape(nb, block).sum(axis=1)
    n_lags = max(1, nb // 2)
    acc = 0.0 + 0j
    for m in range(1, n_lags + 1):
        acc += np.sum(zb[m:] * np.conj(zb[:-m])) / (nb - m)
    return float(np.angle(acc) * rs / (np.pi * (n_lags + 1) * block))


def fine_cfo_ml(rx_sym: np.ndarray, ref_sym: np.ndarray, rs: float,
                f_max: float | None = None, n_grid: int = 1201) -> float:
    """Estimador ML (periodograma) de CFO asistido por datos.

    Tras eliminar la modulacion, z[i] = r[i] a*[i], el offset de frecuencia es
    un tono complejo inmerso en ruido + terminos cruzados de ISI. El estimador
    de maxima verosimilitud es el maximo del periodograma

        J(f) = | sum_i z[i] e^{-j 2 pi f i / Rs} |

    Se evalua en una rejilla fina alrededor de cero (el CFO grueso ya fue
    corregido) y se refina con interpolacion parabolica sobre el maximo. A
    diferencia de los estimadores de un solo retardo, usa toda la longitud de
    observacion, por lo que su varianza alcanza la cota de Cramer-Rao.
    """
    n = min(rx_sym.size, ref_sym.size)
    if n < 32:
        return 0.0
    z = rx_sym[:n] * np.conj(ref_sym[:n])
    f_max = f_max if f_max is not None else 2.0 * rs / n     # +-2 celdas DFT
    f = np.linspace(-f_max, f_max, n_grid)
    i = np.arange(n)
    J = np.abs(np.exp(-2j * np.pi * np.outer(f, i) / rs) @ z)
    k = int(np.argmax(J))
    if 0 < k < n_grid - 1:                       # interpolacion parabolica
        y0, y1, y2 = J[k - 1], J[k], J[k + 1]
        den = (y0 - 2 * y1 + y2)
        delta = 0.5 * (y0 - y2) / den if abs(den) > 1e-12 else 0.0
        return float(f[k] + delta * (f[1] - f[0]))
    return float(f[k])


def derotate(x: np.ndarray, f_hz: float, fs: float, phase0: float = 0.0) -> np.ndarray:
    n = np.arange(x.size)
    return x * np.exp(-1j * (2 * np.pi * f_hz * n / fs + phase0))


# ---------------------------------------------------------------------------
# 5) PLL de fase dirigido por decision
# ---------------------------------------------------------------------------


@dataclass
class PLLResult:
    symbols: np.ndarray
    phase: np.ndarray


def dd_phase_pll(sym: np.ndarray, mod: Modulation, loop_bw: float = 5e-4,
                 zeta: float = 0.707, ref: np.ndarray | None = None,
                 init_freq: float = 0.0) -> PLLResult:
    """PLL de segundo orden dirigido por decision (o asistido por `ref`).

    El detector de fase es e[k] = Im{ y[k] d*[k] } / |d[k]|^2, con d[k] la
    decision dura (o el simbolo conocido durante el entrenamiento).

    `init_freq` siembra el integrador del lazo con un incremento de fase por
    simbolo conocido (rad/simbolo). Es importante: el escalon de FASE inicial ya
    lo elimina la normalizacion de ganancia compleja de un tap, de modo que lo
    unico que le queda al lazo es seguir la RAMPA que deja el residuo del
    estimador grueso de frecuencia. Ante un escalon de frecuencia un lazo de
    segundo orden acaba con error nulo, pero su transitorio dura ~1/(Bn*T)
    simbolos -- 2000 con Bn*T = 5e-4 -- y el error de fase acumulado durante ese
    tramo supera el margen de decision de una constelacion densa como 16-QAM,
    provocando fallos catastroficos intermitentes. Sembrando el integrador el
    lazo arranca ya en regimen.

    Ensanchar el lazo durante el entrenamiento NO es una alternativa valida
    aqui: la ganancia integral crece con el ancho de banda y el integrador
    ejecuta un paseo aleatorio sobre los simbolos de entrenamiento, terminando
    con un error de frecuencia mucho mayor del que se pretendia corregir.
    """
    kp, ki = loop_gains(loop_bw, zeta, k_det=1.0, n_per_update=1)
    n_ref = 0 if ref is None else int(ref.size)

    out = np.empty_like(sym)
    ph = np.empty(sym.size)
    phase = 0.0
    integ = float(init_freq)
    for k, s in enumerate(sym):
        y = s * np.exp(-1j * phase)
        d = ref[k] if k < n_ref else mod.slice(np.array([y]))[0]
        e = np.imag(y * np.conj(d)) / (np.abs(d) ** 2 + 1e-12)
        integ += ki * e
        phase += kp * e + integ
        out[k] = y
        ph[k] = phase
    return PLLResult(symbols=out, phase=ph)

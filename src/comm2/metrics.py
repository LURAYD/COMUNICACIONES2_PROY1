"""Metricas de desempeno (Seccion 10 de la guia)."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy import signal

from .modulation import Modulation


# ---------------------------------------------------------------------------
# Tasa de error
# ---------------------------------------------------------------------------


@dataclass
class ErrorRate:
    errors: int
    total: int

    @property
    def rate(self) -> float:
        return self.errors / self.total if self.total else np.nan

    @property
    def ci95(self) -> tuple[float, float]:
        """Intervalo de confianza 95 % (aproximacion normal de la binomial)."""
        p, n = self.rate, self.total
        if n == 0 or not np.isfinite(p):
            return (np.nan, np.nan)
        s = 1.96 * np.sqrt(max(p * (1 - p), 1e-12) / n)
        return (max(p - s, 0.0), min(p + s, 1.0))

    def __repr__(self):
        return f"{self.rate:.3e} ({self.errors}/{self.total})"


def bit_error_rate(tx_bits: np.ndarray, rx_bits: np.ndarray) -> ErrorRate:
    n = min(tx_bits.size, rx_bits.size)
    e = int(np.count_nonzero(tx_bits[:n] != rx_bits[:n]))
    return ErrorRate(e, n)


def symbol_error_rate(tx_idx: np.ndarray, rx_idx: np.ndarray) -> ErrorRate:
    n = min(tx_idx.size, rx_idx.size)
    e = int(np.count_nonzero(tx_idx[:n] != rx_idx[:n]))
    return ErrorRate(e, n)


def min_bits_for_ber(target_ber: float, n_errors: int = 100) -> int:
    """Bits necesarios para estimar `target_ber` con ~n_errors errores."""
    return int(np.ceil(n_errors / max(target_ber, 1e-12)))


# ---------------------------------------------------------------------------
# Calidad de constelacion
# ---------------------------------------------------------------------------


def symbol_mse(rx: np.ndarray, ref: np.ndarray) -> float:
    """Error cuadratico medio de simbolo (tras alineacion de fase/ganancia)."""
    n = min(rx.size, ref.size)
    rx, ref = rx[:n], ref[:n]
    a = np.vdot(ref, rx) / (np.vdot(ref, ref) + 1e-12)   # ganancia compleja optima
    den = np.mean(np.abs(a * ref) ** 2)
    if den < 1e-15:                      # el receptor no engancho: MSE saturado
        return 1.0
    return float(np.mean(np.abs(rx - a * ref) ** 2) / den)


def evm_percent(rx: np.ndarray, ref: np.ndarray) -> float:
    """EVM RMS en % respecto a la potencia media de referencia."""
    return 100.0 * np.sqrt(symbol_mse(rx, ref))


def evm_to_snr_db(evm_pct: float) -> float:
    return -20 * np.log10(max(evm_pct, 1e-9) / 100.0)


def estimate_snr_m2m4(r: np.ndarray, kurtosis_signal: float = 1.0) -> float:
    """Estimador ciego de SNR M2M4 (util para el informe / validacion cruzada).

    Para constelaciones de modulo constante (ka = 1) y ruido gaussiano (kw = 2):
        M2 = S + N,  M4 = 2 S^2 + 4 S N + 2 N^2  ->  S = sqrt(2 M2^2 - M4)
    """
    m2 = np.mean(np.abs(r) ** 2)
    m4 = np.mean(np.abs(r) ** 4)
    val = 2 * m2 ** 2 - m4
    if val <= 0:
        return -np.inf
    s = np.sqrt(val)
    n = m2 - s
    if n <= 0:
        return np.inf
    return float(10 * np.log10(s / n))


# ---------------------------------------------------------------------------
# Espectro y diagrama de ojo
# ---------------------------------------------------------------------------


def psd(x: np.ndarray, fs: float, nperseg: int = 2048) -> tuple[np.ndarray, np.ndarray]:
    """Densidad espectral de potencia (Welch), centrada y en dB/Hz."""
    f, p = signal.welch(x, fs=fs, nperseg=min(nperseg, x.size),
                        return_onesided=False, detrend=False, scaling="density")
    idx = np.argsort(f)
    return f[idx], 10 * np.log10(p[idx] + 1e-20)


def occupied_bandwidth(x: np.ndarray, fs: float, fraction: float = 0.99) -> float:
    """Ancho de banda que contiene el `fraction` de la potencia total."""
    f, pdb = psd(x, fs)
    p = 10 ** (pdb / 10)
    p = p / p.sum()
    order = np.argsort(np.abs(f))
    cum = np.cumsum(p[order])
    k = int(np.searchsorted(cum, fraction))
    k = min(k, order.size - 1)
    return float(2 * np.abs(f[order][k]))


def eye_data(x: np.ndarray, sps: int, n_traces: int = 200, span: int = 2,
             offset: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Trazas para el diagrama de ojo. Devuelve (t [T], matriz n_traces x L)."""
    L = span * sps
    start = offset
    usable = (x.size - start) // L
    n = int(min(n_traces, usable))
    if n <= 0:
        return np.array([]), np.zeros((0, L))
    seg = x[start:start + n * L].reshape(n, L)
    t = np.arange(L) / sps - span / 2
    return t, seg


def best_sampling_phase(x: np.ndarray, sps: int) -> int:
    """Fase de muestreo (0..sps-1) que maximiza la potencia media.

    Con un pulso de Nyquist la potencia de las muestras es maxima en el
    instante optimo, asi que este criterio localiza el centro del ojo sin
    necesitar la referencia de temporizacion.
    """
    p = [np.mean(np.abs(x[o::sps]) ** 2) for o in range(sps)]
    return int(np.argmax(p))


def slow_phase(x: np.ndarray, constellation: np.ndarray, sps: int = 1,
               offset: int = 0, block: int = 32) -> np.ndarray:
    """Giro lento de portadora de una senal, estimado a ciegas, muestra a muestra.

    Estimador de potencia P-esima por bloques de `block` simbolos (P = 4 para
    QPSK/QAM, 8 para 8PSK), desenrollado entre bloques e interpolado. Sirve
    para DIBUJAR el ojo: el ojo mide ISI y ruido sobre la componente I, y un
    giro residual de unos pocos Hz mezcla I con Q y lo cierra aunque no haya
    ISI (medido: 11 Hz de residuo del estimador grueso giran 16 grados en los
    600 simbolos del ojo y cierran el de AWGN a 12 dB). El receptor no lo usa.

    x : senal a tasa de simbolo (sps=1) o sobremuestreada, muestreada en
        `offset` para la estimacion. Devuelve la fase para cada muestra de x.
    """
    x = np.asarray(x)
    c = np.asarray(constellation)
    P = 8 if (np.allclose(np.abs(c), np.abs(c[0])) and c.size == 8) else 4
    ref = np.angle(np.mean(c ** P))              # fase de referencia de c^P
    s = x[offset::sps] if sps > 1 else x
    nb = max(1, s.size // block)
    centers, ph = [], []
    for b in range(nb):
        seg = s[b * block:(b + 1) * block]
        ph.append(np.angle(np.sum(seg ** P) * np.exp(-1j * ref)))
        centers.append((b * block + seg.size / 2.0) * sps + offset)
    ph = np.unwrap(np.array(ph)) / P
    return np.interp(np.arange(x.size), np.array(centers), ph)


def eye_opening(x: np.ndarray, sps: int = 1, offset: int | None = None) -> dict:
    """Apertura vertical normalizada del ojo, sobre la componente en fase.

    Devuelve la distancia entre el percentil 5 de los niveles positivos y el
    percentil 95 de los negativos, dividida por la separacion media entre esos
    dos niveles. Un ojo limpio da ~1; un ojo cerrado, <= 0.

    `x` puede darse sobremuestreado (indicando `sps`) o ya a tasa de simbolo
    (sps = 1). Si `offset` es None se busca automaticamente el instante optimo.
    """
    if sps > 1:
        off = best_sampling_phase(x, sps) if offset is None else offset
        s = np.real(x[off::sps])
    else:
        s = np.real(x)
    s = s[np.abs(s) > 1e-9]
    pos, neg = s[s > 0], s[s < 0]
    if pos.size < 8 or neg.size < 8:
        return {"opening": np.nan, "jitter_std": np.nan, "offset": -1}
    level = (np.mean(pos) - np.mean(neg)) / 2.0
    op = (np.percentile(pos, 5) - np.percentile(neg, 95)) / (2.0 * level + 1e-12)
    jit = float(np.std(np.abs(s)) / (np.mean(np.abs(s)) + 1e-12))
    return {"opening": float(op), "jitter_std": jit,
            "offset": int(off) if sps > 1 else 0}


# ---------------------------------------------------------------------------
# Interferencia intersimbolica
# ---------------------------------------------------------------------------


def isi_metrics(c: np.ndarray) -> dict:
    """Medidas de ISI de un canal equivalente a tasa de simbolo c[k].

    El cursor es el coeficiente de mayor modulo (el que toma el receptor como
    referencia de temporizacion); todos los demas son ISI.

      sir_db          |c0|^2 / sum_{k!=0} |ck|^2          senal util / ISI
      peak_distortion D = sum_{k!=0} |ck| / |c0|           D >= 1 -> ojo cerrado (BPSK)
      eye_worst_qpsk  1 - sum_{k!=0} (|Re c'k| + |Im c'k|), c' = c/c0
                      apertura vertical de peor caso del carril I en QPSK,
                      normalizada al nivel sin ISI (1 = ojo limpio, <= 0 cerrado)
      energy          sum |ck|^2: potencia util que entrega el canal (1 si la
                      normalizacion del perfil conserva la SNR)
    """
    c = np.atleast_1d(np.asarray(c, dtype=complex))
    i0 = int(np.argmax(np.abs(c)))
    c0 = c[i0]
    rest = np.delete(c, i0)
    isi = float(np.sum(np.abs(rest) ** 2))
    cn = rest / c0
    return {
        "cursor": i0, "n_pre": i0, "n_post": int(c.size - i0 - 1),
        "c0": complex(c0),
        "sir_db": float(10 * np.log10(abs(c0) ** 2 / isi)) if isi > 0 else np.inf,
        "peak_distortion": float(np.sum(np.abs(rest)) / abs(c0)),
        "eye_worst_qpsk": float(1 - np.sum(np.abs(cn.real) + np.abs(cn.imag))),
        "energy": float(np.sum(np.abs(c) ** 2)),
    }


def eye_opening_known(rx: np.ndarray, ref: np.ndarray, q: float = 0.0) -> float:
    """Apertura vertical del ojo (carril I) agrupando por el simbolo TRANSMITIDO.

    `eye_opening` agrupa por el signo de la muestra recibida y por tanto nunca
    baja de 0 aunque el ojo este cerrado. Aqui, con los simbolos conocidos
    (rx alineado con ref, cursor en el retardo 0), un ojo cerrado da < 0.
    q es el percentil de cada grupo (0 = peor caso observado). Normalizada al
    nivel medio, comparable con isi_metrics()['eye_worst_qpsk'].
    """
    n = min(rx.size, ref.size)
    y, s = np.real(rx[:n]), np.real(ref[:n])
    pos, neg = y[s > 0], y[s < 0]
    level = (np.mean(pos) - np.mean(neg)) / 2.0
    return float((np.percentile(pos, 100 * q) - np.percentile(neg, 100 * (1 - q)))
                 / (2.0 * level + 1e-12))


def mmse_le_snr_db(c: np.ndarray, esn0_db: float, n_freq: int = 4096) -> float:
    """SNR maxima de CUALQUIER ecualizador lineal (MMSE, infinitos taps).

    MMSE = integral_{-1/2}^{1/2} df / (1 + Es/N0 |C(f)|^2) y SNR = 1/MMSE, que
    acota la SNR medida como 1/EVM^2 (error frente al simbolo transmitido). Con
    canal plano de energia 1 vale 1 + Es/N0. Superarla exige un ecualizador no
    lineal (DFE, MLSE).
    """
    f = np.linspace(-0.5, 0.5, n_freq, endpoint=False)
    C = np.exp(-2j * np.pi * np.outer(f, np.arange(np.size(c)))) @ np.asarray(c)
    snr = 10 ** (esn0_db / 10)
    return float(-10 * np.log10(np.mean(1 / (1 + snr * np.abs(C) ** 2))))


def estimate_symbol_channel(rx: np.ndarray, ref: np.ndarray, n_pre: int = 8,
                            n_post: int = 8) -> tuple[np.ndarray, float]:
    """Estima por minimos cuadrados el canal a tasa de simbolo que vio `rx`.

    Ajusta rx[n] ~ sum_{k=-n_pre}^{n_post} c[k] ref[n-k] con los simbolos
    transmitidos conocidos. Es la medida *experimental* de la ISI: sale de la
    senal recibida, sin conocer el canal. Devuelve (c, varianza del residuo);
    c[n_pre] corresponde al retardo 0 y el residuo es ruido mas todo lo que un
    FIR lineal no explica (jitter de temporizacion, deriva de fase).
    """
    n = min(rx.size, ref.size)
    L = n_pre + n_post + 1
    rows = np.arange(n_post, n - n_pre)
    # columna j <-> retardo k = j - n_pre, simbolo ref[n - k]
    idx = rows[:, None] - (np.arange(L)[None, :] - n_pre)
    A = ref[idx]
    b = rx[rows]
    c, *_ = np.linalg.lstsq(A, b, rcond=None)
    resid = b - A @ c
    return c, float(np.mean(np.abs(resid) ** 2))


# ---------------------------------------------------------------------------
# Eficiencia espectral
# ---------------------------------------------------------------------------


def spectral_efficiency(bits_per_symbol: int, beta: float) -> float:
    """eta = Rb / B = k / (1 + beta)  [bit/s/Hz]."""
    return bits_per_symbol / (1.0 + beta)


def shannon_limit(snr_db: float) -> float:
    return float(np.log2(1 + 10 ** (snr_db / 10.0)))


def summarize(mod: Modulation, rx_sym: np.ndarray, tx_sym: np.ndarray,
              tx_bits: np.ndarray, rx_bits: np.ndarray, beta: float) -> dict:
    tx_idx = mod.hard_decide(tx_sym)
    rx_idx = mod.hard_decide(rx_sym)
    ber = bit_error_rate(tx_bits, rx_bits)
    ser = symbol_error_rate(tx_idx, rx_idx)
    return {
        "ber": ber.rate, "ber_errors": ber.errors, "ber_bits": ber.total,
        "ber_ci_lo": ber.ci95[0], "ber_ci_hi": ber.ci95[1],
        "ser": ser.rate, "ser_errors": ser.errors, "ser_symbols": ser.total,
        "mse": symbol_mse(rx_sym, tx_sym),
        "evm_pct": evm_percent(rx_sym, tx_sym),
        "snr_evm_db": evm_to_snr_db(evm_percent(rx_sym, tx_sym)),
        "eta_bps_hz": spectral_efficiency(mod.bits_per_symbol, beta),
    }

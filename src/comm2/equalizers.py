"""Ecualizadores (Seccion 8 de la guia).

Convenio de indices
-------------------
El ecualizador es un FIR de N taps con tap de referencia D. La salida es

    y[n] = w^H u[n] = sum_i f[i] r[n + D - i],     f = conj(w)

donde u[n] es el vector regresor. Con la inicializacion w = e_D se obtiene
y[n] = r[n], es decir, el receptor *sin ecualizar*: eso hace que la curva de
aprendizaje arranque exactamente en el desempeno del caso base.

Metodos implementados
---------------------
  none  : paso directo (referencia).
  lms   : Least Mean Squares.        w <- w + mu u e*        O(N)
  rls   : Recursive Least Squares.   ganancia de Kalman      O(N^2)
  zf    : Zero-Forcing (LS) a partir del canal conocido.
  mmse  : MMSE (Wiener) a partir del canal conocido y sigma^2.
  cma   : Constant Modulus Algorithm (ciego, Godard 1980).

Referencias:
  S. Haykin, "Adaptive Filter Theory", 5a ed., Pearson, 2014, caps. 5-10.
  D. N. Godard, "Self-recovering equalization and carrier tracking in
    two-dimensional data communication systems", IEEE Trans. Commun.,
    28(11), pp. 1867-1875, 1980.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import numpy as np

from .modulation import Modulation
from .params import EqualizerConfig


# ---------------------------------------------------------------------------
# Resultado comun
# ---------------------------------------------------------------------------


@dataclass
class EqResult:
    y: np.ndarray                  # salida ecualizada (mismo largo que la entrada)
    err: np.ndarray                # senal de error instantanea |e|^2
    w: np.ndarray                  # taps finales
    kind: str
    n_taps: int
    ref_tap: int
    learning_curve: np.ndarray = field(default=None)   # |e|^2 suavizado [dB]
    steady_mse_db: float = np.nan
    convergence_symbols: int = -1   # -1: no converge / no aplica (none, zf, mmse)
    flops_per_symbol: dict = field(default_factory=dict)

    def time_to_reach(self, mse_db: float, hold: int = 16) -> int:
        """Simbolos hasta que el MSE suavizado baja de un umbral ABSOLUTO.

        `convergence_symbols` mide el tiempo hasta estabilizarse en el propio
        regimen permanente, lo que penaliza injustamente al algoritmo con mejor
        MSE final: un metodo que converge lento pero muy abajo puede parecer
        rapido. Para comparar LMS y RLS (Experimento 3) hace falta un umbral
        comun; -1 indica que nunca se alcanza.

        `hold` exige que la curva se mantenga bajo el umbral durante ese numero
        de simbolos consecutivos, para que una sola muestra afortunada al
        arrancar no se contabilice como convergencia.
        """
        lc = self.learning_curve
        if lc is None or lc.size == 0:
            return -1
        below = lc <= mse_db
        if hold <= 1:
            idx = np.where(below)[0]
            return int(idx[0]) if idx.size else -1
        # ventana deslizante: primer i con below[i:i+hold] todo True
        run = np.convolve(below.astype(int), np.ones(hold, dtype=int), mode="valid")
        idx = np.where(run == hold)[0]
        return int(idx[0]) if idx.size else -1

    def summary(self) -> str:
        return (f"{self.kind.upper():5s} N={self.n_taps:3d} D={self.ref_tap:3d} | "
                f"MSE_res={self.steady_mse_db:6.2f} dB | "
                f"conv={self.convergence_symbols:4d} simb | "
                f"{self.flops_per_symbol.get('real_mults', 0):6d} mult. reales/simb")


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _regressors(r: np.ndarray, n_taps: int, ref_tap: int) -> np.ndarray:
    """Matriz de regresores u[n] (n_out x N), fila n = ventana para la salida n."""
    pre = n_taps - 1 - ref_tap
    rp = np.concatenate([np.zeros(pre, dtype=complex), r, np.zeros(ref_tap, dtype=complex)])
    n_out = r.size
    # ventana deslizante: u[n] = rp[n : n+N] invertida
    idx = np.arange(n_out)[:, None] + np.arange(n_taps)[None, :]
    return rp[idx][:, ::-1]


def _smooth(x: np.ndarray, win: int = 32) -> np.ndarray:
    """Media movil CAUSAL (solo muestras pasadas), normalizada en el arranque.

    Con una ventana centrada y relleno de ceros (`np.convolve(..., 'same')`) el
    inicio de la curva de aprendizaje queda artificialmente por debajo del valor
    real, y el tiempo de convergencia medido sale cero. Una media movil causal
    con normalizacion exacta evita ese sesgo.
    """
    if win <= 1 or x.size < 2:
        return x.astype(float)
    c = np.concatenate([[0.0], np.cumsum(x)])
    i = np.arange(x.size)
    lo = np.maximum(i - win + 1, 0)
    return (c[i + 1] - c[lo]) / (i - lo + 1)


def _analyze(err2: np.ndarray, n_train: int, adaptive: bool = True,
             diverged: bool = False, check_head: bool = True) -> tuple[np.ndarray, float, int]:
    """Curva de aprendizaje, MSE residual y tiempo de convergencia.

    Convergencia = primer simbolo en que la mediana movil de |e|^2 entra en la
    banda de 3 dB sobre el regimen permanente. Antes se tomaba el ULTIMO
    simbolo fuera de la banda, y cualquier rafaga de errores de decision al
    final de la trama lo disparaba: medido en escenario B moderado a 20 dB con
    cinco semillas, el RLS daba 71/288/54/4146/-1; con la primera entrada da
    56/53/54/68/62, del orden de 2N-3N que predice la teoria del RLS. Es una
    sola realizacion: la curva de aprendizaje de la teoria es un promedio de
    conjunto. Se devuelve -1 si:
      - el ecualizador no es adaptativo (`adaptive=False`: none/zf/mmse), pues
        no hay proceso de convergencia que medir;
      - el filtro diverge (`diverged`, o con `check_head` la curva termina mas de
        3 dB peor que como empezo): sin esta guarda, una curva que nunca supera
        estado_estacionario+3 dB daba conv = 0, "convergio al instante". El CMA
        pasa check_head=False: su error de dispersion en QAM no baja de ~-3 dB
        y el inicio no es comparable;
      - la curva nunca se estabiliza.
    """
    err2 = np.nan_to_num(np.asarray(err2, dtype=float), nan=1e30, posinf=1e30)
    lc = 10 * np.log10(_smooth(err2, 32) + 1e-15)
    # Los ultimos simbolos tienen la ventana de regresores rellena de ceros
    # (fin de la rafaga): su error crece por el borde, no por el filtro. Se
    # excluyen del regimen permanente y del instante de convergencia.
    edge = min(64, err2.size // 10)
    err2 = err2[:err2.size - edge]
    tail = max(16, err2.size // 10)
    steady = 10 * np.log10(np.mean(err2[-tail:]) + 1e-15)
    if not adaptive:
        return lc, float(steady), -1
    # Medianas y no medias: un solo error de decision da un |e|^2 cientos de
    # veces mayor que el MSE y, con la media, una trama ya convergida parecia
    # "terminar peor que empezo" (divergencia falsa).
    head = 10 * np.log10(np.median(err2[:min(32, err2.size)]) + 1e-15)
    steady_m = 10 * np.log10(np.median(err2[-tail:]) + 1e-15)
    if diverged or not np.isfinite(steady) or (check_head and steady_m > head + 3.0):
        return lc, float(steady), -1                # diverge: termina peor que empezo
    from scipy.ndimage import median_filter
    lcm = 10 * np.log10(median_filter(err2, size=65, mode="nearest") + 1e-15)
    inside = np.where(lcm <= steady_m + 3.0)[0]
    conv = int(inside[0]) if inside.size else -1   # -1: nunca entra en la banda
    return lc, float(steady), conv


def flop_count(kind: str, n_taps: int) -> dict:
    """Coste computacional por simbolo (multiplicaciones reales equivalentes).

    Una multiplicacion compleja = 4 multiplicaciones reales.
      LMS : N (filtrado) + N (actualizacion) = 2N mult. complejas -> 8N
      RLS : ~4N^2 + 4N mult. complejas                            -> 16N^2+16N
      ZF/MMSE (fijos): solo filtrado, N mult. complejas           -> 4N
      CMA : como LMS mas el calculo de |y|^2                      -> 8N + 4
    """
    n = n_taps
    table = {
        "none": 0,
        "lms": 8 * n,
        "cma": 8 * n + 4,
        "rls": 16 * n * n + 16 * n,
        "zf": 4 * n,
        "mmse": 4 * n,
    }
    order = {"none": "-", "lms": "O(N)", "cma": "O(N)", "rls": "O(N^2)",
             "zf": "O(N)", "mmse": "O(N)"}
    return {"real_mults": int(table.get(kind, 0)), "order": order.get(kind, "?"),
            "n_taps": n}


# ---------------------------------------------------------------------------
# Algoritmos adaptativos
# ---------------------------------------------------------------------------


def run_lms(r: np.ndarray, train: np.ndarray, mod: Modulation, cfg: EqualizerConfig,
            normalized: bool = True) -> EqResult:
    """LMS (opcionalmente normalizado) con conmutacion a modo DD."""
    n, d = cfg.n_taps, cfg.resolved_ref_tap()
    u_all = _regressors(r, n, d)
    w = np.zeros(n, dtype=complex)
    w[d] = 1.0                                   # arranque = sin ecualizar
    y = np.empty(r.size, dtype=complex)
    err2 = np.empty(r.size)
    nt = train.size
    for k in range(r.size):
        u = u_all[k]
        yk = np.vdot(w, u)                       # w^H u
        if k < nt:
            dk = train[k]
            mu = cfg.mu
        else:
            if not cfg.decision_directed:
                y[k:] = u_all[k:] @ np.conj(w)
                err2[k:] = err2[k - 1] if k else 0.0
                break
            dk = mod.slice(np.array([yk]))[0]
            mu = cfg.mu * cfg.dd_mu_scale
        e = dk - yk
        step = mu / (np.vdot(u, u).real + 1e-9) if normalized else mu
        w = w + step * u * np.conj(e)
        y[k] = yk
        err2[k] = np.abs(e) ** 2
    lc, steady, conv = _analyze(err2, nt)
    return EqResult(y=y, err=err2, w=w, kind="lms", n_taps=n, ref_tap=d,
                    learning_curve=lc, steady_mse_db=steady,
                    convergence_symbols=conv, flops_per_symbol=flop_count("lms", n))


def run_rls(r: np.ndarray, train: np.ndarray, mod: Modulation,
            cfg: EqualizerConfig) -> EqResult:
    """RLS con factor de olvido lambda e inicializacion P = delta^-1 I."""
    n, d = cfg.n_taps, cfg.resolved_ref_tap()
    u_all = _regressors(r, n, d)
    w = np.zeros(n, dtype=complex)
    w[d] = 1.0
    P = np.eye(n, dtype=complex) / cfg.delta
    lam = cfg.lam
    y = np.empty(r.size, dtype=complex)
    err2 = np.empty(r.size)
    nt = train.size
    for k in range(r.size):
        u = u_all[k]
        yk = np.vdot(w, u)
        if k < nt:
            dk = train[k]
        else:
            if not cfg.decision_directed:
                y[k:] = u_all[k:] @ np.conj(w)
                err2[k:] = err2[k - 1] if k else 0.0
                break
            dk = mod.slice(np.array([yk]))[0]
        e = dk - yk
        Pu = P @ u
        g = Pu / (lam + np.vdot(u, Pu).real + 1e-12)      # ganancia de Kalman
        w = w + g * np.conj(e)
        P = (P - np.outer(g, np.conj(Pu))) / lam
        # Estabilizacion numerica: la recursion de Riccati pierde la simetria
        # hermitica por redondeo y, con lambda < 1, el error se amplifica en
        # 1/lambda por iteracion hasta que P deja de ser definida positiva y el
        # algoritmo diverge. Simetrizar en cada paso es la salvaguarda clasica.
        P = 0.5 * (P + P.conj().T)
        y[k] = yk
        err2[k] = np.abs(e) ** 2
    lc, steady, conv = _analyze(err2, nt)
    return EqResult(y=y, err=err2, w=w, kind="rls", n_taps=n, ref_tap=d,
                    learning_curve=lc, steady_mse_db=steady,
                    convergence_symbols=conv, flops_per_symbol=flop_count("rls", n))


CMA_MU_SCALE = 0.1      # factor entre el mu del deslizador (NLMS) y el del CMA


def run_cma(r: np.ndarray, train: np.ndarray, mod: Modulation,
            cfg: EqualizerConfig) -> EqResult:
    """CMA normalizado (variante propia del CMA de Godard, p = 2): ciego.

    No usa la secuencia de entrenamiento. El gradiente de Godard
    (|y|^2 - R2) y* u se divide por ||u||^2 (CMA normalizado, conocido) y ADEMAS
    por max(|y|^2, R2), que no es estandar: estabiliza en todo el rango del
    deslizador, pero pesa distinto cada muestra en la condicion de equilibrio,
    asi que no es exactamente el CMA de Godard y debe citarse como variante.
    `err` y la curva de aprendizaje son el error de DISPERSION (|y|^2 - R2)^2,
    no el error frente al simbolo transmitido: no son comparables con el MSE
    del LMS/RLS y en QAM no tienden a cero.
    """
    n, d = cfg.n_taps, cfg.resolved_ref_tap()
    u_all = _regressors(r, n, d)
    w = np.zeros(n, dtype=complex)
    w[d] = 1.0
    c = mod.constellation
    R2 = np.mean(np.abs(c) ** 4) / np.mean(np.abs(c) ** 2)
    y = np.empty(r.size, dtype=complex)
    err2 = np.empty(r.size)
    # El deslizador mu es el del NLMS (rango [0.01, 1]); el CMA es un gradiente
    # de orden 3 en |y| y diverge con ese rango, asi que usa mu * CMA_MU_SCALE.
    mu_eff = cfg.mu * CMA_MU_SCALE
    w0 = w.copy()
    n_reset = 0
    for k in range(r.size):
        u = u_all[k]
        yk = np.vdot(w, u)
        eps = np.abs(yk) ** 2 - R2
        eps = float(np.clip(eps, -10 * R2, 10 * R2))
        # paso normalizado por ||u||^2 y por max(|y|^2, R2): el efecto sobre la
        # salida es dy = -mu_eff * eps * y / max(|y|^2, R2), una contraccion para
        # mu_eff < 1 aunque |y| sea enorme (el gradiente crudo crece con |y|^3).
        step = mu_eff / ((np.vdot(u, u).real + 1e-9) * max(abs(yk) ** 2, R2))
        # actualizacion CMA: w <- w - mu (|y|^2 - R2) y* u  (gradiente de Godard)
        wn = w - step * eps * np.conj(yk) * u
        if np.all(np.isfinite(wn)):
            w = wn
        else:                                       # divergencia: reinicia al tap central
            w = w0.copy()
            n_reset += 1
        y[k] = yk
        err2[k] = eps ** 2
    tail = err2[-max(16, err2.size // 10):]
    diverged = (not np.all(np.isfinite(y)) or np.mean(tail) > 4 * R2 ** 2
                or n_reset > r.size // 10)
    lc, steady, conv = _analyze(err2, train.size, diverged=diverged, check_head=False)
    return EqResult(y=y, err=err2, w=w, kind="cma", n_taps=n, ref_tap=d,
                    learning_curve=lc, steady_mse_db=steady,
                    convergence_symbols=conv, flops_per_symbol=flop_count("cma", n))


# ---------------------------------------------------------------------------
# Ecualizadores fijos calculados a partir del canal
# ---------------------------------------------------------------------------


def _conv_matrix(c: np.ndarray, n_taps: int) -> np.ndarray:
    """Matriz de convolucion A ((Lc+N-1) x N) tal que A f = f * c."""
    lc = c.size
    A = np.zeros((lc + n_taps - 1, n_taps), dtype=complex)
    for j in range(n_taps):
        A[j:j + lc, j] = c
    return A


def design_zf(c: np.ndarray, n_taps: int, ref_tap: int) -> np.ndarray:
    """Ecualizador Zero-Forcing por minimos cuadrados: min ||f*c - delta_D||."""
    A = _conv_matrix(c, n_taps)
    b = np.zeros(A.shape[0], dtype=complex)
    b[min(ref_tap, A.shape[0] - 1)] = 1.0
    f, *_ = np.linalg.lstsq(A, b, rcond=None)
    return np.conj(f)                                # w = conj(f)


def design_mmse(c: np.ndarray, n_taps: int, ref_tap: int, sigma2: float) -> np.ndarray:
    """Ecualizador MMSE (Wiener): f = (A^H A + sigma^2 I)^-1 A^H delta_D."""
    A = _conv_matrix(c, n_taps)
    b = np.zeros(A.shape[0], dtype=complex)
    b[min(ref_tap, A.shape[0] - 1)] = 1.0
    R = A.conj().T @ A + sigma2 * np.eye(n_taps)
    f = np.linalg.solve(R, A.conj().T @ b)
    return np.conj(f)


def run_fixed(r: np.ndarray, w: np.ndarray, train: np.ndarray, kind: str,
              ref_tap: int) -> EqResult:
    """Aplica un ecualizador de coeficientes fijos."""
    n = w.size
    u_all = _regressors(r, n, ref_tap)
    y = u_all @ np.conj(w)
    # AGC de salida: ZF/MMSE no garantizan ganancia unitaria y las decisiones
    # de QAM (a diferencia de PSK) dependen de la escala absoluta.
    nt0 = min(train.size, y.size)
    if nt0 > 0:
        a = np.vdot(train[:nt0], y[:nt0]) / (np.vdot(train[:nt0], train[:nt0]) + 1e-12)
        if abs(a) > 1e-9:
            y = y / a
            w = w * np.conj(a)
    err2 = np.zeros(r.size)
    nt = min(train.size, r.size)
    err2[:nt] = np.abs(train[:nt] - y[:nt]) ** 2
    err2[nt:] = np.mean(err2[:nt]) if nt else 0.0
    lc, steady, conv = _analyze(err2, nt, adaptive=False)
    return EqResult(y=y, err=err2, w=w, kind=kind, n_taps=n, ref_tap=ref_tap,
                    learning_curve=lc, steady_mse_db=steady, convergence_symbols=-1,
                    flops_per_symbol=flop_count(kind, n))


def run_none(r: np.ndarray, train: np.ndarray) -> EqResult:
    err2 = np.zeros(r.size)
    nt = min(train.size, r.size)
    err2[:nt] = np.abs(train[:nt] - r[:nt]) ** 2
    err2[nt:] = np.mean(err2[:nt]) if nt else 0.0
    lc, steady, conv = _analyze(err2, nt, adaptive=False)
    return EqResult(y=r.copy(), err=err2, w=np.array([1.0 + 0j]), kind="none",
                    n_taps=1, ref_tap=0, learning_curve=lc, steady_mse_db=steady,
                    convergence_symbols=-1, flops_per_symbol=flop_count("none", 1))


# ---------------------------------------------------------------------------
# Despachador
# ---------------------------------------------------------------------------


def equalize(r: np.ndarray, train: np.ndarray, mod: Modulation, cfg: EqualizerConfig,
             channel_sym: Optional[np.ndarray] = None,
             sigma2: float = 0.0) -> EqResult:
    """Ejecuta el ecualizador indicado en `cfg.kind`."""
    kind = cfg.kind.lower()
    if kind == "none":
        return run_none(r, train)
    if kind == "lms":
        return run_lms(r, train, mod, cfg)
    if kind == "rls":
        return run_rls(r, train, mod, cfg)
    if kind == "cma":
        return run_cma(r, train, mod, cfg)
    if kind in ("zf", "mmse"):
        if channel_sym is None:
            raise ValueError(f"'{kind}' requiere el canal equivalente a tasa de simbolo")
        d = cfg.resolved_ref_tap()
        # el retardo total optimo incluye el retardo del propio canal
        d_tot = d + int(np.argmax(np.abs(channel_sym)))
        w = (design_zf(channel_sym, cfg.n_taps, d_tot) if kind == "zf"
             else design_mmse(channel_sym, cfg.n_taps, d_tot, sigma2))
        return run_fixed(r, w, train, kind, d)
    raise ValueError(f"ecualizador desconocido: {cfg.kind}")

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

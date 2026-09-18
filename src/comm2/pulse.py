"""Conformacion de pulsos: Root Raised Cosine (RRC) y Raised Cosine (RC).

Se implementa la formula analitica en lugar de usar una libreria externa,
tanto por control como porque el desarrollo forma parte de la fundamentacion
teorica del informe (criterio 10 % de la rubrica).

    h_RRC(t) = ( sin(pi t/T (1-b)) + 4 b (t/T) cos(pi t/T (1+b)) )
               / ( pi (t/T) (1 - (4 b t/T)^2) )

con las singularidades en t = 0 y t = +-T/(4b) resueltas por limite.
El filtro se normaliza a energia unitaria (sum h^2 = 1), de modo que la
cascada TX-RRC + RX-RRC tiene ganancia unitaria en el instante optimo y la
contabilidad de Es/N0 tras el filtro adaptado es directa.
"""

from __future__ import annotations

import numpy as np
from scipy import signal


def rrc_filter(beta: float, span: int, sps: int, normalize: str = "energy") -> np.ndarray:
    """Respuesta al impulso del filtro de raiz de coseno alzado.

    Parameters
    ----------
    beta : roll-off en [0, 1]
    span : duracion total del filtro en simbolos (se usa span*sps+1 muestras)
    sps  : muestras por simbolo
    normalize : 'energy' (sum h^2 = 1) o 'peak' (h[0] = 1) o 'none'
    """
    if not 0.0 <= beta <= 1.0:
        raise ValueError("beta debe estar en [0, 1]")
    n = np.arange(-span * sps / 2, span * sps / 2 + 1)
    t = n / sps                                   # tiempo en periodos de simbolo
    h = np.zeros_like(t, dtype=float)

    # --- caso general -----------------------------------------------------
    with np.errstate(divide="ignore", invalid="ignore"):
        num = np.sin(np.pi * t * (1 - beta)) + 4 * beta * t * np.cos(np.pi * t * (1 + beta))
        den = np.pi * t * (1 - (4 * beta * t) ** 2)
        h = num / den

    # --- singularidad t = 0 ----------------------------------------------
    i0 = np.isclose(t, 0.0)
    h[i0] = 1.0 - beta + 4 * beta / np.pi

    # --- singularidad t = +- T/(4 beta) ----------------------------------
    if beta > 0:
        ic = np.isclose(np.abs(t), 1.0 / (4 * beta))
        if ic.any():
            h[ic] = (beta / np.sqrt(2)) * (
                (1 + 2 / np.pi) * np.sin(np.pi / (4 * beta))
                + (1 - 2 / np.pi) * np.cos(np.pi / (4 * beta))
            )

    if normalize == "energy":
        h = h / np.sqrt(np.sum(h ** 2))
    elif normalize == "peak":
        h = h / np.max(np.abs(h))
    return h


def rc_filter(beta: float, span: int, sps: int) -> np.ndarray:
    """Coseno alzado (respuesta conjunta TX+RX ideal, Nyquist)."""
    n = np.arange(-span * sps / 2, span * sps / 2 + 1)
    t = n / sps
    with np.errstate(divide="ignore", invalid="ignore"):
        h = np.sinc(t) * np.cos(np.pi * beta * t) / (1 - (2 * beta * t) ** 2)
    if beta > 0:
        ic = np.isclose(np.abs(t), 1.0 / (2 * beta))
        h[ic] = (np.pi / 4) * np.sinc(1 / (2 * beta))
    h[np.isnan(h)] = 0.0
    return h / np.max(np.abs(h))


def upsample(x: np.ndarray, sps: int) -> np.ndarray:
    """Insercion de sps-1 ceros entre muestras."""
    y = np.zeros(len(x) * sps, dtype=complex)
    y[::sps] = x
    return y


def pulse_shape(symbols: np.ndarray, h: np.ndarray, sps: int) -> np.ndarray:
    """Conformacion de pulso: upsample + filtrado (convolucion completa)."""
    return np.convolve(upsample(symbols, sps), h, mode="full")


def matched_filter(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    """Filtro adaptado. Para h real y simetrico coincide con el propio h."""
    return np.convolve(x, h, mode="full")


def filter_delay(h: np.ndarray) -> int:
    """Retardo de grupo (en muestras) de un FIR de fase lineal."""
    return (len(h) - 1) // 2


def frac_delay_taps(delay: float, n_taps: int = 41, window: str = "hann") -> np.ndarray:
    """FIR interpolador de retardo fraccional (sinc enventanado).

    Sirve para colocar ecos multitrayectoria en retardos no enteros y para
    introducir error de temporizacion controlado.
    """
    n = np.arange(n_taps) - (n_taps - 1) // 2
    h = np.sinc(n - delay)
    h *= signal.get_window(window, n_taps, fftbins=False)
    return h / np.sum(h)


def apply_frac_delay(x: np.ndarray, delay: float, n_taps: int = 41) -> np.ndarray:
    """Retarda x un numero fraccional de muestras conservando la longitud."""
    if np.isclose(delay, 0.0):
        return x.copy()
    int_d = int(np.floor(delay))
    frac = delay - int_d
    h = frac_delay_taps(frac, n_taps)
    y = np.convolve(x, h, mode="full")[(n_taps - 1) // 2:][: len(x)]
    if int_d > 0:
        y = np.concatenate([np.zeros(int_d, dtype=complex), y])[: len(x)]
    elif int_d < 0:
        y = np.concatenate([y[-int_d:], np.zeros(-int_d, dtype=complex)])
    return y


def excess_bandwidth_check(beta: float, sps: int) -> dict:
    """Verificacion numerica del criterio de Nyquist para el RC resultante."""
    h = rrc_filter(beta, 20, sps)
    g = np.convolve(h, h)                       # respuesta conjunta = RC
    g = g / np.max(np.abs(g))
    center = len(g) // 2
    isi_samples = g[center % sps:: sps]
    peak = np.max(np.abs(isi_samples))
    isi = np.sum(np.abs(isi_samples)) - peak
    return {"peak": float(peak), "residual_isi": float(isi)}

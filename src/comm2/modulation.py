"""Modulaciones digitales con mapeo Gray y BER/SER teoricas.

Constelaciones normalizadas a energia media unitaria: E{|s|^2} = 1.
Esto permite definir Es = 1 y trabajar directamente con Es/N0 y Eb/N0.
"""

from __future__ import annotations

import numpy as np
from scipy.special import erfc

# ---------------------------------------------------------------------------
# Utilidades Gray
# ---------------------------------------------------------------------------


def gray_code(n_bits: int) -> np.ndarray:
    """Devuelve el vector g tal que g[i] = codigo Gray del entero i."""
    i = np.arange(2 ** n_bits)
    return i ^ (i >> 1)


def _inverse_permutation(p: np.ndarray) -> np.ndarray:
    inv = np.empty_like(p)
    inv[p] = np.arange(p.size)
    return inv


# ---------------------------------------------------------------------------
# Constelaciones
# ---------------------------------------------------------------------------


def _psk_constellation(m: int) -> np.ndarray:
    """M-PSK con mapeo Gray. El indice binario natural i se coloca en el
    angulo cuyo indice Gray-decodificado es i, garantizando que simbolos
    adyacentes en fase difieran en un solo bit."""
    k = int(np.log2(m))
    angles = 2 * np.pi * np.arange(m) / m
    if m == 4:
        angles = angles + np.pi / 4          # QPSK sobre las diagonales
    points_by_position = np.exp(1j * angles)  # punto en la posicion angular n
    gray = gray_code(k)                       # gray[n] = etiqueta del angulo n
    const = np.zeros(m, dtype=complex)
    const[gray] = points_by_position          # const[etiqueta] = punto
    return const


def _qam_constellation(m: int) -> np.ndarray:
    """M-QAM cuadrada con Gray independiente por eje I y Q."""
    k = int(np.log2(m))
    assert k % 2 == 0, "solo QAM cuadrada (16, 64, 256...)"
    kh = k // 2
    l = 2 ** kh                                # niveles por eje
    levels = 2 * np.arange(l) - (l - 1)        # -(L-1) ... +(L-1)
    gray = gray_code(kh)
    axis = np.zeros(l)
    axis[gray] = levels                        # axis[etiqueta] = nivel PAM
    const = np.zeros(m, dtype=complex)
    for i in range(m):
        hi = i >> kh                           # bits mas significativos -> I
        lo = i & (l - 1)                       # bits menos significativos -> Q
        const[i] = axis[hi] + 1j * axis[lo]
    const /= np.sqrt(np.mean(np.abs(const) ** 2))
    return const


class Modulation:
    """Modulador/demodulador con mapeo Gray y energia media unitaria."""

    SUPPORTED = {"bpsk": 2, "qpsk": 4, "8psk": 8, "16qam": 16, "64qam": 64, "256qam": 256}

    def __init__(self, name: str):
        name = name.lower()
        if name not in self.SUPPORTED:
            raise ValueError(f"modulacion '{name}' no soportada: {list(self.SUPPORTED)}")
        self.name = name
        self.M = self.SUPPORTED[name]
        self.bits_per_symbol = int(np.log2(self.M))
        if name.endswith("qam"):
            self.constellation = _qam_constellation(self.M)
            self.family = "qam"
        else:
            self.constellation = _psk_constellation(self.M)
            self.family = "psk"
        # matriz de bits: fila i = etiqueta binaria del simbolo i (MSB primero)
        k = self.bits_per_symbol
        idx = np.arange(self.M)[:, None]
        self.bit_table = ((idx >> np.arange(k - 1, -1, -1)) & 1).astype(np.uint8)

    # ------------------------------------------------------------------ TX
    def modulate(self, bits: np.ndarray) -> np.ndarray:
        bits = np.asarray(bits, dtype=np.uint8).ravel()
        k = self.bits_per_symbol
        if bits.size % k:
            raise ValueError(f"numero de bits ({bits.size}) no multiplo de k={k}")
        groups = bits.reshape(-1, k)
        weights = 2 ** np.arange(k - 1, -1, -1)
        idx = groups @ weights
        return self.constellation[idx]

    def symbols_to_bits(self, idx: np.ndarray) -> np.ndarray:
        return self.bit_table[np.asarray(idx, dtype=int)].ravel()

    # ------------------------------------------------------------------ RX
    def hard_decide(self, r: np.ndarray) -> np.ndarray:
        """Decision por minima distancia euclidea. Devuelve indices."""
        r = np.asarray(r).ravel()
        d2 = np.abs(r[:, None] - self.constellation[None, :]) ** 2
        return np.argmin(d2, axis=1)

    def slice(self, r: np.ndarray) -> np.ndarray:
        """Decision dura devolviendo el simbolo mas cercano (para modo DD)."""
        return self.constellation[self.hard_decide(r)]

    def demodulate(self, r: np.ndarray) -> np.ndarray:
        return self.symbols_to_bits(self.hard_decide(r))

    # -------------------------------------------------------------- teoria
    def ber_theory(self, ebn0_db: np.ndarray) -> np.ndarray:
        """BER teorica en AWGN con mapeo Gray."""
        ebn0 = 10 ** (np.asarray(ebn0_db, dtype=float) / 10.0)
        k = self.bits_per_symbol
        esn0 = k * ebn0
        if self.M == 2:                                  # BPSK exacta
            return 0.5 * erfc(np.sqrt(ebn0))
        if self.M == 4:                                  # QPSK exacta (= BPSK)
            return 0.5 * erfc(np.sqrt(ebn0))
        if self.family == "psk":                         # M-PSK, aprox. Gray
            ser = erfc(np.sqrt(esn0) * np.sin(np.pi / self.M))
            return ser / k
        # M-QAM cuadrada: BER exacta para el termino dominante (Gray, por eje)
        m_sqrt = np.sqrt(self.M)
        c = 4 * (m_sqrt - 1) / (m_sqrt * k)
        return c * 0.5 * erfc(np.sqrt(1.5 * k * ebn0 / (self.M - 1)))

    def ser_theory(self, ebn0_db: np.ndarray) -> np.ndarray:
        """SER teorica en AWGN."""
        ebn0 = 10 ** (np.asarray(ebn0_db, dtype=float) / 10.0)
        k = self.bits_per_symbol
        esn0 = k * ebn0
        if self.M == 2:
            return 0.5 * erfc(np.sqrt(ebn0))
        if self.M == 4:
            q = 0.5 * erfc(np.sqrt(ebn0))
            return 2 * q - q ** 2                        # exacta para QPSK
        if self.family == "psk":
            return erfc(np.sqrt(esn0) * np.sin(np.pi / self.M))
        m_sqrt = np.sqrt(self.M)
        q = 0.5 * erfc(np.sqrt(1.5 * esn0 / (self.M - 1)))
        p = 2 * (1 - 1 / m_sqrt) * q
        return 2 * p - p ** 2                             # exacta para QAM cuadrada

    def __repr__(self) -> str:
        return f"Modulation({self.name.upper()}, M={self.M}, k={self.bits_per_symbol})"


def available() -> list[str]:
    return list(Modulation.SUPPORTED)

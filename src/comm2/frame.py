"""Generacion de bits y construccion de la trama.

Estructura de la rafaga (Requisito 4.2 de la guia):

    [ guarda ][ ZC | ZC ][ entrenamiento ][ carga util ][ guarda ]
               \_______/   \____________/  \__________/
              sincronismo   ecualizador       datos
              + CFO         (LMS/RLS)

* Las dos mitades identicas Zadoff-Chu permiten sincronizacion de trama y
  estimacion de offset de frecuencia por el metodo de Schmidl & Cox: la
  autocorrelacion con retardo L presenta una meseta cuya fase es
  proporcional al CFO.
* Zadoff-Chu se elige por su autocorrelacion periodica ideal (impulso) y
  envolvente constante (CAZAC), lo que da un pico de correlacion nitido
  incluso con canal multitrayectoria.
* La secuencia de entrenamiento es QPSK de modulo constante para que la
  adaptacion del ecualizador no dependa del nivel instantaneo de potencia.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .modulation import Modulation
from .params import SystemParams


def zadoff_chu(length: int, root: int = 25) -> np.ndarray:
    """Secuencia Zadoff-Chu de longitud `length` y raiz `root` (coprima)."""
    if np.gcd(root, length) != 1:
        raise ValueError("la raiz debe ser coprima con la longitud")
    n = np.arange(length)
    if length % 2 == 0:
        return np.exp(-1j * np.pi * root * n ** 2 / length)
    return np.exp(-1j * np.pi * root * n * (n + 1) / length)


def pn_qpsk(length: int, rng: np.random.Generator) -> np.ndarray:
    """Secuencia de entrenamiento QPSK pseudoaleatoria, |s| = 1."""
    bits = rng.integers(0, 2, size=2 * length).astype(np.uint8)
    return Modulation("qpsk").modulate(bits)


@dataclass
class Frame:
    """Contenedor con todo lo que el receptor necesita conocer/comparar."""

    symbols: np.ndarray          # trama completa en simbolos (sin guarda)
    preamble: np.ndarray         # [ZC ZC]
    training: np.ndarray         # simbolos de entrenamiento
    payload: np.ndarray          # simbolos de datos
    bits: np.ndarray             # bits de la carga util
    zc_len: int
    n_train: int
    n_payload: int
    mod: Modulation

    @property
    def preamble_len(self) -> int:
        return 2 * self.zc_len

    @property
    def train_start(self) -> int:
        return self.preamble_len

    @property
    def payload_start(self) -> int:
        return self.preamble_len + self.n_train


def build_frame(p: SystemParams, rng: np.random.Generator | None = None,
                mod_name: str | None = None) -> Frame:
    """Construye una trama completa segun los parametros del sistema."""
    rng = rng if rng is not None else p.rng()
    mod = Modulation(mod_name or p.mod)

    zc = zadoff_chu(p.zc_len)
    preamble = np.concatenate([zc, zc])                 # dos mitades identicas
    training = pn_qpsk(p.n_train, rng)

    bits = rng.integers(0, 2, size=p.n_payload * mod.bits_per_symbol).astype(np.uint8)
    payload = mod.modulate(bits)

    symbols = np.concatenate([preamble, training, payload])
    return Frame(symbols=symbols, preamble=preamble, training=training,
                 payload=payload, bits=bits, zc_len=p.zc_len,
                 n_train=p.n_train, n_payload=p.n_payload, mod=mod)


def add_guard(symbols: np.ndarray, guard: int) -> np.ndarray:
    """Agrega guarda de ceros para que los transitorios del filtro no
    contaminen el inicio/fin de la rafaga."""
    z = np.zeros(guard, dtype=complex)
    return np.concatenate([z, symbols, z])

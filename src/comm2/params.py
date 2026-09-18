"""Parametros del sistema y utilidades de configuracion.

Todo el proyecto trabaja en banda base compleja (equivalente pasabajos).
La frecuencia de muestreo `fs` es la del simulador; la tasa de simbolos es
Rs = fs / sps. No se simula portadora RF: los offsets de frecuencia se
aplican como rotacion del fasor complejo, que es exactamente el efecto que
una desviacion de portadora produce en la envolvente compleja.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional
import numpy as np


@dataclass
class SystemParams:
    """Especificacion completa del enlace (Requisito 4 de la guia)."""

    # --- Tasas y muestreo ---------------------------------------------------
    fs: float = 1.0e6           # Hz, frecuencia de muestreo del simulador
    sps: int = 8                # muestras por simbolo (oversampling)

    # --- Conformacion de pulso (RRC) ---------------------------------------
    beta: float = 0.35          # roll-off
    span: int = 10              # duracion del filtro en simbolos (a cada lado: span/2)

    # --- Modulacion ---------------------------------------------------------
    mod: str = "qpsk"           # 'bpsk' | 'qpsk' | '8psk' | '16qam' | '64qam'

    # --- Estructura de trama ------------------------------------------------
    zc_len: int = 64            # longitud de CADA mitad del preambulo Zadoff-Chu
    n_train: int = 512          # simbolos de entrenamiento para el ecualizador
    n_payload: int = 8192       # simbolos de datos utiles
    guard: int = 64             # simbolos de guarda (ceros) antes/despues de la rafaga

    # --- Semilla ------------------------------------------------------------
    seed: int = 2026

    # ------------------------------------------------------------------ util
    @property
    def rs(self) -> float:
        """Tasa de simbolos [baud]."""
        return self.fs / self.sps

    @property
    def bits_per_symbol(self) -> int:
        from .modulation import Modulation
        return Modulation(self.mod).bits_per_symbol

    @property
    def rb(self) -> float:
        """Tasa binaria bruta [bit/s]."""
        return self.rs * self.bits_per_symbol

    @property
    def bw(self) -> float:
        """Ancho de banda ocupado por el RRC: B = Rs (1 + beta) [Hz]."""
        return self.rs * (1.0 + self.beta)

    @property
    def spectral_efficiency(self) -> float:
        """Eficiencia espectral nominal [bit/s/Hz] = Rb / B = k / (1+beta)."""
        return self.rb / self.bw

    @property
    def n_frame_symbols(self) -> int:
        return 2 * self.zc_len + self.n_train + self.n_payload

    def rng(self, offset: int = 0) -> np.random.Generator:
        """Generador reproducible; `offset` permite realizaciones independientes."""
        return np.random.default_rng(self.seed + offset)

    def replace(self, **kw) -> "SystemParams":
        d = asdict(self)
        d.update(kw)
        return SystemParams(**d)

    def summary(self) -> str:
        return (
            f"fs={self.fs/1e6:.3f} MHz | sps={self.sps} | Rs={self.rs/1e3:.1f} kBd | "
            f"mod={self.mod.upper()} (k={self.bits_per_symbol}) | Rb={self.rb/1e3:.1f} kb/s | "
            f"beta={self.beta} | B={self.bw/1e3:.1f} kHz | eta={self.spectral_efficiency:.3f} b/s/Hz"
        )


@dataclass
class EqualizerConfig:
    """Configuracion del ecualizador adaptativo (Seccion 8 de la guia)."""

    kind: str = "lms"           # 'none' | 'lms' | 'rls' | 'zf' | 'mmse' | 'cma'
    n_taps: int = 21            # longitud del filtro FIR ecualizador
    ref_tap: Optional[int] = None   # posicion del tap de referencia (None -> centro)
    mu: float = 0.10            # paso de adaptacion (LMS normalizado / CMA)
    lam: float = 0.995          # factor de olvido (RLS)
    delta: float = 0.01         # inicializacion P = delta^-1 I (RLS)
    decision_directed: bool = True   # seguir adaptando sobre la carga util
    dd_mu_scale: float = 0.25   # reduccion del paso en modo dirigido por decision

    def resolved_ref_tap(self) -> int:
        return self.n_taps // 2 if self.ref_tap is None else self.ref_tap


@dataclass
class ReceiverConfig:
    """Que bloques del receptor se activan (permite ablaciones por experimento)."""

    matched_filter: bool = True
    timing_recovery: bool = True     # lazo de Gardner
    # Bn*T = 0.02 es el optimo medido (ver exp4): con lazos mas lentos la
    # adquisicion no termina antes de la secuencia de entrenamiento y queda un
    # error de temporizacion estatico que degrada la BER de forma uniforme;
    # con lazos mas rapidos domina el jitter de temporizacion.
    timing_loop_bw: float = 0.02     # ancho de banda normalizado del lazo de temporizacion
    cfo_correction: bool = True      # estimacion Schmidl-Cox sobre el preambulo
    # Etapa fina de CFO (ML sobre la secuencia de entrenamiento). Desactivada
    # por defecto: medida sobre el escenario C, el estimador grueso de
    # Schmidl-Cox deja un residuo de 2-5 Hz, mientras que el fino, calculado
    # ANTES de ecualizar, es arrastrado por los terminos cruzados de ISI y su
    # error tipico sube a 10-25 Hz. Con canal plano (escenario A) si conviene.
    fine_cfo: bool = False
    phase_pll: bool = True           # PLL dirigido por decision tras el ecualizador
    # Bn*T = 5e-4 es el optimo medido (ver experiments/exp4_robustez.py):
    #   Bn*T alto  -> deslizamientos de ciclo a Eb/N0 bajo, la BER se satura;
    #   Bn*T bajo  -> el lazo no sigue la rampa de fase que deja el error
    #                 residual del estimador grueso de frecuencia.
    phase_loop_bw: float = 5e-4
    eq: EqualizerConfig = field(default_factory=EqualizerConfig)

"""comm2 - Receptor digital adaptativo sobre canal inalambrico simulado.

Proyecto 1, Comunicaciones II 2026 (Prof. Dr. Ing. Carlos A. Medina C.).

Modulos
-------
params      Parametros del sistema, del receptor y del ecualizador.
modulation  Constelaciones Gray (BPSK/QPSK/8PSK/16-64QAM) y BER/SER teoricas.
pulse       Root Raised Cosine, filtro adaptado e interpoladores fraccionales.
frame       Preambulo Zadoff-Chu, entrenamiento y carga util.
channel     AWGN, multitrayectoria FIR, Rayleigh, CFO, fase y temporizacion.
sync        Schmidl-Cox, Gardner, sincronismo fino de trama y PLL de fase.
equalizers  LMS, RLS, ZF, MMSE y CMA con metricas de convergencia y coste.
metrics     BER/SER, EVM, MSE, PSD, diagrama de ojo, eficiencia espectral.
link        Cadena TX-canal-RX completa y simulaciones Monte Carlo.
scenarios   Escenarios A (AWGN), B (multipath) y C/D (degradado).
plots       Graficas normalizadas para el informe.
"""

from .params import SystemParams, ReceiverConfig, EqualizerConfig
from .modulation import Modulation
from .channel import ChannelConfig, MultipathProfile, PROFILES
from .link import run_link, monte_carlo, LinkResult
from . import scenarios, metrics, plots, sync, equalizers, pulse, frame, channel

__version__ = "1.0.0"

__all__ = [
    "SystemParams", "ReceiverConfig", "EqualizerConfig", "Modulation",
    "ChannelConfig", "MultipathProfile", "PROFILES", "run_link", "monte_carlo",
    "LinkResult", "scenarios", "metrics", "plots", "sync", "equalizers",
    "pulse", "frame", "channel",
]

"""Escenarios de canal A, B y C (Seccion 7 de la guia).

Los parametros se expresan en magnitudes normalizadas a la tasa de simbolo
para que sean independientes de fs, y se justifican en docs/parametros.md.
"""

from __future__ import annotations

import numpy as np

from .channel import ChannelConfig, PROFILES, get_profile
from .params import SystemParams


def scenario_a(p: SystemParams, ebn0_db: float = 10.0) -> ChannelConfig:
    """A - Canal de referencia: solo AWGN. Valida la cadena contra la teoria."""
    return ChannelConfig(name="A", profile=PROFILES["flat"], ebn0_db=ebn0_db)


def scenario_b(p: SystemParams, ebn0_db: float = 10.0,
               profile="moderate") -> ChannelConfig:
    """B - Multitrayectoria determinista + AWGN. Aisla el efecto de la ISI.

    profile : nombre de perfil predefinido, MultipathProfile o respuesta al
              impulso ('0,0.2,1,0,0.8' o secuencia), ver channel.get_profile.
    """
    return ChannelConfig(name="B", profile=get_profile(profile), ebn0_db=ebn0_db)


def scenario_c(p: SystemParams, ebn0_db: float = 10.0, profile="moderate",
               cfo_frac_rs: float = 0.003, phase_deg: float = 37.0,
               timing_frac: float = 0.37, clock_ppm: float = 20.0,
               rayleigh: bool = False, fd_frac_rs: float = 0.0) -> ChannelConfig:
    """C - Canal degradado: multitrayectoria + AWGN + CFO + fase + temporizacion.

    cfo_frac_rs : offset de frecuencia como fraccion de Rs. Debe quedar dentro
                  del rango de adquisicion de Schmidl-Cox, |f| < Rs/(2*zc_len).
    """
    return ChannelConfig(
        name="C", profile=get_profile(profile), ebn0_db=ebn0_db,
        cfo_hz=cfo_frac_rs * p.rs,
        phase_off_rad=np.radians(phase_deg),
        timing_frac=timing_frac, clock_ppm=clock_ppm,
        rayleigh=rayleigh, fd_hz=fd_frac_rs * p.rs,
    )


def scenario_d_fading(p: SystemParams, ebn0_db: float = 10.0,
                      profile="moderate", fd_frac_rs: float = 2e-4) -> ChannelConfig:
    """Variante de C con desvanecimiento Rayleigh variable en el tiempo.

    fD/Rs = 2e-4 corresponde, con Rs = 125 kBd, a fD = 25 Hz: un movil a
    ~13 km/h en 2.1 GHz. El canal es lento respecto a la trama (coherencia
    ~0.4/fD = 16 ms >> duracion de la rafaga), por lo que el ecualizador
    adaptativo puede seguirlo en modo dirigido por decision.
    """
    cfg = scenario_c(p, ebn0_db, profile, rayleigh=True, fd_frac_rs=fd_frac_rs)
    cfg.name = "D"
    return cfg


ALL = {
    "A": scenario_a,
    "B": scenario_b,
    "C": scenario_c,
    "D": scenario_d_fading,
}


def get(name: str, p: SystemParams, **kw) -> ChannelConfig:
    return ALL[name.upper()](p, **kw)

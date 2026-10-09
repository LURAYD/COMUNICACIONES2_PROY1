"""Configuración del enlace como JSON de variables para GNU Radio Companion.

El fichero es un diccionario plano: cada clave es el nombre de una variable de
GRC y su valor sale de los MISMOS objetos que usa la simulación (`engine.build`),
no de los deslizadores. Así lo exportado es lo que el canal aplica de verdad:
en el escenario A el offset de frecuencia vale 0 aunque el deslizador diga otra
cosa, porque ese escenario no lo aplica.

JSON no tiene números complejos: los vectores complejos van partidos en `_re` e
`_im`, y se recomponen en GRC con una línea (ver `GRC_SNIPPET`).

Equivalencias con los bloques de GNU Radio:
  - `noise_voltage` es la desviación típica del ruido complejo (potencia = v²),
    que es lo que espera el bloque Channel Model. Vale √σ² con
    σ² = 1/(k·Eb/N0), correcto porque `rrc_taps` va normalizado en energía.
  - `freq_offset_norm` está en ciclos por muestra (CFO / samp_rate), la unidad
    del campo «Frequency Offset» del Channel Model.
  - `epsilon` es la razón de reloj del Channel Model: 1 + ppm·10⁻⁶.
"""

from __future__ import annotations

import json
from datetime import datetime

import numpy as np

from .engine import Request, build

GRC_SNIPPET = """\
Bloque Import:     import json, cmath
Variable  cfg:     json.load(open(r"{path}", encoding="utf-8"))
Variable  samp_rate:   cfg["samp_rate"]
Variable  sps:         cfg["sps"]
Variable  rrc_taps:    cfg["rrc_taps"]
Variable  chan_taps:   [complex(a, b) for a, b in zip(cfg["channel_taps_re"], cfg["channel_taps_im"])]
Variable  constel:     [complex(a, b) for a, b in zip(cfg["constellation_re"], cfg["constellation_im"])]
Variable  noise_v:     cfg["noise_voltage"]
Variable  f_off:       cfg["freq_offset_norm"]
Variable  epsilon:     cfg["epsilon"]
Variable  giro:        cmath.exp(1j * cfg["phase_offset_rad"])

Interp FIR Filter: Interpolation = sps · Taps = rrc_taps
Multiply Const:    Constant = giro     (fase fija: el Channel Model no la tiene)
Channel Model:     Noise Voltage = noise_v · Frequency Offset = f_off
                   Epsilon = epsilon · Taps = chan_taps

No se reproducen con estos bloques (lista "_no_reproducible" del JSON): el
retardo fraccional fijo (timing_offset_samples) y el Rayleigh (rayleigh,
doppler_hz). El Channel Model retrasa además 3 muestras respecto a Python.
Para comparar señales y receptores hace falta la corrida completa:
    .venv\\Scripts\\python grc\\validar_gnuradio.py este_fichero.json
"""


def _f(x) -> float:
    return round(float(x), 10)


def _vec(v) -> list[float]:
    return [_f(a) for a in np.asarray(v, dtype=float)]


def build_config(req: Request) -> dict:
    """Las variables del enlace, con nombres válidos como identificadores de GRC."""
    from comm2.channel import noise_sigma2
    from comm2.modulation import Modulation
    from comm2.pulse import rrc_filter

    p, chan, rx = build(req)
    mod = Modulation(req.mod)
    k = mod.bits_per_symbol
    rrc = rrc_filter(p.beta, p.span, p.sps)
    taps = np.asarray(chan.profile.taps(p.sps), dtype=complex)
    sigma2 = noise_sigma2(chan.ebn0_db, k)
    c = np.asarray(mod.constellation, dtype=complex)
    eq = rx.eq

    return {
        "_descripcion": "Configuración del enlace (Comunicaciones II 2026). "
                        "Cada clave es una variable de GNU Radio Companion.",
        "_generado": datetime.now().isoformat(timespec="seconds"),

        # -- generación de onda --------------------------------------------
        "samp_rate": _f(p.fs),
        "sps": int(p.sps),
        "symbol_rate": _f(p.rs),
        "bit_rate": _f(p.rb),
        "bandwidth": _f(p.bw),
        "modulation": req.mod,
        "bits_per_symbol": int(k),
        "constellation_re": _vec(c.real),
        "constellation_im": _vec(c.imag),
        "rrc_beta": _f(p.beta),
        "rrc_span": int(p.span),
        "rrc_ntaps": int(rrc.size),
        "rrc_taps": _vec(rrc),
        "zc_len": int(p.zc_len),
        "n_train": int(p.n_train),
        "n_payload": int(p.n_payload),
        "guard": int(p.guard),

        # -- canal ----------------------------------------------------------
        "scenario": chan.name,
        "channel_profile": req.profile if req.scenario.upper() != "A" else "flat",
        "channel_taps_re": _vec(taps.real),
        "channel_taps_im": _vec(taps.imag),
        "ebn0_db": _f(chan.ebn0_db),
        "esn0_db": _f(chan.ebn0_db + 10 * np.log10(k)),
        "noise_sigma2": _f(sigma2),
        "noise_voltage": _f(np.sqrt(sigma2)),
        "freq_offset_hz": _f(chan.cfo_hz),
        "freq_offset_norm": _f(chan.cfo_hz / p.fs),
        "phase_offset_rad": _f(chan.phase_off_rad),
        "phase_offset_deg": _f(np.degrees(chan.phase_off_rad)),
        "timing_offset_samples": _f(chan.timing_frac),
        "clock_ppm": _f(chan.clock_ppm),
        "epsilon": _f(1.0 + chan.clock_ppm * 1e-6),
        "rayleigh": bool(chan.rayleigh),
        "doppler_hz": _f(chan.fd_hz),
        # Lo que el Channel Model de GNU Radio no puede aplicar: quien lo use
        # debe saber que en estos puntos su canal NO es el de Python.
        "_no_reproducible": [n for n, activo in (
            ("timing_offset_samples", bool(chan.timing_frac)),
            ("rayleigh", bool(chan.rayleigh))) if activo],

        # -- receptor -------------------------------------------------------
        "equalizer": eq.kind,
        "eq_ntaps": int(eq.n_taps),
        "eq_mu": _f(eq.mu),
        "eq_lambda": _f(eq.lam),
        "matched_filter": bool(rx.matched_filter),
        "timing_recovery": bool(rx.timing_recovery),
        "cfo_correction": bool(rx.cfo_correction),
        "phase_pll": bool(rx.phase_pll),
    }


def dumps(req: Request) -> str:
    """Una variable por línea, vectores incluidos: se lee como la lista de GRC."""
    lines = [f"  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}"
             for k, v in build_config(req).items()]
    return "{\n" + ",\n".join(lines) + "\n}\n"

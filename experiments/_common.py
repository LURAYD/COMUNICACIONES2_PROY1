"""Utilidades compartidas por los scripts de experimentos.

Cada experimento escribe:
  results/data/<nombre>.csv     tabla reproducible con todos los numeros
  results/figures/<nombre>*.png figuras listas para el informe
"""

from __future__ import annotations

from pathlib import Path
import time
import numpy as np
import pandas as pd

from comm2 import (SystemParams, ReceiverConfig, EqualizerConfig, scenarios,
                   run_link, monte_carlo, plots)
from comm2.modulation import Modulation

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results" / "data"
FIGS = ROOT / "results" / "figures"
DATA.mkdir(parents=True, exist_ok=True)
FIGS.mkdir(parents=True, exist_ok=True)

# Parametros base del enlace, comunes a todos los experimentos.
BASE = SystemParams(
    fs=1.0e6, sps=8, beta=0.35, span=10,
    mod="qpsk", zc_len=64, n_train=512, n_payload=20000, guard=64, seed=2026,
)

# Metodo A y metodo B de la seccion 8 de la guia.
METHOD_A = EqualizerConfig(kind="lms", n_taps=21, mu=0.50, dd_mu_scale=0.25)
METHOD_B = EqualizerConfig(kind="rls", n_taps=21, lam=0.999, delta=0.01,
                           dd_mu_scale=1.0)
NO_EQ = EqualizerConfig(kind="none")

EQ_LABELS = {
    "none": "Sin ecualizar", "lms": "LMS (metodo A)", "rls": "RLS (metodo B)",
    "zf": "Zero-Forcing (canal conocido)", "mmse": "MMSE (canal conocido)",
    "cma": "CMA (ciego)",
}


def eq_config(kind: str, **kw) -> EqualizerConfig:
    """Configuracion por defecto de cada ecualizador, con sobrescritura."""
    base = {
        "none": dict(kind="none"),
        # mu = 0.5 (LMS normalizado) es el valor medido optimo: con mu = 0.15 la
        # BER a 14 dB era 2.2e-3 y con 0.5 baja a 4.2e-5, al nivel del RLS.
        "lms": dict(kind="lms", n_taps=21, mu=0.50, dd_mu_scale=0.25),
        "rls": dict(kind="rls", n_taps=21, lam=0.999, delta=0.01, dd_mu_scale=1.0),
        "zf": dict(kind="zf", n_taps=21),
        "mmse": dict(kind="mmse", n_taps=21),
        "cma": dict(kind="cma", n_taps=21, mu=0.02),
    }[kind]
    base.update(kw)
    return EqualizerConfig(**base)


def frames_for(ebn0_db: float, base: int = 2) -> int:
    """Mas realizaciones a Eb/N0 alto para que la BER medida tenga sentido.

    Se busca acumular del orden de 100 errores; por debajo de ~20 errores la
    estimacion tiene un intervalo de confianza demasiado ancho para graficarse.
    """
    if ebn0_db <= 6:
        return base
    if ebn0_db <= 10:
        return base * 2
    if ebn0_db <= 14:
        return base * 4
    return base * 8


def sweep_ebn0(p: SystemParams, scenario: str, eq_kind: str, ebn0_list,
               rxcfg_kw: dict | None = None, eq_kw: dict | None = None,
               scen_kw: dict | None = None, base_frames: int = 2,
               label: str = "") -> pd.DataFrame:
    """Barrido de Eb/N0 devolviendo un DataFrame con todas las metricas."""
    rows = []
    for eb in ebn0_list:
        rx = ReceiverConfig(eq=eq_config(eq_kind, **(eq_kw or {})),
                            **(rxcfg_kw or {}))
        nf = frames_for(eb, base_frames)
        t0 = time.time()
        out = monte_carlo(
            p, lambda i, eb=eb: scenarios.get(scenario, p, ebn0_db=eb,
                                              **(scen_kw or {})),
            rx, n_frames=nf)
        rows.append({
            "escenario": scenario, "eq": eq_kind, "etiqueta": label or EQ_LABELS[eq_kind],
            "mod": p.mod, "ebn0_db": eb, "ber": out["ber"], "ser": out["ser"],
            "ber_errors": out["ber_errors"], "ber_bits": out["ber_bits"],
            "ber_ci_lo": out["ber_ci_lo"], "ber_ci_hi": out["ber_ci_hi"],
            "mse": out["mse"], "evm_pct": out["evm_pct"],
            "eq_mse_db": out["eq_mse_db"], "eq_conv": out["eq_conv"],
            "corr_sync": out["fine_corr"], "n_frames": nf,
            "t_s": round(time.time() - t0, 2),
        })
        print(f"    Eb/N0={eb:5.1f} dB  {eq_kind:5s}  BER={out['ber']:.3e} "
              f"({out['ber_errors']:5d}/{out['ber_bits']}) EVM={out['evm_pct']:5.1f}% "
              f"[{rows[-1]['t_s']:.1f}s]")
    return pd.DataFrame(rows)


def save_table(df: pd.DataFrame, name: str) -> Path:
    path = DATA / f"{name}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    try:
        mostrado = path.relative_to(ROOT)
    except ValueError:          # DATA redirigido fuera del proyecto (pruebas)
        mostrado = path
    print(f"  -> {mostrado}")
    return path


def banner(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def theory_curve(mod_name: str, ebn0):
    return Modulation(mod_name).ber_theory(np.asarray(ebn0, dtype=float))

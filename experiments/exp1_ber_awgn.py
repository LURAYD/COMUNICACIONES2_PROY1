"""Experimento 1 - BER teorica y simulada en canal AWGN (Escenario A).

Objetivo: validar la cadena completa contra la teoria antes de introducir
cualquier degradacion. Si la curva simulada no cae sobre la teorica, cualquier
conclusion posterior sobre ecualizacion carece de valor.

Se comparan BER y SER medidas con las expresiones analiticas:
    QPSK / BPSK : Pb = (1/2) erfc( sqrt(Eb/N0) )                     [exacta]
    M-PSK       : Ps ~ erfc( sqrt(k Eb/N0) sin(pi/M) ),  Pb ~ Ps/k    [Gray]
    M-QAM       : Pb ~ 4(sqrt(M)-1)/(sqrt(M) k) * (1/2) erfc( sqrt(1.5 k Eb/N0/(M-1)) )

El receptor opera con TODOS sus bloques activos (sincronizacion de trama,
correccion de frecuencia, lazo de Gardner y PLL de fase) para que la perdida de
implementacion medida sea la real, no la de un receptor idealizado.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from _common import (BASE, banner, plots, save_table, sweep_ebn0,
                     theory_curve)
from comm2.modulation import Modulation

EBN0 = np.arange(0, 13, 2.0)
MODS = ["qpsk", "16qam"]          # QPSK + segunda modulacion (Requisito 4.4)


def main() -> pd.DataFrame:
    banner("EXPERIMENTO 1 - BER teorica vs simulada, canal AWGN (Escenario A)")
    plots.setup()
    frames = []
    for m in MODS:
        p = BASE.replace(mod=m)
        print(f"\n  {p.summary()}")
        df = sweep_ebn0(p, "A", "none", EBN0, base_frames=4)
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    save_table(df, "exp1_ber_awgn")

    # ------------------------------------------------------------------ figura
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2))

    ax = axes[0]
    for m, color in zip(MODS, ["#1f77b4", "#d62728"]):
        sub = df[df["mod"] == m]
        mod = Modulation(m)
        eb = sub["ebn0_db"].to_numpy()
        ax.semilogy(eb, mod.ber_theory(eb), "--", color=color, lw=1.1,
                    label=f"{m.upper()} teorica")
        ax.semilogy(eb, np.where(sub["ber"] <= 0, np.nan, sub["ber"]), "o-",
                    color=color, label=f"{m.upper()} simulada")
        ax.fill_between(eb, np.maximum(sub["ber_ci_lo"], 1e-12), sub["ber_ci_hi"],
                        color=color, alpha=0.15, lw=0)
    ax.set_xlabel("$E_b/N_0$ [dB]"); ax.set_ylabel("BER")
    ax.set_ylim(1e-6, 1); ax.grid(True, which="both", alpha=0.3)
    ax.set_title("BER: teorica vs simulada")
    ax.legend(fontsize=7)

    ax = axes[1]
    for m, color in zip(MODS, ["#1f77b4", "#d62728"]):
        sub = df[df["mod"] == m]
        mod = Modulation(m)
        eb = sub["ebn0_db"].to_numpy()
        ax.semilogy(eb, mod.ser_theory(eb), "--", color=color, lw=1.1,
                    label=f"{m.upper()} teorica")
        ax.semilogy(eb, np.where(sub["ser"] <= 0, np.nan, sub["ser"]), "s-",
                    color=color, label=f"{m.upper()} simulada")
    ax.set_xlabel("$E_b/N_0$ [dB]"); ax.set_ylabel("SER")
    ax.set_ylim(1e-6, 1); ax.grid(True, which="both", alpha=0.3)
    ax.set_title("SER: teorica vs simulada")
    ax.legend(fontsize=7)

    fig.suptitle("Experimento 1 - Validacion en canal AWGN (Escenario A)", y=1.02)
    plots.save_fig(fig, "exp1_ber_awgn")

    # ------------------------------------------- perdida de implementacion
    rows = []
    for m in MODS:
        sub = df[df["mod"] == m]
        eb = sub["ebn0_db"].to_numpy()
        sim = sub["ber"].to_numpy()
        teo = theory_curve(m, eb)
        for e, s, t in zip(eb, sim, teo):
            if s > 0 and t > 0:
                # dB de Eb/N0 adicionales necesarios para igualar la teoria
                rows.append({"mod": m, "ebn0_db": e, "ber_sim": s, "ber_teo": t,
                             "razon": s / t})
    loss = pd.DataFrame(rows)
    save_table(loss, "exp1_perdida_implementacion")
    print("\n  Razon BER simulada/teorica (perdida de implementacion):")
    for m in MODS:
        r = loss[loss["mod"] == m]["razon"]
        print(f"    {m.upper():6s} mediana={r.median():.2f}  max={r.max():.2f}")
    return df


if __name__ == "__main__":
    main()

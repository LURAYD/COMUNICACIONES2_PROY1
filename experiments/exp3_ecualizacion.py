"""Experimento 3 - Ecualizacion: sin ecualizar vs metodo A (LMS) vs metodo B (RLS).

Es el experimento central del proyecto. Se comparan los cinco criterios que
exige la seccion 8 de la guia:

    BER  |  velocidad de convergencia  |  error residual  |
    sensibilidad al SNR  |  complejidad computacional

Se incluyen ademas, como cotas de referencia, los ecualizadores ZF y MMSE
calculados a partir del canal *conocido* (que un receptor real no tiene) y el
CMA ciego, que no consume secuencia de entrenamiento.

Complejidad: se cuentan multiplicaciones reales por simbolo (1 producto
complejo = 4 reales).
    LMS : filtrado N + actualizacion N  -> 8N        O(N)
    RLS : ganancia de Kalman y update P -> 16N^2+16N O(N^2)
    ZF/MMSE (coeficientes fijos)        -> 4N        O(N) en operacion,
                                            pero requieren estimar e invertir
                                            el canal fuera de linea.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from _common import (BASE, EQ_LABELS, banner, eq_config, plots, save_table,
                     sweep_ebn0)
from comm2 import ReceiverConfig, run_link, scenarios
from comm2.equalizers import flop_count

EBN0 = np.arange(4, 21, 2.0)
METODOS = ["none", "lms", "rls", "zf", "mmse", "cma"]
ESCENARIO = "B"          # multitrayectoria + AWGN: aisla el efecto de la ISI
EBN0_DETALLE = 14.0      # punto de trabajo para curvas de aprendizaje


def main() -> pd.DataFrame:
    banner("EXPERIMENTO 3 - Comparacion de estrategias de ecualizacion")
    plots.setup()
    p = BASE
    print(f"  {p.summary()}")
    print(f"  Escenario {ESCENARIO}: {scenarios.get(ESCENARIO, p).describe(p.sps, p.fs)}\n")

    # ------------------------------------------------------- barrido de BER
    frames = []
    for kind in METODOS:
        print(f"  --- {EQ_LABELS[kind]} ---")
        frames.append(sweep_ebn0(p, ESCENARIO, kind, EBN0, base_frames=2))
    df = pd.concat(frames, ignore_index=True)
    save_table(df, "exp3_ber_ecualizadores")

    # ------------------------------- curvas de aprendizaje y taps (un punto)
    detalle, curvas = [], {}
    for kind in METODOS:
        rx = ReceiverConfig(eq=eq_config(kind))
        r = run_link(p, scenarios.get(ESCENARIO, p, ebn0_db=EBN0_DETALLE), rx)
        curvas[kind] = r
        fl = flop_count(kind, r.eq.n_taps)
        detalle.append({
            "metodo": kind, "etiqueta": EQ_LABELS[kind], "n_taps": r.eq.n_taps,
            "ber": r.stats["ber"], "evm_pct": r.stats["evm_pct"],
            "mse_residual_db": r.eq.steady_mse_db,
            "conv_propia": r.eq.convergence_symbols,
            "conv_a_-6dB": r.eq.time_to_reach(-6.0),
            "conv_a_-12dB": r.eq.time_to_reach(-12.0),
            "conv_a_-9dB": r.eq.time_to_reach(-9.0),
            "mult_reales_por_simbolo": fl["real_mults"], "orden": fl["order"],
        })
        print(f"  {kind:5s} BER={r.stats['ber']:.3e}  MSEres={r.eq.steady_mse_db:6.2f} dB  "
              f"conv(-6dB)={r.eq.time_to_reach(-6.0):5d}  "
              f"conv(-9dB)={r.eq.time_to_reach(-9.0):5d}  "
              f"{fl['real_mults']:6d} mult/simb ({fl['order']})")
    det = pd.DataFrame(detalle)
    save_table(det, "exp3_comparacion_detallada")

    # ------------------------- sensibilidad del LMS a mu y del RLS a lambda
    sens = []
    for mu in (0.02, 0.05, 0.1, 0.2, 0.5, 1.0):
        rx = ReceiverConfig(eq=eq_config("lms", mu=mu))
        r = run_link(p, scenarios.get(ESCENARIO, p, ebn0_db=EBN0_DETALLE), rx)
        sens.append({"metodo": "lms", "parametro": "mu", "valor": mu,
                     "ber": r.stats["ber"], "mse_residual_db": r.eq.steady_mse_db,
                     "conv_a_-6dB": r.eq.time_to_reach(-6.0)})
    for lam in (0.95, 0.98, 0.99, 0.995, 0.999, 1.0):
        rx = ReceiverConfig(eq=eq_config("rls", lam=lam))
        r = run_link(p, scenarios.get(ESCENARIO, p, ebn0_db=EBN0_DETALLE), rx)
        sens.append({"metodo": "rls", "parametro": "lambda", "valor": lam,
                     "ber": r.stats["ber"], "mse_residual_db": r.eq.steady_mse_db,
                     "conv_a_-6dB": r.eq.time_to_reach(-6.0)})
    sdf = pd.DataFrame(sens)
    save_table(sdf, "exp3_sensibilidad_parametros")
    print("\n  Compromiso velocidad / error residual:")
    for _, row in sdf.iterrows():
        print(f"    {row['metodo']:4s} {row['parametro']:6s}={row['valor']:<6} "
              f"conv={row['conv_a_-6dB']:5.0f}  MSEres={row['mse_residual_db']:6.2f} dB  "
              f"BER={row['ber']:.2e}")

    # =================================================================== figuras
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4), constrained_layout=True)

    ax = axes[0]
    for kind in METODOS:
        sub = df[df["eq"] == kind]
        ax.semilogy(sub["ebn0_db"], np.where(sub["ber"] <= 0, np.nan, sub["ber"]),
                    "o-", color=plots.COLORS[kind], label=EQ_LABELS[kind], ms=3.5)
    from comm2.modulation import Modulation
    ax.semilogy(EBN0, Modulation(p.mod).ber_theory(EBN0), "k--", lw=1.1,
                label="AWGN teorica (cota)")
    ax.set_xlabel("$E_b/N_0$ [dB]"); ax.set_ylabel("BER")
    ax.set_ylim(1e-6, 1); ax.grid(True, which="both", alpha=0.3)
    ax.set_title(f"BER vs $E_b/N_0$ - Escenario {ESCENARIO}")
    ax.legend(fontsize=7)

    ax = axes[1]
    for kind in ("none", "lms", "rls", "cma"):
        plots.learning_curve(ax, curvas[kind].eq, EQ_LABELS[kind],
                             color=plots.COLORS[kind])
    ax.axvline(p.n_train, color="0.4", ls="--", lw=1)
    ax.text(p.n_train * 1.05, ax.get_ylim()[1] - 2, "fin del entrenamiento\n(paso a modo DD)",
            fontsize=7, va="top")
    ax.set_xlim(0, 3000); ax.set_ylim(-16, 12)
    ax.set_title(f"Curvas de aprendizaje ($E_b/N_0$ = {EBN0_DETALLE:.0f} dB)")
    ax.legend(fontsize=7)
    fig.suptitle("Experimento 3 - Ecualizacion: desempeno y convergencia")
    plots.save_fig(fig, "exp3_ecualizacion")

    # ------------------------------------------- taps y compromiso parametrico
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 3.8), constrained_layout=True)

    ax = axes[0]
    for kind, m in (("lms", "o"), ("rls", "s"), ("mmse", "^")):
        w = curvas[kind].eq.w
        ax.plot(np.arange(w.size), np.abs(w) / np.max(np.abs(w)), m + "-",
                color=plots.COLORS[kind], label=EQ_LABELS[kind], ms=3.5)
    ax.set_xlabel("Indice de tap"); ax.set_ylabel("$|w|$ normalizado")
    ax.set_title("Coeficientes finales del ecualizador"); ax.legend(fontsize=7)

    ax = axes[1]
    for met, color in (("lms", plots.COLORS["lms"]), ("rls", plots.COLORS["rls"])):
        sub = sdf[sdf["metodo"] == met]
        ax.plot(sub["conv_a_-6dB"], sub["mse_residual_db"], "o-", color=color,
                label=EQ_LABELS[met])
        for _, row in sub.iterrows():
            ax.annotate(f"{row['valor']:g}", (row["conv_a_-6dB"], row["mse_residual_db"]),
                        fontsize=6, xytext=(3, 3), textcoords="offset points")
    ax.set_xlabel("Simbolos hasta MSE = -6 dB"); ax.set_ylabel("MSE residual [dB]")
    ax.set_title("Compromiso velocidad / error residual"); ax.legend(fontsize=7)

    ax = axes[2]
    taps = np.arange(5, 42, 2)
    ax.semilogy(taps, [flop_count("lms", n)["real_mults"] for n in taps], "o-",
                color=plots.COLORS["lms"], label="LMS  $O(N)$", ms=3.5)
    ax.semilogy(taps, [flop_count("rls", n)["real_mults"] for n in taps], "s-",
                color=plots.COLORS["rls"], label="RLS  $O(N^2)$", ms=3.5)
    ax.semilogy(taps, [flop_count("mmse", n)["real_mults"] for n in taps], "^-",
                color=plots.COLORS["mmse"], label="ZF/MMSE (fijos)", ms=3.5)
    ax.set_xlabel("Numero de taps $N$"); ax.set_ylabel("Mult. reales por simbolo")
    ax.set_title("Complejidad computacional"); ax.legend(fontsize=7)
    ax.grid(True, which="both", alpha=0.3)

    fig.suptitle("Experimento 3 - Coeficientes, compromiso parametrico y coste")
    plots.save_fig(fig, "exp3_taps_complejidad")

    # ---------------------------------------------- constelaciones comparadas
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.6), constrained_layout=True)
    for ax, kind in zip(axes, ("none", "lms", "rls", "mmse")):
        r = curvas[kind]
        plots.constellation(ax, r.payload_rx, f"{EQ_LABELS[kind]}\nBER={r.stats['ber']:.2e}",
                            mod=r.frame.mod, color=plots.COLORS[kind])
    fig.suptitle(f"Experimento 3 - Constelacion recibida ($E_b/N_0$ = {EBN0_DETALLE:.0f} dB, escenario {ESCENARIO})")
    plots.save_fig(fig, "exp3_constelaciones")
    return df


if __name__ == "__main__":
    main()

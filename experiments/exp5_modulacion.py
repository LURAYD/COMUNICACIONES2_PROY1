"""Experimento 5 - Comparacion de modulaciones.

QPSK (obligatoria) frente a la segunda modulacion elegida, 16-QAM, con 8PSK y
64-QAM como referencias adicionales. Se contrastan:

  * BER y SER frente a Eb/N0 en el escenario A (AWGN) y en el C (degradado);
  * eficiencia espectral eta = k / (1 + beta) [bit/s/Hz];
  * Eb/N0 necesario para alcanzar BER = 1e-3 -> curva "coste en potencia" vs
    "beneficio en eficiencia espectral", que es el compromiso real de diseno;
  * constelaciones y PSD (identica para todas: la ocupacion espectral la fija
    el RRC, no el orden de la modulacion).

Eleccion de 16-QAM como segunda modulacion: frente a 8PSK gana 0.74 bit/s/Hz de
eficiencia espectral con una penalizacion de Eb/N0 similar, y su sensibilidad a
errores de ganancia/fase la hace un caso mas exigente -- y por tanto mas
informativo -- para evaluar el receptor adaptativo.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from _common import (BASE, banner, eq_config, plots, save_table, sweep_ebn0)
from comm2 import ReceiverConfig, run_link, scenarios, metrics
from comm2.modulation import Modulation

MODS = ["qpsk", "8psk", "16qam", "64qam"]
COLORS = {"qpsk": "#1f77b4", "8psk": "#2ca02c", "16qam": "#d62728", "64qam": "#9467bd"}
EBN0 = np.arange(2, 25, 2.0)
BER_OBJETIVO = 1e-3


def ebn0_para_ber(eb: np.ndarray, ber: np.ndarray, objetivo: float) -> float:
    """Interpola en escala log el Eb/N0 que alcanza la BER objetivo."""
    eb = np.asarray(eb, float)
    ber = np.asarray(ber, float)
    ok = np.isfinite(ber) & (ber > 0)
    eb, ber = eb[ok], np.log10(ber[ok])
    tgt = np.log10(objetivo)
    for i in range(len(eb) - 1):
        if (ber[i] - tgt) * (ber[i + 1] - tgt) <= 0:
            f = (tgt - ber[i]) / (ber[i + 1] - ber[i] + 1e-15)
            return float(eb[i] + f * (eb[i + 1] - eb[i]))
    return float("nan")


def main() -> pd.DataFrame:
    banner("EXPERIMENTO 5 - QPSK vs segunda modulacion")
    plots.setup()

    frames = []
    for esc, kind in (("A", "none"), ("C", "rls")):
        for m in MODS:
            p = BASE.replace(mod=m)
            print(f"\n  Escenario {esc} | {p.summary()}")
            frames.append(sweep_ebn0(p, esc, kind, EBN0, base_frames=1))
    df = pd.concat(frames, ignore_index=True)
    save_table(df, "exp5_modulaciones")

    # ------------------------------------ resumen: potencia vs eficiencia
    rows = []
    for esc in ("A", "C"):
        for m in MODS:
            sub = df[(df["mod"] == m) & (df["escenario"] == esc)]
            mod = Modulation(m)
            eb_req = ebn0_para_ber(sub["ebn0_db"], sub["ber"], BER_OBJETIVO)
            eb_teo = ebn0_para_ber(np.linspace(0, 30, 601),
                                   mod.ber_theory(np.linspace(0, 30, 601)),
                                   BER_OBJETIVO)
            rows.append({
                "escenario": esc, "mod": m, "k": mod.bits_per_symbol,
                "eta_bps_hz": metrics.spectral_efficiency(mod.bits_per_symbol, BASE.beta),
                "ebn0_req_db": eb_req, "ebn0_teo_db": eb_teo,
                "penalizacion_db": eb_req - eb_teo,
            })
    res = pd.DataFrame(rows)
    save_table(res, "exp5_potencia_vs_eficiencia")
    print(f"\n  Eb/N0 necesario para BER = {BER_OBJETIVO:g}:")
    for _, r in res.iterrows():
        print(f"    [{r['escenario']}] {r['mod'].upper():6s} k={r['k']}  "
              f"eta={r['eta_bps_hz']:.2f} b/s/Hz  "
              f"Eb/N0={r['ebn0_req_db']:5.1f} dB (teorico {r['ebn0_teo_db']:5.1f}, "
              f"penalizacion {r['penalizacion_db']:+4.1f} dB)")

    # ------------------------------------------------------ constelaciones
    ejemplos = {}
    for m in MODS:
        p = BASE.replace(mod=m)
        eb = {"qpsk": 12.0, "8psk": 14.0, "16qam": 16.0, "64qam": 22.0}[m]
        rx = ReceiverConfig(eq=eq_config("rls"))
        ejemplos[m] = (run_link(p, scenarios.scenario_c(p, eb), rx), eb)

    # ================================================================ figuras
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2), constrained_layout=True)

    for ax, esc, titulo in zip(axes[:2], ("A", "C"),
                               ("Escenario A (AWGN, sin ecualizar)",
                                "Escenario C (degradado, RLS)")):
        for m in MODS:
            sub = df[(df["mod"] == m) & (df["escenario"] == esc)]
            ax.semilogy(sub["ebn0_db"], np.where(sub["ber"] <= 0, np.nan, sub["ber"]),
                        "o-", color=COLORS[m], ms=3.5, label=f"{m.upper()} simulada")
            ax.semilogy(EBN0, Modulation(m).ber_theory(EBN0), "--", color=COLORS[m],
                        lw=0.9, alpha=0.6)
        ax.axhline(BER_OBJETIVO, color="0.4", ls=":", lw=1)
        ax.set_xlabel("$E_b/N_0$ [dB]"); ax.set_ylabel("BER")
        ax.set_ylim(1e-6, 1); ax.grid(True, which="both", alpha=0.3)
        ax.set_title(titulo); ax.legend(fontsize=6)

    ax = axes[2]
    for esc, marker in (("A", "o"), ("C", "s")):
        sub = res[res["escenario"] == esc]
        ax.plot(sub["ebn0_req_db"], sub["eta_bps_hz"], marker + "-",
                label=f"Escenario {esc}")
        for _, r in sub.iterrows():
            ax.annotate(r["mod"].upper(), (r["ebn0_req_db"], r["eta_bps_hz"]),
                        fontsize=7, xytext=(4, -2), textcoords="offset points")
    snr = np.linspace(0, 30, 200)
    ax.plot(snr, [metrics.shannon_limit(s) for s in snr], "k--", lw=1,
            alpha=0.5, label="limite de Shannon")
    ax.set_xlim(0, 26); ax.set_ylim(0, 6)
    ax.set_xlabel(f"$E_b/N_0$ para BER = {BER_OBJETIVO:g} [dB]")
    ax.set_ylabel(r"Eficiencia espectral $\eta$ [bit/s/Hz]")
    ax.set_title("Compromiso potencia / eficiencia espectral"); ax.legend(fontsize=7)

    fig.suptitle("Experimento 5 - QPSK frente a modulaciones de orden superior")
    plots.save_fig(fig, "exp5_modulaciones")

    fig, axes = plt.subplots(1, 4, figsize=(14, 3.6), constrained_layout=True)
    for ax, m in zip(axes, MODS):
        r, eb = ejemplos[m]
        plots.constellation(ax, r.payload_rx,
                            f"{m.upper()} - $E_b/N_0$={eb:.0f} dB\nBER={r.stats['ber']:.2e}"
                            f"  EVM={r.stats['evm_pct']:.1f}%",
                            mod=r.frame.mod, color=COLORS[m], alpha=0.15)
    fig.suptitle("Experimento 5 - Constelaciones tras ecualizacion RLS (escenario C)")
    plots.save_fig(fig, "exp5_constelaciones")

    # PSD: misma ocupacion para todas las modulaciones
    fig, ax = plt.subplots(figsize=(6, 3.8), constrained_layout=True)
    for m in MODS:
        r, _ = ejemplos[m]
        plots.psd(ax, r.tx_signal, BASE.fs, f"{m.upper()}  "
                  f"$\\eta$={metrics.spectral_efficiency(Modulation(m).bits_per_symbol, BASE.beta):.2f}",
                  color=COLORS[m])
    ax.axvline(BASE.rs * (1 + BASE.beta) / 2 / 1e3, color="r", ls=":", lw=1)
    ax.axvline(-BASE.rs * (1 + BASE.beta) / 2 / 1e3, color="r", ls=":", lw=1)
    ax.set_xlim(-300, 300); ax.legend(fontsize=7)
    ax.set_title("PSD transmitida: la ocupacion la fija el RRC,\nno el orden de la modulacion")
    plots.save_fig(fig, "exp5_psd")
    return df


if __name__ == "__main__":
    main()

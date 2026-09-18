"""Experimento 4 - Robustez del receptor.

Barridos exigidos por la guia (Eb/N0, nivel de multitrayectoria, errores de
fase/frecuencia) mas los barridos de diseno que sustentan la eleccion de
parametros del receptor:

  4.1  BER vs Eb/N0 en los escenarios A, B y C.
  4.2  BER vs severidad del canal (dispersion de retardo).
  4.3  BER vs offset de frecuencia -> limite de adquisicion de Schmidl-Cox.
  4.4  BER vs offset de fase y vs error de temporizacion.
  4.5  BER vs numero de taps del ecualizador y longitud del entrenamiento.
  4.6  BER vs ancho de banda de los lazos (temporizacion y fase).
  4.7  Escenario D: desvanecimiento Rayleigh -> papel del factor de olvido.

El punto 4.7 es el unico donde lambda del RLS importa de verdad: en un canal
estatico la velocidad de convergencia del RLS es ~2N iteraciones sea cual sea
lambda; es al seguir un canal variable donde el compromiso memoria/ruido
aparece.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from _common import (BASE, EQ_LABELS, banner, eq_config, plots,
                     save_table, sweep_ebn0)
from comm2 import ReceiverConfig, monte_carlo, run_link, scenarios
from comm2.channel import PROFILES
from comm2.modulation import Modulation
from comm2.sync import max_cfo_acquisition

EBN0 = np.arange(4, 19, 2.0)
METODOS = ["none", "lms", "rls"]
EB_FIJO = 14.0


def _mc(p, chan_factory, eq_kind, n_frames=3, **rxkw):
    rx = ReceiverConfig(eq=eq_config(eq_kind), **rxkw)
    return monte_carlo(p, chan_factory, rx, n_frames=n_frames)


def main() -> dict:
    banner("EXPERIMENTO 4 - Robustez")
    plots.setup()
    p = BASE
    out = {}

    # ------------------------------------------------ 4.1 BER por escenario
    print("\n  4.1 BER vs Eb/N0 en los tres escenarios")
    rows = []
    for esc in ("A", "B", "C"):
        for kind in METODOS:
            df = sweep_ebn0(p, esc, kind, EBN0, base_frames=1)
            rows.append(df)
    d41 = pd.concat(rows, ignore_index=True)
    save_table(d41, "exp4_1_escenarios")
    out["escenarios"] = d41

    # ----------------------------------------- 4.2 severidad del canal
    print("\n  4.2 BER vs severidad de la multitrayectoria")
    rows = []
    for perfil in ("flat", "mild", "moderate", "severe"):
        for kind in METODOS:
            r = _mc(p, lambda i, pr=perfil: scenarios.scenario_b(p, EB_FIJO, profile=pr),
                    kind, n_frames=3)
            rows.append({"perfil": perfil, "tau_rms_T": PROFILES[perfil].delay_spread_sym,
                         "eq": kind, "ebn0_db": EB_FIJO, "ber": r["ber"],
                         "evm_pct": r["evm_pct"], "eq_mse_db": r["eq_mse_db"]})
            print(f"    {perfil:9s} {kind:5s} tau={PROFILES[perfil].delay_spread_sym:.3f}T "
                  f"BER={r['ber']:.3e}")
    d42 = pd.DataFrame(rows)
    save_table(d42, "exp4_2_severidad")
    out["severidad"] = d42

    # --------------------------------------------- 4.3 offset de frecuencia
    print("\n  4.3 BER vs offset de frecuencia (limite de adquisicion)")
    f_max = max_cfo_acquisition(p.zc_len * p.sps, p.fs)
    print(f"    Rango de adquisicion Schmidl-Cox: +-{f_max:.0f} Hz "
          f"(+-{100*f_max/p.rs:.2f} % de Rs)")
    cfos = np.array([0, 0.001, 0.002, 0.004, 0.006, 0.008, 0.010, 0.012])
    rows = []
    for cf in cfos:
        for kind in ("none", "rls"):
            r = _mc(p, lambda i, cf=cf: scenarios.scenario_c(
                p, EB_FIJO, cfo_frac_rs=cf, phase_deg=0.0, timing_frac=0.0,
                clock_ppm=0.0), kind, n_frames=3)
            rows.append({"cfo_frac_rs": cf, "cfo_hz": cf * p.rs, "eq": kind,
                         "ber": r["ber"], "corr_sync": r["fine_corr"]})
        print(f"    CFO={cf*100:5.2f} % Rs ({cf*p.rs:7.1f} Hz)  "
              f"BER(none)={rows[-2]['ber']:.3e}  BER(rls)={rows[-1]['ber']:.3e}")
    d43 = pd.DataFrame(rows)
    save_table(d43, "exp4_3_cfo")
    out["cfo"] = d43

    # ------------------------------------ 4.4 fase y error de temporizacion
    print("\n  4.4 BER vs offset de fase y error de temporizacion")
    rows = []
    for ph in (0, 30, 60, 90, 135, 180):
        r = _mc(p, lambda i, ph=ph: scenarios.scenario_c(
            p, EB_FIJO, cfo_frac_rs=0.0, phase_deg=ph, timing_frac=0.0,
            clock_ppm=0.0), "rls", n_frames=3)
        rows.append({"variable": "fase_deg", "valor": ph, "ber": r["ber"]})
        print(f"    fase={ph:4d} deg  BER={r['ber']:.3e}")
    for tf in (0.0, 0.1, 0.25, 0.5, 0.75, 1.0):
        r = _mc(p, lambda i, tf=tf: scenarios.scenario_c(
            p, EB_FIJO, cfo_frac_rs=0.0, phase_deg=0.0, timing_frac=tf,
            clock_ppm=0.0), "rls", n_frames=3)
        rows.append({"variable": "timing_muestras", "valor": tf, "ber": r["ber"]})
        print(f"    retardo={tf:4.2f} muestras  BER={r['ber']:.3e}")
    for ppm in (0, 10, 25, 50, 100, 200):
        r = _mc(p, lambda i, ppm=ppm: scenarios.scenario_c(
            p, EB_FIJO, cfo_frac_rs=0.0, phase_deg=0.0, timing_frac=0.0,
            clock_ppm=ppm), "rls", n_frames=3)
        rows.append({"variable": "reloj_ppm", "valor": ppm, "ber": r["ber"]})
        print(f"    reloj={ppm:4d} ppm  BER={r['ber']:.3e}")
    d44 = pd.DataFrame(rows)
    save_table(d44, "exp4_4_fase_temporizacion")
    out["fase_timing"] = d44

    # ------------------------------ 4.5 taps del ecualizador y entrenamiento
    print("\n  4.5 BER vs numero de taps y longitud del entrenamiento")
    rows = []
    for n in (5, 9, 13, 17, 21, 25, 31, 41):
        for kind in ("lms", "rls"):
            rx = ReceiverConfig(eq=eq_config(kind, n_taps=n))
            r = monte_carlo(p, lambda i: scenarios.scenario_b(p, EB_FIJO), rx, n_frames=2)
            rows.append({"variable": "n_taps", "valor": n, "eq": kind,
                         "ber": r["ber"], "eq_mse_db": r["eq_mse_db"]})
        print(f"    N={n:3d}  BER(lms)={rows[-2]['ber']:.3e}  BER(rls)={rows[-1]['ber']:.3e}")
    for nt in (64, 128, 256, 512, 1024):
        pp = p.replace(n_train=nt)
        for kind in ("lms", "rls"):
            rx = ReceiverConfig(eq=eq_config(kind))
            r = monte_carlo(pp, lambda i: scenarios.scenario_b(pp, EB_FIJO), rx, n_frames=2)
            rows.append({"variable": "n_train", "valor": nt, "eq": kind,
                         "ber": r["ber"], "eq_mse_db": r["eq_mse_db"]})
        print(f"    entrenamiento={nt:5d} simb  BER(lms)={rows[-2]['ber']:.3e}  "
              f"BER(rls)={rows[-1]['ber']:.3e}")
    d45 = pd.DataFrame(rows)
    save_table(d45, "exp4_5_taps_entrenamiento")
    out["taps"] = d45

    # ---------------------------------------- 4.6 anchos de banda de lazo
    print("\n  4.6 BER vs ancho de banda de los lazos de sincronizacion")
    rows = []
    # Cada lazo se barre en DOS puntos de trabajo. El compromiso de un lazo solo
    # es visible cerca del umbral del sistema: con QPSK a 14 dB el margen de
    # decision es tan amplio que un error de temporizacion estatico no se nota,
    # y hace falta una constelacion densa (16-QAM a 10 dB) para verlo. Con el
    # PLL pasa lo simetrico: en AWGN puro la curva es plana y solo el escenario
    # degradado, donde hay residuo de frecuencia que seguir, revela el minimo.
    for mod, esc, eb, kind in (("16qam", "A", 10.0, "none"),
                               ("qpsk", "C", EB_FIJO, "rls")):
        pm = p.replace(mod=mod)
        for bw in (0.002, 0.005, 0.01, 0.02, 0.05, 0.1):
            r = _mc(pm, lambda i: scenarios.get(esc, pm, ebn0_db=eb), kind,
                    n_frames=4, timing_loop_bw=bw)
            rows.append({"lazo": "temporizacion", "mod": mod, "escenario": esc,
                         "ebn0_db": eb, "eq": kind, "bn_t": bw, "ber": r["ber"],
                         "corr_sync": r["fine_corr"]})
            print(f"    temporizacion {mod:5s} esc.{esc} {eb:4.1f} dB  "
                  f"Bn*T={bw:<6} BER={r['ber']:.3e}")
    for mod, esc, eb, kind in (("qpsk", "A", 2.0, "none"),
                               ("qpsk", "C", 6.0, "rls")):
        pm = p.replace(mod=mod)
        for bw in (5e-5, 1e-4, 2e-4, 5e-4, 1e-3, 2e-3, 5e-3):
            r = _mc(pm, lambda i: scenarios.get(esc, pm, ebn0_db=eb), kind,
                    n_frames=4, phase_loop_bw=bw)
            rows.append({"lazo": "fase", "mod": mod, "escenario": esc,
                         "ebn0_db": eb, "eq": kind, "bn_t": bw, "ber": r["ber"],
                         "corr_sync": r["fine_corr"]})
            print(f"    fase {mod:5s} esc.{esc} {eb:4.1f} dB  Bn*T={bw:<7} "
                  f"BER={r['ber']:.3e}")
    d46 = pd.DataFrame(rows)
    save_table(d46, "exp4_6_lazos")
    out["lazos"] = d46

    # ------------------------------------------ 4.7 Rayleigh y factor de olvido
    print("\n  4.7 Escenario D (Rayleigh): papel del factor de olvido")
    rows = []
    for fd in (0.0, 5e-5, 2e-4, 1e-3, 5e-3):
        for lam in (0.99, 0.999, 0.9999):
            rx = ReceiverConfig(eq=eq_config("rls", lam=lam))
            r = monte_carlo(p, lambda i, fd=fd: scenarios.scenario_d_fading(
                p, EB_FIJO, fd_frac_rs=fd), rx, n_frames=3, seed_offset=1)
            rows.append({"fd_frac_rs": fd, "fd_hz": fd * p.rs, "lam": lam,
                         "ber": r["ber"], "eq_mse_db": r["eq_mse_db"]})
        best = min(rows[-3:], key=lambda d: d["ber"])
        print(f"    fD/Rs={fd:<8g} ({fd*p.rs:7.1f} Hz)  "
              + "  ".join(f"lam={d['lam']}: {d['ber']:.2e}" for d in rows[-3:])
              + f"   -> mejor lam={best['lam']}")
    d47 = pd.DataFrame(rows)
    save_table(d47, "exp4_7_rayleigh")
    out["rayleigh"] = d47

    # ================================================================ figuras
    # Bits acumulados por punto en cada barrido: fijan el suelo de resolucion de
    # la BER (0.5/n_bits), que se dibuja con marcador hueco en vez de descartar
    # los puntos sin errores (si se descartan, el metodo que mejor funciona
    # desaparece de la grafica).
    k = p.bits_per_symbol
    BITS_3F = 3 * p.n_payload * k
    BITS_2F = 2 * p.n_payload * k
    fig, axes = plt.subplots(2, 3, figsize=(14, 8), constrained_layout=True)

    ax = axes[0, 0]
    styles = {"A": "-", "B": "--", "C": ":"}
    for esc in ("A", "B", "C"):
        for kind in METODOS:
            sub = d41[(d41["escenario"] == esc) & (d41["eq"] == kind)]
            ax.semilogy(sub["ebn0_db"], np.where(sub["ber"] <= 0, np.nan, sub["ber"]),
                        styles[esc], color=plots.COLORS[kind], lw=1.3,
                        label=f"{esc} / {kind.upper()}")
    ax.semilogy(EBN0, Modulation(p.mod).ber_theory(EBN0), "k-", lw=1.6, alpha=0.5,
                label="AWGN teorica")
    ax.set_xlabel("$E_b/N_0$ [dB]"); ax.set_ylabel("BER"); ax.set_ylim(1e-6, 1)
    ax.grid(True, which="both", alpha=0.3); ax.legend(fontsize=6, ncol=2)
    ax.set_title("4.1  Escenarios A / B / C")

    ax = axes[0, 1]
    for kind in METODOS:
        sub = d42[d42["eq"] == kind].sort_values("tau_rms_T")
        plots.ber_with_floor(ax, sub["tau_rms_T"], sub["ber"], BITS_3F,
                             label=EQ_LABELS[kind], color=plots.COLORS[kind])
    ax.set_yscale("log")
    ax.set_xlabel(r"Dispersion de retardo RMS  $\tau_{rms}/T$")
    ax.set_ylabel("BER"); ax.set_ylim(1e-6, 1)
    ax.grid(True, which="both", alpha=0.3); ax.legend(fontsize=7)
    ax.set_title(f"4.2  Severidad del canal ($E_b/N_0$={EB_FIJO:.0f} dB)")

    ax = axes[0, 2]
    for kind in ("none", "rls"):
        sub = d43[d43["eq"] == kind]
        plots.ber_with_floor(ax, sub["cfo_frac_rs"] * 100, sub["ber"], BITS_3F,
                             label=EQ_LABELS[kind], color=plots.COLORS[kind])
    ax.set_yscale("log")
    ax.axvline(100 * f_max / p.rs, color="r", ls="--", lw=1.2,
               label=f"limite Schmidl-Cox\n$R_s/(2 L)$ = {100*f_max/p.rs:.2f} %")
    ax.set_xlabel("Offset de frecuencia [% de $R_s$]"); ax.set_ylabel("BER")
    ax.set_ylim(1e-6, 1); ax.grid(True, which="both", alpha=0.3); ax.legend(fontsize=7)
    ax.set_title("4.3  Offset de frecuencia")

    ax = axes[1, 0]
    for var, marker, col, lab in (
            ("fase_deg", "o", "#1f77b4", "Fase [grados]"),
            ("timing_muestras", "s", "#d62728", "Retardo [muestras x100]"),
            ("reloj_ppm", "^", "#2ca02c", "Reloj [ppm]")):
        sub = d44[d44["variable"] == var]
        x = sub["valor"].to_numpy(dtype=float)
        if var == "timing_muestras":
            x = x * 100
        plots.ber_with_floor(ax, x, sub["ber"], BITS_3F, label=lab, color=col,
                             marker=marker, floor_marker=marker)
    ax.set_yscale("log")
    ax.set_xlabel("Valor de la perturbacion"); ax.set_ylabel("BER")
    ax.set_ylim(1e-6, 1); ax.grid(True, which="both", alpha=0.3); ax.legend(fontsize=7)
    ax.set_title("4.4  Fase y temporizacion (RLS)")

    ax = axes[1, 1]
    for kind in ("lms", "rls"):
        sub = d45[(d45["variable"] == "n_taps") & (d45["eq"] == kind)]
        plots.ber_with_floor(ax, sub["valor"], sub["ber"], BITS_2F,
                             label=EQ_LABELS[kind], color=plots.COLORS[kind])
    ax.set_yscale("log")
    ax.set_xlabel("Numero de taps $N$"); ax.set_ylabel("BER")
    ax.set_ylim(1e-6, 1); ax.grid(True, which="both", alpha=0.3); ax.legend(fontsize=7)
    ax.set_title(f"4.5  Longitud del ecualizador ($E_b/N_0$={EB_FIJO:.0f} dB)")

    ax = axes[1, 2]
    col7 = ["#1f77b4", "#2ca02c", "#9467bd", "#d62728", "#ff7f0e"]
    for c, fd in zip(col7, sorted(d47["fd_frac_rs"].unique())):
        sub = d47[d47["fd_frac_rs"] == fd].sort_values("lam")
        plots.ber_with_floor(ax, sub["lam"], sub["ber"], BITS_3F, color=c,
                             label=f"$f_D/R_s$ = {fd:g}")
    ax.set_yscale("log")
    ax.set_xlabel(r"Factor de olvido $\lambda$"); ax.set_ylabel("BER")
    ax.set_ylim(1e-6, 1); ax.grid(True, which="both", alpha=0.3); ax.legend(fontsize=6)
    ax.set_title("4.7  Rayleigh: memoria del RLS")

    fig.suptitle("Experimento 4 - Robustez del receptor  (marcador hueco = cero "
                 "errores, por debajo del suelo de resolucion)")
    plots.save_fig(fig, "exp4_robustez")

    # ------------------------------- figura de los lazos y del entrenamiento
    fig, axes = plt.subplots(1, 3, figsize=(14, 3.9), constrained_layout=True)

    col_mod = {"16qam": "#d62728", "qpsk": "#1f77b4"}
    for ax, lazo, marca, titulo in (
            (axes[0], "temporizacion", 0.02, "4.6  Lazo de temporizacion (Gardner)"),
            (axes[1], "fase", 5e-4, "4.6  PLL de fase dirigido por decision")):
        sub = d46[d46["lazo"] == lazo]
        for (mod, esc, eb), s in sub.groupby(["mod", "escenario", "ebn0_db"],
                                             sort=False):
            kk = 4 if mod == "16qam" else 2
            plots.ber_with_floor(ax, s["bn_t"], s["ber"], 4 * p.n_payload * kk,
                                 color=col_mod[mod], ls="-" if esc == "A" else "--",
                                 label=f"{mod.upper()}, esc. {esc}, {eb:.0f} dB")
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.axvline(marca, color="0.4", ls=":", lw=1.2)
        ax.set_xlabel(r"$B_n T$"); ax.set_ylabel("BER")
        ax.grid(True, which="both", alpha=0.3); ax.legend(fontsize=6.5)
        ax.set_title(titulo)

    ax = axes[2]
    for kind in ("lms", "rls"):
        sub = d45[(d45["variable"] == "n_train") & (d45["eq"] == kind)].sort_values("valor")
        plots.ber_with_floor(ax, sub["valor"], sub["ber"], BITS_2F,
                             color=plots.COLORS[kind], marker="s", floor_marker="s",
                             label=EQ_LABELS[kind])
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_ylim(1e-6, 1e-2)
    ax.set_xlabel("Simbolos de entrenamiento"); ax.set_ylabel("BER")
    ax.grid(True, which="both", alpha=0.3); ax.legend(fontsize=7)
    ax.set_title("4.5  Longitud de la secuencia de entrenamiento")

    fig.suptitle("Experimento 4 - Compromisos de diseno  (marcador hueco = cero errores)")
    plots.save_fig(fig, "exp4_lazos")
    return out


if __name__ == "__main__":
    main()

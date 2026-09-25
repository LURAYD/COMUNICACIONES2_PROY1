"""Experimento 8 - Que hace el ecualizador: canal ideal frente a canal h.

El ecualizador existe para deshacer la ISI, no para quitar ruido. Este
experimento lo muestra comparando, con los MISMOS datos y el MISMO ruido
(semillas comunes), cuatro enlaces por el escenario B (multitrayecto + AWGN,
sin errores de sincronismo, para aislar la ISI):

    canal ideal  h = [1]  sin ecualizar      la referencia: solo ruido
    canal ideal  h = [1]  + ecualizador      no mejora nada: no hay ISI que quitar
    canal h               sin ecualizar      ISI + ruido
    canal h               + ecualizador      la ISI desaparece; el ruido no

Receptor: filtro adaptado + Schmidl-Cox (trama) + Gardner (temporizacion) +
ecualizador. La sincronizacion de PORTADORA (CFO y PLL) se desactiva porque el
escenario B no tiene offset de frecuencia ni de fase, y con el ojo cerrado el
PLL dirigido por decision desliza 90 grados (medido: h = [0.2, 1, 0, 0.8] sin
ecualizar a 6 dB daba BER 0.587, peor que una moneda). Ese fallo seria de
sincronismo, no de ISI. --sincronismo-completo los vuelve a activar.

El canal h se da a mano (--h "0,0.2,1,0,0.8") o se sortea con una semilla
(--semilla 7): misma semilla, mismo canal, de modo que se puede ir cambiando
de canal de forma reproducible. La semilla del canal es independiente de la
de los datos y el ruido (--semilla-sim), asi que al cambiar de canal lo unico
que cambia es el canal.

Figuras:
  <nombre>.png            constelaciones, BER, SNR efectiva y reparto ISI/ruido
  <nombre>_mecanismo.png  canal, ecualizador y su convolucion (~ impulso) en
                          tiempo y en frecuencia: donde el canal tiene un nulo,
                          el ecualizador pone ganancia, y con ella amplifica ruido

    python exp8_ecualizador_isi.py                      # canal aleatorio, semilla 7
    python exp8_ecualizador_isi.py --semilla 3
    python exp8_ecualizador_isi.py --semilla 3 --max-eco 0.4 --ntaps 7
    python exp8_ecualizador_isi.py --h "0,0.2,1,0,0.8" --eq lms,rls
"""

from __future__ import annotations

import argparse
from dataclasses import replace

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from _common import BASE, NO_EQ, banner, eq_config, frames_for, plots, save_table
from comm2 import ReceiverConfig, monte_carlo, run_link, scenarios, metrics
from comm2.channel import MultipathProfile, PROFILES, format_taps, parse_taps, random_taps
from comm2.link import equalizer_breakdown, symbol_rate_channel
from comm2.modulation import Modulation
from comm2.pulse import rrc_filter

# Colores (validados con el comprobador de paleta: CVD y contraste en claro).
# El color codifica el RECEPTOR y el trazo el CANAL: discontinuo = ideal,
# continuo = h.
C_RX = {"none": plots.COLORS["none"], "lms": plots.COLORS["lms"],
        "rls": plots.COLORS["rls"]}
C_ISI, C_RUIDO, C_TEO = "#c65d00", "#6b6b6b", "#333333"
NOMBRE_RX = {"none": "sin ecualizar", "lms": "LMS", "rls": "RLS"}


def parse_range(text: str) -> np.ndarray:
    if ":" in text:
        a, b, s = (float(t) for t in text.split(":"))
        return np.round(np.arange(a, b + s / 2, s), 10)
    return np.array([float(t) for t in text.replace(",", " ").split()])


def main(argv=None) -> pd.DataFrame:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--h", default=None, help="canal a mano, p. ej. '0,0.2,1,0,0.8'")
    ap.add_argument("--semilla", type=int, default=7,
                    help="semilla del canal aleatorio (si no se da --h)")
    ap.add_argument("--ntaps", type=int, default=5, help="coeficientes del canal aleatorio")
    ap.add_argument("--cursor", type=int, default=None,
                    help="posicion del coeficiente principal (por defecto el centro)")
    ap.add_argument("--max-eco", type=float, default=0.6,
                    help="amplitud maxima de los ecos aleatorios (el cursor vale 1)")
    ap.add_argument("--complejo", action="store_true", help="ecos con fase aleatoria")
    ap.add_argument("--eq", default="lms", help="ecualizadores: 'lms', 'rls' o 'lms,rls'")
    ap.add_argument("--ebn0", default="0:16:2", help="barrido de Eb/N0 [dB]")
    ap.add_argument("--ebn0-detalle", type=float, default=14.0,
                    help="Eb/N0 de las constelaciones y del reparto ISI/ruido")
    ap.add_argument("--tramas", type=int, default=1, help="tramas base por punto de BER")
    ap.add_argument("--semilla-sim", type=int, default=BASE.seed,
                    help="semilla de datos y ruido (comun a todos los enlaces)")
    ap.add_argument("--sincronismo-completo", action="store_true",
                    help="activa CFO y PLL de fase (por defecto apagados, ver arriba)")
    ap.add_argument("--nombre", default=None, help="prefijo de CSV y figuras")
    args = ap.parse_args(argv)

    if args.h is not None:
        h = parse_taps(args.h)
        origen = "dado a mano"
        nombre = args.nombre or "exp8_ecualizador_isi"
    else:
        h = random_taps(args.ntaps, args.semilla, args.cursor, args.max_eco, args.complejo)
        origen = f"aleatorio, semilla {args.semilla}"
        nombre = args.nombre or f"exp8_ecualizador_isi_s{args.semilla}"
    eqs = [e.strip() for e in args.eq.split(",") if e.strip()]
    p = replace(BASE, seed=args.semilla_sim)
    prof_h = MultipathProfile.from_taps(h, name=f"h = [{format_taps(h)}]")
    rrc = rrc_filter(p.beta, p.span, p.sps)
    c_th = symbol_rate_channel(rrc, prof_h.taps(p.sps), p.sps, "cursor")
    th = metrics.isi_metrics(c_th)
    n_win = h.size + 3

    banner(f"EXPERIMENTO 8 - Ecualizador: canal ideal frente a h = [{format_taps(h)}] ({origen})")
    D = th["peak_distortion"]
    estado = ("ojo CERRADO sin ecualizar" if D > 1.005 else
              "ojo justo en el limite (D = 1)" if D >= 0.995 else "ojo abierto")
    print(f"  ISI del canal h: SIR = {th['sir_db']:.2f} dB, D = {D:.2f} ({estado})")
    rx_kw = {} if args.sincronismo_completo else dict(cfo_correction=False, phase_pll=False)

    enlaces = [("ideal", PROFILES["flat"], "none")]
    enlaces += [("ideal", PROFILES["flat"], e) for e in eqs]
    enlaces += [("h", prof_h, "none")]
    enlaces += [("h", prof_h, e) for e in eqs]

    # ------------------------------------------------ barrido de Eb/N0
    rows = []
    for canal, prof, eq in enlaces:
        rx = ReceiverConfig(eq=NO_EQ if eq == "none" else eq_config(eq), **rx_kw)
        print(f"  canal {canal:5s} + {NOMBRE_RX[eq]}")
        for eb in parse_range(args.ebn0):
            nf = frames_for(eb, args.tramas)
            out = monte_carlo(p, lambda i, eb=eb, prof=prof: scenarios.scenario_b(
                p, eb, profile=prof), rx, n_frames=nf)
            rows.append({
                "canal": canal, "h": format_taps(h) if canal == "h" else "1",
                "eq": eq, "ebn0_db": eb, "esn0_db": eb + 10 * np.log10(2),
                "ber": out["ber"], "ber_errors": out["ber_errors"],
                "ber_bits": out["ber_bits"], "evm_pct": out["evm_pct"],
                "snr_efectiva_db": metrics.evm_to_snr_db(out["evm_pct"]),
                "n_frames": nf,
            })
            print(f"    Eb/N0={eb:5.1f} dB  BER={out['ber']:.3e} "
                  f"({out['ber_errors']:6d}/{out['ber_bits']})  "
                  f"SNR ef.={rows[-1]['snr_efectiva_db']:5.1f} dB")
    df = pd.DataFrame(rows)
    df["limite_lineal_db"] = [metrics.mmse_le_snr_db(c_th, e) if cn == "h" else e
                              for cn, e in zip(df["canal"], df["esn0_db"])]
    save_table(df, nombre)

    # ------------------------------------------- detalle a un Eb/N0 fijo
    det = {}
    for canal, prof, eq in enlaces:
        rx = ReceiverConfig(eq=NO_EQ if eq == "none" else eq_config(eq), **rx_kw)
        r = run_link(p, scenarios.scenario_b(p, args.ebn0_detalle, profile=prof), rx)
        det[(canal, eq)] = (r, equalizer_breakdown(r, n_win))
    print(f"\n  Reparto del error a Eb/N0 = {args.ebn0_detalle:g} dB "
          f"(potencia relativa a la senal util):")
    filas = []
    for (canal, eq), (r, d) in det.items():
        print(f"    canal {canal:5s} {NOMBRE_RX[eq]:13s}  ISI = {10*np.log10(d['isi_rel']+1e-12):6.1f} dB  "
              f"ruido = {10*np.log10(d['noise_rel']):6.1f} dB  "
              f"(ganancia de ruido del ecualizador {d['noise_gain_db']:+.2f} dB)  "
              f"MSE medido = {10*np.log10(d['mse']):6.1f} dB  BER = {r.stats['ber']:.2e}")
        filas.append({"canal": canal, "eq": eq, "ebn0_db": args.ebn0_detalle,
                      "isi_rel_db": 10 * np.log10(d["isi_rel"] + 1e-12),
                      "ruido_rel_db": 10 * np.log10(d["noise_rel"]),
                      "ganancia_ruido_eq_db": d["noise_gain_db"],
                      "mse_medido_db": 10 * np.log10(d["mse"]),
                      "ber": r.stats["ber"], "ber_errors": r.stats["ber_errors"]})
    save_table(pd.DataFrame(filas), f"{nombre}_reparto")

    _figura_comparacion(df, det, h, eqs, th, args, p, nombre, origen)
    _figura_mecanismo(det, h, eqs[0], args, nombre)
    return df


def _linea(canal):
    return dict(ls="--", marker="o", mfc="white") if canal == "ideal" else dict(ls="-", marker="o")


def _figura_comparacion(df, det, h, eqs, th, args, p, nombre, origen):
    plots.setup()
    fig = plt.figure(figsize=(15, 9.2), constrained_layout=True)
    gs = fig.add_gridspec(2, 3 + len(eqs) - 1)
    eq0 = eqs[0]

    # ---------------------------------------------- fila 1: constelaciones
    paneles = [("ideal", "none", "Canal ideal, sin ecualizar")]
    paneles += [("h", "none", "Canal h, sin ecualizar")]
    paneles += [("h", e, f"Canal h + {NOMBRE_RX[e]}") for e in eqs]
    for j, (canal, eq, titulo) in enumerate(paneles):
        ax = fig.add_subplot(gs[0, j])
        r = det[(canal, eq)][0]
        plots.constellation(ax, r.payload_rx, f"{titulo}\nBER = {_ber_txt(r)}",
                            mod=r.frame.mod, color=C_RX[eq])
        ax.set_xlim(-2, 2); ax.set_ylim(-2, 2)

    sub = gs[1, :].subgridspec(1, 3)

    # ---------------------------------------------- BER
    ax = fig.add_subplot(sub[0, 0])
    eb = np.array(sorted(df["ebn0_db"].unique()))
    ax.plot(eb, Modulation("qpsk").ber_theory(eb), color=C_TEO, lw=1,
            label="teoria AWGN (canal ideal)")
    for (canal, eq), g in df.groupby(["canal", "eq"], sort=False):
        st = _linea(canal)
        plots.ber_with_floor(ax, g["ebn0_db"], g["ber"], g["ber_bits"].max(),
                             label=f"{'ideal' if canal == 'ideal' else 'h'}, {NOMBRE_RX[eq]}",
                             color=C_RX[eq], ls=st["ls"])
    # el suelo (0 errores) se dibuja en 0.5/bits: el eje tiene que llegar a el
    ax.set_yscale("log"); ax.set_ylim(bottom=0.25 / df["ber_bits"].max())
    ax.set_xlabel("$E_b/N_0$ [dB]"); ax.set_ylabel("BER")
    ax.set_title("BER: el ecualizador devuelve h hacia el canal ideal")
    ax.legend(fontsize=7)

    # ---------------------------------------------- SNR efectiva
    ax = fig.add_subplot(sub[0, 1])
    esn0 = eb + 10 * np.log10(2)
    ax.plot(eb, esn0, color=C_TEO, lw=1, label="$E_s/N_0$: techo (canal ideal)")
    for (canal, eq), g in df.groupby(["canal", "eq"], sort=False):
        st = _linea(canal)
        ax.plot(g["ebn0_db"], g["snr_efectiva_db"], color=C_RX[eq], ls=st["ls"],
                marker="o", ms=4, mfc=st.get("mfc", C_RX[eq]),
                label=f"{'ideal' if canal == 'ideal' else 'h'}, {NOMBRE_RX[eq]}")
    gh = df[(df["canal"] == "h") & (df["eq"] == "none")]
    ax.plot(gh["ebn0_db"], gh["limite_lineal_db"], color=C_TEO, lw=1, ls="-.",
            label="limite de cualquier ecualizador lineal con h")
    ax.axhline(th["sir_db"], color=C_ISI, ls=":", lw=1)
    ax.text(eb.max(), th["sir_db"] + 0.4, f"SIR del canal h = {th['sir_db']:.1f} dB",
            fontsize=7, color="0.3", ha="right")
    ax.set_xlabel("$E_b/N_0$ [dB]"); ax.set_ylabel("SNR efectiva a la salida [dB]")
    ax.set_title("Nadie supera el techo: el ecualizador no quita ruido")
    ax.legend(fontsize=7)

    # ---------------------------------------------- reparto ISI / ruido
    ax = fig.add_subplot(sub[0, 2])
    etiquetas, isi, ruido, mse = [], [], [], []
    for (canal, eq), (r, d) in det.items():
        etiquetas.append(f"{'ideal' if canal == 'ideal' else 'h'}, {NOMBRE_RX[eq]}")
        isi.append(10 * np.log10(d["isi_rel"] + 1e-12))
        ruido.append(10 * np.log10(d["noise_rel"]))
        mse.append(10 * np.log10(d["mse"]))
    y = np.arange(len(etiquetas))[::-1]
    lo = min(min(isi), min(ruido)) - 3
    for yi, a, b in zip(y, isi, ruido):
        ax.plot([lo, max(a, b)], [yi, yi], color="0.88", lw=1, zorder=1)
    ax.plot(isi, y, "o", color=C_ISI, ms=8, label="ISI residual", zorder=3)
    ax.plot(ruido, y, "s", color=C_RUIDO, ms=8, label="ruido", zorder=3)
    ax.plot(mse, y, "x", color="k", ms=8, mew=1.6, label="error total medido", zorder=4)
    for yi, a in zip(y, isi):
        ax.annotate(f"{a:.0f}", (a, yi), textcoords="offset points", xytext=(0, 7),
                    ha="center", fontsize=7, color="0.3")
    ax.set_yticks(y); ax.set_yticklabels(etiquetas, fontsize=8)
    ax.set_xlim(left=max(lo, -60))
    ax.set_xlabel("potencia relativa a la senal util [dB]")
    ax.set_title(f"De que esta hecho el error ($E_b/N_0$ = {args.ebn0_detalle:g} dB)")
    ax.legend(fontsize=7, loc="lower left")

    sinc = "sincronismo completo" if args.sincronismo_completo else "sin CFO/PLL (escenario B)"
    fig.suptitle(f"Experimento 8 - Canal ideal frente a h = [{format_taps(h)}] ({origen}); "
                 f"SIR = {th['sir_db']:.1f} dB, D = {th['peak_distortion']:.2f}  |  "
                 f"{sinc}  |  trazo discontinuo: canal ideal, continuo: canal h")
    plots.save_fig(fig, nombre)


def _figura_mecanismo(det, h, eq, args, nombre):
    plots.setup()
    r, d = det[("h", eq)]
    c, f, q = d["c"], d["f"], d["q"]
    fig, axes = plt.subplots(1, 4, figsize=(17, 3.9), constrained_layout=True)

    def stem(ax, v, color, titulo):
        k = np.arange(v.size) - int(np.argmax(np.abs(v)))
        mk, st, _ = ax.stem(k, np.abs(v), basefmt=" ")
        plt.setp(st, color=color, lw=1.4); plt.setp(mk, color=color, ms=5)
        ax.axhline(0, color="0.8", lw=0.8)
        ax.set_xlabel("k (simbolos respecto al tap principal)"); ax.set_title(titulo)

    # recorta colas despreciables para que se lea
    def recorta(v, thr=0.02):
        nz = np.flatnonzero(np.abs(v) > thr * np.abs(v).max())
        return v[nz[0]: nz[-1] + 1]

    stem(axes[0], recorta(c), C_ISI, "1) Canal h que ve el receptor $|c_k|$")
    axes[0].set_ylabel("modulo")
    stem(axes[1], recorta(f), C_RX[eq], f"2) Ecualizador {NOMBRE_RX[eq]} $|f_k|$")
    stem(axes[2], recorta(q), "k", "3) Canal * ecualizador $\\approx$ impulso")
    axes[2].text(0.02, 0.95, f"ISI residual {10*np.log10(d['isi_rel']+1e-12):.1f} dB",
                 transform=axes[2].transAxes, fontsize=8, va="top")

    ax = axes[3]
    fr = np.linspace(-0.5, 0.5, 1024)

    def resp(v):
        return 20 * np.log10(np.abs(np.exp(-2j * np.pi * np.outer(fr, np.arange(v.size))) @ v) + 1e-9)

    ax.plot(fr, resp(c), color=C_ISI, lw=1.6, label="canal $|C(f)|$")
    ax.plot(fr, resp(f), color=C_RX[eq], lw=1.6, label=f"ecualizador $|F(f)|$")
    ax.plot(fr, resp(q), color="k", lw=1.6, label="conjunto $|C\\cdot F|$")
    ax.axhline(0, color="0.6", ls=":", lw=1)
    ax.set_ylim(-25, 20); ax.set_xlabel("f / Rs"); ax.set_ylabel("dB")
    ax.set_title(f"4) Donde el canal cae, el ecualizador sube\n"
                 f"(y amplifica el ruido: {d['noise_gain_db']:+.1f} dB)")
    ax.legend(fontsize=7, loc="lower center")
    fig.suptitle(f"Como actua el ecualizador sobre h = [{format_taps(h)}] "
                 f"($E_b/N_0$ = {args.ebn0_detalle:g} dB)")
    plots.save_fig(fig, f"{nombre}_mecanismo")


def _ber_txt(r) -> str:
    s = r.stats
    return f"{s['ber']:.2e}" if s["ber_errors"] else f"< {1 / s['ber_bits']:.0e} (0 errores)"


if __name__ == "__main__":
    main()

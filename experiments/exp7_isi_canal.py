"""Experimento 7 - ISI en funcion de la respuesta al impulso del canal h.

Se parte de un canal discreto dado a mano, por ejemplo

    h = [0, 0.2, 1, 0, 0.8]        (un coeficiente por periodo de simbolo)

y se va "encendiendo" el canal con un factor alfa: el cursor (coeficiente
mayor) queda fijo y los ecos se escalan, h_alfa[k] = alfa * h[k] para k != cursor.
alfa = 0 es el canal plano, alfa = 1 es exactamente el h dado y alfa > 1 lo
exagera. En cada punto se mide la ISI de dos formas independientes:

  teorica  a partir del canal equivalente a tasa de simbolo RRC * g * RRC,
           muestreado en el instante de Nyquist del trayecto dominante;
  medida   ajustando por minimos cuadrados el canal que vio el receptor real
           (Schmidl-Cox + Gardner + sinc. de trama) a partir de los simbolos
           conocidos, a Eb/N0 alto para que domine la ISI y no el ruido.

Metricas (ver comm2.metrics.isi_metrics):
  SIR = |c0|^2 / sum|ck|^2       potencia util frente a potencia de ISI
  D   = sum|ck| / |c0|           distorsion de pico; D >= 1 cierra el ojo
  apertura de ojo de peor caso (carril I, agrupada por simbolo transmitido;
  < 0 = ojo cerrado), EVM y BER sin ecualizar / con LMS.

    python exp7_isi_canal.py
    python exp7_isi_canal.py --h "1, 0.5, -0.3" --alfa 0:2:0.1
    python exp7_isi_canal.py --h "0,0.2,1,0,0.8" --variar 4      # solo h[4]
"""

from __future__ import annotations

import argparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from _common import BASE, banner, eq_config, plots, save_table
from comm2 import ReceiverConfig, EqualizerConfig, run_link, scenarios, metrics
from comm2.channel import MultipathProfile, format_taps, parse_taps
from comm2.link import symbol_rate_channel
from comm2.pulse import rrc_filter

H_DEF = "0, 0.2, 1, 0, 0.8"
ALFA_DEF = "0:1.5:0.1"
EBN0_BER = 12.0        # Eb/N0 de la comparacion de BER (ruido + ISI)
EBN0_MEDIDA = 40.0     # Eb/N0 de la medida de ISI (el ruido queda ~30 dB por debajo)


def parse_range(text: str) -> np.ndarray:
    """'0:1.5:0.1' -> [0, 0.1, ..., 1.5]; tambien acepta lista '0,0.5,1'."""
    if ":" in text:
        a, b, s = (float(t) for t in text.split(":"))
        return np.round(np.arange(a, b + s / 2, s), 10)
    return np.array([float(t) for t in text.replace(",", " ").split()])


def scaled_taps(h: np.ndarray, alfa: float, variar) -> np.ndarray:
    """h con los coeficientes elegidos multiplicados por alfa."""
    out = np.array(h, dtype=complex)
    if variar == "ecos":
        idx = [k for k in range(h.size) if k != int(np.argmax(np.abs(h)))]
    else:
        idx = [int(variar)]
    out[idx] *= alfa
    return out.real.copy() if np.all(out.imag == 0) else out


def eye_window(r, p, n_sym: int = 400):
    """Tramo del filtro adaptado dentro de la CARGA UTIL.

    mf_sync empieza 16 simbolos antes del preambulo. A diferencia de exp2, se
    salta preambulo y entrenamiento (+32 simbolos de margen): el preambulo
    Zadoff-Chu tiene modulo constante pero fase arbitraria, su componente I
    recorre todo [-1, 1] y ensucia el ojo aunque el canal sea plano.
    """
    off = (16 + r.frame.preamble_len + r.frame.n_train + 32) * p.sps
    return r.sync_info["mf_sync"][off: off + n_sym * p.sps]


def main(argv=None) -> pd.DataFrame:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--h", default=H_DEF, help="respuesta al impulso, p. ej. '0,0.2,1,0,0.8'")
    ap.add_argument("--espaciado", type=float, default=1.0,
                    help="separacion entre coeficientes de h, en periodos de simbolo")
    ap.add_argument("--alfa", default=ALFA_DEF, help="barrido 'inicio:fin:paso' o lista")
    ap.add_argument("--variar", default="ecos",
                    help="'ecos' (todos menos el cursor) o el indice k de un solo coeficiente")
    ap.add_argument("--ebn0", type=float, default=EBN0_BER)
    ap.add_argument("--ebn0-medida", type=float, default=EBN0_MEDIDA)
    ap.add_argument("--eq", default="lms", choices=["lms", "rls", "mmse", "zf"])
    ap.add_argument("--nombre", default="exp7_isi_canal", help="prefijo de CSV y figuras")
    args = ap.parse_args(argv)

    h0 = parse_taps(args.h)
    alfas = parse_range(args.alfa)
    variar = args.variar if args.variar == "ecos" else int(args.variar)
    p = BASE
    rrc = rrc_filter(p.beta, p.span, p.sps)
    banner(f"EXPERIMENTO 7 - ISI frente al canal h = [{format_taps(h0)}] "
           f"(paso {args.espaciado:g} T), variando {variar}")

    # Receptor para MEDIR la ISI: sin ecualizador, sin CFO ni PLL (el
    # escenario B no tiene offset de frecuencia), asi los simbolos antes del
    # ecualizador solo llevan canal + ruido.
    rx_medida = ReceiverConfig(eq=EqualizerConfig(kind="none"),
                               cfo_correction=False, phase_pll=False)
    rx_none = ReceiverConfig(eq=EqualizerConfig(kind="none"))
    rx_eq = ReceiverConfig(eq=eq_config(args.eq))
    n_win = int(np.ceil(h0.size * args.espaciado)) + 3

    rows, keep = [], {}
    a_eyes = sorted({float(alfas[np.argmin(np.abs(alfas - a))])
                     for a in (0.0, 0.5, 1.0, alfas.max())})
    for alfa in alfas:
        h = scaled_taps(h0, alfa, variar)
        prof = MultipathProfile.from_taps(h, args.espaciado)

        # ---------------------------------------------------------- teoria
        c_th = symbol_rate_channel(rrc, prof.taps(p.sps), p.sps, phase="cursor")
        th = metrics.isi_metrics(c_th)

        # ---------------------------------------------------------- medida
        r = run_link(p, scenarios.scenario_b(p, args.ebn0_medida, profile=prof), rx_medida)
        # Solo la carga util: durante el entrenamiento Gardner aun esta en su
        # transitorio y su error de muestreo se sumaria a la ISI del canal.
        ref = r.frame.payload
        rx_p = r.sym_pre_eq[r.frame.n_train:]
        c_me, resid = metrics.estimate_symbol_channel(rx_p, ref, n_win, n_win)
        me = metrics.isi_metrics(c_me)
        # rx esta alineado con ref en el retardo 0 del ajuste; si el trayecto
        # dominante no cae ahi (alfa grande), se desplaza ref hasta el cursor.
        lag = int(np.argmax(np.abs(c_me))) - n_win
        rx_c = rx_p / c_me[lag + n_win]
        ojo = metrics.eye_opening_known(rx_c[max(lag, 0):], ref[max(-lag, 0):])
        if float(alfa) in a_eyes:
            keep[float(alfa)] = (r, c_th, c_me)

        # ------------------------------------------------ BER con ruido real
        chan = scenarios.scenario_b(p, args.ebn0, profile=prof)
        rn = run_link(p, chan, rx_none)
        re_ = run_link(p, chan, rx_eq)

        rows.append({
            "alfa": alfa, "h": format_taps(h), "tau_rms_T": prof.delay_spread_sym,
            "sir_teo_db": th["sir_db"], "sir_med_db": me["sir_db"],
            "D_teo": th["peak_distortion"], "D_med": me["peak_distortion"],
            "ojo_peor_teo": th["eye_worst_qpsk"], "ojo_peor_med": ojo,
            "energia_util": th["energy"],
            "residuo_db": 10 * np.log10(resid + 1e-30),
            "evm_sin_eq_pct": r.stats["evm_pct"], "enganche": r.locked,
            "ebn0_db": args.ebn0,
            "ber_sin_eq": rn.stats["ber"], "err_sin_eq": rn.stats["ber_errors"],
            f"ber_{args.eq}": re_.stats["ber"], f"err_{args.eq}": re_.stats["ber_errors"],
            f"evm_{args.eq}_pct": re_.stats["evm_pct"], "bits": rn.stats["ber_bits"],
        })
        f = lambda b, e: f"{b:.2e}" if e else f"<{1 / rn.stats['ber_bits']:.0e}"
        print(f"  alfa={alfa:4.2f}  SIR teo={th['sir_db']:6.2f} med={me['sir_db']:6.2f} dB  "
              f"D={th['peak_distortion']:.3f}  ojo={ojo:6.3f}  "
              f"BER@{args.ebn0:g}dB sin eq={f(rn.stats['ber'], rn.stats['ber_errors'])} "
              f"{args.eq}={f(re_.stats['ber'], re_.stats['ber_errors'])}")
    df = pd.DataFrame(rows)
    save_table(df, args.nombre)
    _figuras(df, keep, h0, args, p)
    return df


def _figuras(df, keep, h0, args, p):
    plots.setup()
    x = df["alfa"].to_numpy()
    c_teo, c_med = "#333333", plots.COLORS["none"]

    def marca_h(ax):
        if x.min() <= 1.0 <= x.max():
            ax.axvline(1.0, color="0.6", ls="--", lw=0.9)

    fig, axes = plt.subplots(2, 3, figsize=(14, 7.8), constrained_layout=True)

    # (a) respuesta al impulso a tasa de simbolo: teoria vs medida en alfa ~ 1
    ax = axes[0, 0]
    a1 = min(keep, key=lambda a: abs(a - 1.0))
    _, c_th, c_me = keep[a1]
    kt = np.arange(c_th.size) - int(np.argmax(np.abs(c_th)))
    km = np.arange(c_me.size) - int(np.argmax(np.abs(c_me)))
    ml, sl, bl = ax.stem(kt, np.abs(c_th) / np.abs(c_th).max(), linefmt="0.35",
                         markerfmt="o", basefmt=" ", label="teorica")
    ml.set_color(c_teo)
    ax.plot(km, np.abs(c_me) / np.abs(c_me).max(), "x", color=c_med, ms=8, mew=1.6,
            label="medida (MC)")
    ax.set_xlim(kt.min() - 1.5, kt.max() + 1.5)
    ax.set_xlabel("k (simbolos respecto al cursor)"); ax.set_ylabel("$|c_k| / |c_0|$")
    ax.set_title(f"Canal a tasa de simbolo, alfa = {a1:g}"); ax.legend(fontsize=8)

    # (b) respuesta en frecuencia a tasa de simbolo para varios alfa
    ax = axes[0, 1]
    f = np.linspace(-0.5, 0.5, 512)
    for i, a in enumerate(sorted(keep)):
        c = keep[a][1]
        H = np.exp(-2j * np.pi * np.outer(f, np.arange(c.size))) @ c
        ax.plot(f, 20 * np.log10(np.abs(H) + 1e-6), lw=1.3,
                color=plt.cm.viridis(i / max(len(keep) - 1, 1)), label=f"alfa = {a:g}")
    ax.set_ylim(-30, 10); ax.set_xlabel("f / Rs"); ax.set_ylabel("$|C(f)|$ [dB]")
    ax.set_title("Nulos selectivos del canal"); ax.legend(fontsize=7)

    # (c) SIR
    ax = axes[0, 2]
    ax.plot(x, df["sir_teo_db"], "-", color=c_teo, label="teorica")
    ax.plot(x, df["sir_med_db"], "o", color=c_med, ms=4.5, label="medida")
    marca_h(ax)
    ax.set_xlabel("alfa (escala de los ecos)"); ax.set_ylabel("SIR [dB]")
    ax.set_ylim(min(-3, np.nanmin(df["sir_teo_db"][np.isfinite(df["sir_teo_db"])]) - 2), 45)
    ax.set_title("Relacion senal / ISI"); ax.legend(fontsize=8)

    # (d) distorsion de pico
    ax = axes[1, 0]
    ax.plot(x, df["D_teo"], "-", color=c_teo, label="teorica")
    ax.plot(x, df["D_med"], "o", color=c_med, ms=4.5, label="medida")
    ax.axhline(1.0, color="0.5", ls=":", lw=1)
    ax.text(x.min(), 1.02, "D = 1: ojo cerrado", fontsize=7, color="0.4", va="bottom")
    marca_h(ax)
    ax.set_xlabel("alfa"); ax.set_ylabel("D = $\\sum|c_k| / |c_0|$")
    ax.set_title("Distorsion de pico"); ax.legend(fontsize=8)

    # (e) apertura del ojo
    ax = axes[1, 1]
    ax.plot(x, df["ojo_peor_teo"], "-", color=c_teo, label="peor caso (teorica)")
    ax.plot(x, df["ojo_peor_med"], "o", color=c_med, ms=4.5, label="peor caso observado")
    ax.axhline(0.0, color="0.5", ls=":", lw=1)
    marca_h(ax)
    ax.set_xlabel("alfa"); ax.set_ylabel("apertura normalizada")
    ax.set_title(f"Apertura del ojo, Eb/N0 = {args.ebn0_medida:g} dB"); ax.legend(fontsize=8)

    # (f) BER
    ax = axes[1, 2]
    bits = float(df["bits"].iloc[0])
    plots.ber_with_floor(ax, x, df["ber_sin_eq"], bits, label="sin ecualizar",
                         color=plots.COLORS["none"])
    plots.ber_with_floor(ax, x, df[f"ber_{args.eq}"], bits, label=args.eq.upper(),
                         color=plots.COLORS.get(args.eq))
    ax.set_yscale("log"); marca_h(ax)
    ax.set_xlabel("alfa"); ax.set_ylabel("BER")
    ax.set_title(f"BER a Eb/N0 = {args.ebn0:g} dB (hueco: sin errores, cota)")
    ax.legend(fontsize=8)

    fig.suptitle(f"Experimento 7 - ISI frente al canal h = [{format_taps(h0)}] "
                 f"(paso {args.espaciado:g} T); linea discontinua: h dado (alfa = 1)")
    plots.save_fig(fig, args.nombre)

    # ---------------------------------------------- ojos a varios alfa
    fig, axes = plt.subplots(1, len(keep), figsize=(3.5 * len(keep), 3.4),
                             sharey=True, constrained_layout=True, squeeze=False)
    for ax, a in zip(axes[0], sorted(keep)):
        r, c_th, _ = keep[a]
        m = metrics.isi_metrics(c_th)
        plots.eye(ax, eye_window(r, p), p.sps, n_traces=250,
                  title=f"alfa = {a:g}\nSIR = {m['sir_db']:.1f} dB, D = {m['peak_distortion']:.2f}")
    fig.suptitle(f"Experimento 7 - Cierre del ojo, Eb/N0 = {args.ebn0_medida:g} dB")
    plots.save_fig(fig, f"{args.nombre}_ojos")


if __name__ == "__main__":
    main()

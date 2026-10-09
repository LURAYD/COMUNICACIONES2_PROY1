"""Diagrama de bloques del sistema (Requisito 4, producto de la semana 1).

Genera results/figures/diagrama_bloques.png con la cadena completa
transmisor - canal - receptor, anotando en cada bloque el parametro de diseno
que lo caracteriza y el modulo de `comm2` que lo implementa.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from _common import BASE, banner, plots

TX = "#1f77b4"
CH = "#d62728"
RX = "#2ca02c"


def caja(ax, x, y, w, h, titulo, detalle, color, fs=7.4):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
                                linewidth=1.3, edgecolor=color,
                                facecolor=color, alpha=0.10, zorder=2))
    ax.text(x + w / 2, y + h * 0.70, titulo, ha="center", va="center",
            fontsize=fs + 0.8, fontweight="bold", zorder=3)
    ax.text(x + w / 2, y + h * 0.30, detalle, ha="center", va="center",
            fontsize=fs - 1.0, color="0.25", zorder=3, linespacing=1.35)


def flecha(ax, x0, y0, x1, y1, color="0.35", style="-|>", lw=1.2, rad=0.0):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style,
                                 mutation_scale=11, linewidth=lw, color=color,
                                 connectionstyle=f"arc3,rad={rad}", zorder=1))


def main():
    banner("DIAGRAMA DE BLOQUES DEL SISTEMA")
    plots.setup()
    p = BASE
    fig, ax = plt.subplots(figsize=(15.5, 8.2))
    ax.set_xlim(0, 100); ax.set_ylim(0, 56)
    ax.axis("off")

    W, H = 14.2, 7.4

    # ------------------------------------------------------------ TRANSMISOR
    ax.text(2, 53.4, "TRANSMISOR", fontsize=11, fontweight="bold", color=TX)
    fila = 44.5
    bloques_tx = [
        ("Generacion de bits", f"PRBS reproducible\n{p.n_payload} simbolos utiles\ncomm2.frame"),
        ("Construccion de trama", f"[ZC | ZC] {2*p.zc_len} + entren. {p.n_train}\nZadoff-Chu CAZAC\ncomm2.frame"),
        ("Mapeo Gray", f"QPSK + 16-QAM\n$E\\{{|s|^2\\}}$ = 1\ncomm2.modulation"),
        ("Conformacion RRC", f"$\\beta$ = {p.beta}, {p.span} simbolos\n{p.sps} muestras/simbolo\ncomm2.pulse"),
    ]
    xs = [2, 20, 38, 56]
    for x, (t, d) in zip(xs, bloques_tx):
        caja(ax, x, fila, W, H, t, d, TX)
    for x in xs[:-1]:
        flecha(ax, x + W, fila + H / 2, x + 18, fila + H / 2)

    # ----------------------------------------------------------------- CANAL
    ax.text(76, 53.4, "CANAL", fontsize=11, fontweight="bold", color=CH)
    caja(ax, 74, fila - 1.6, W, H + 3.2, "Canal inalambrico",
         "FIR multitrayectoria\n$\\tau_{rms}$ = 0 ... 1.15 T\nAWGN, CFO, fase,\n"
         "temporizacion, Rayleigh\ncomm2.channel", CH)
    flecha(ax, xs[-1] + W, fila + H / 2, 74, fila + H / 2)

    # bajada al receptor
    flecha(ax, 81, fila, 81, 36.5, color="0.35")

    # ------------------------------------------------------------- RECEPTOR
    ax.text(2, 33.6, "RECEPTOR ADAPTATIVO", fontsize=11, fontweight="bold", color=RX)

    fila2 = 25.5
    bloques_rx1 = [
        ("Filtro adaptado", "RRC identico al TX\n(matched filter)\ncomm2.pulse"),
        ("Deteccion + CFO grueso", f"Schmidl-Cox sobre [ZC|ZC]\nrango $\\pm R_s/(2L)$ = $\\pm${p.rs/(2*p.zc_len):.0f} Hz\ncomm2.sync"),
        ("Temporizacion (Gardner)", "TED no asistido por decision\ninterpolador cubico\n$B_nT$ = 0.02\ncomm2.sync"),
        ("Sincronismo de trama", "Correlacion con la\nsecuencia de entrenamiento\ncomm2.sync"),
    ]
    xs2 = [74, 56, 38, 20]
    for x, (t, d) in zip(xs2, bloques_rx1):
        caja(ax, x, fila2, W, H, t, d, RX)
    for x in xs2[:-1]:
        flecha(ax, x, fila2 + H / 2, x - 3.8, fila2 + H / 2)

    flecha(ax, 27, fila2, 27, 18.0, color="0.35")

    fila3 = 7.0
    bloques_rx2 = [
        ("Ecualizacion", "Metodo A: LMS  $O(N)$\nMetodo B: RLS  $O(N^2)$\n(+ ZF / MMSE / CMA)\nN = 21 taps\ncomm2.equalizers"),
        ("PLL de fase", "Dirigido por decision\n$B_nT$ = 5e-4, sembrado con\nCFO residual post-ecualizador\ncomm2.sync"),
        ("Demodulacion", "Decision por minima\ndistancia (Gray)\ncomm2.modulation"),
        ("Metricas", "BER, SER, EVM, MSE,\nPSD, ojo, convergencia\ncomm2.metrics"),
    ]
    xs3 = [20, 38, 56, 74]
    for x, (t, d) in zip(xs3, bloques_rx2):
        caja(ax, x, fila3, W, H + 1.2, t, d, RX)
    for x in xs3[:-1]:
        flecha(ax, x + W, fila3 + (H + 1.2) / 2, x + 18, fila3 + (H + 1.2) / 2)

    # realimentaciones: cada bloque se realimenta con SUS decisiones. No hay
    # lazo del PLL al ecualizador: link.py ejecuta el ecualizador completo y
    # despues el PLL sobre su salida (antes se dibujaba una flecha PLL -> ecualizador).
    top = fila3 + H + 1.2
    for x0 in (xs3[0], xs3[1]):
        # a la derecha de la caja: en el centro baja la flecha del sincronismo
        ax.annotate("", xy=(x0 + 0.62 * W, top), xytext=(x0 + 0.95 * W, top),
                    arrowprops=dict(arrowstyle="-|>", color="#999", lw=1.0,
                                    connectionstyle="arc3,rad=0.9", ls="--"))
        ax.text(x0 + 0.785 * W, top + 3.4, "sus decisiones", fontsize=6.6,
                color="#666", ha="center", style="italic")

    # nota lateral
    ax.text(2, 18.0,
            "Orden justificado en docs/arquitectura.md:\n"
            "Schmidl-Cox va primero porque es no coherente\n"
            "y no necesita temporizacion; Gardner tolera el\n"
            "CFO residual; el ecualizador se entrena antes de\n"
            "cerrar el PLL para que este arranque sin ISI.",
            fontsize=6.8, color="0.3", va="top", linespacing=1.5,
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#f4f4f4",
                      edgecolor="0.8", linewidth=0.8))

    ax.text(2, 1.5, f"Comunicaciones II 2026 - Proyecto 1   |   {p.summary()}",
            fontsize=7.5, color="0.35")

    fig.suptitle("Receptor digital adaptativo sobre canal inalambrico simulado - diagrama de bloques",
                 fontsize=12.5, y=0.985)
    path = plots.save_fig(fig, "diagrama_bloques")
    print(f"  -> {path}")
    return path


if __name__ == "__main__":
    main()

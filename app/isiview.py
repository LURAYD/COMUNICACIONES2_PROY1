"""Vista «ISI y ecualizador»: canal ideal frente a canal h, con y sin ecualizar.

La pregunta que responde: ¿qué hace el ecualizador? Deshace la ISI; no quita
ruido. Para verlo se simulan cuatro enlaces con los MISMOS datos y el MISMO
ruido (`engine.compare_isi`): canal ideal y canal h, cada uno sin ecualizar y
con el ecualizador del rail. Todo sale de `run_link`, igual que en el banco.

Lo que se lee en pantalla:

- **Arriba**, las tres constelaciones: ideal (solo ruido), h sin ecualizar
  (ruido + ISI) y h ecualizado. Al cambiar de canal los puntos se desplazan
  índice a índice, porque los símbolos transmitidos son los mismos.
- **Abajo**, el mecanismo: el canal y el canal * ecualizador (casi un impulso),
  sus respuestas en frecuencia (donde el canal cae, el ecualizador sube) y el
  error de cada enlace repartido en ISI y ruido.
- **La barra inferior** pone las SNR efectivas junto a sus dos cotas: el canal
  ideal (techo absoluto) y el mejor ecualizador lineal posible para este h.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QSizePolicy, QVBoxLayout,
                               QWidget)

from . import theme as T
from .bench import StatusDot, fmt_ber
from .displays import Constellation, _label, _plot
from .engine import SYMBOL, IsiResult
from .widgets import Panel, Readout, panel_label, text_label

STORY = ("El ecualizador existe para deshacer la ISI, no para quitar ruido. Aquí se "
         "comparan, con los mismos datos y el mismo ruido, el canal ideal y el canal h, "
         "sin ecualizar y con el ecualizador del rail. Escenario B sin sincronismo de "
         "portadora: no hay offset que corregir, así que todo lo que se ve es ISI y ruido.")


def _host(w: QWidget) -> QWidget:
    """Mismo margen interior que los instrumentos del banco."""
    holder = QWidget()
    v = QVBoxLayout(holder)
    v.setContentsMargins(6, 4, 6, 6)
    v.setSpacing(0)
    v.addWidget(w)
    return holder


def _no_si(pi) -> None:
    """Ejes en unidades propias (Rs, dB, símbolos): sin prefijo SI automático.
    Sin esto pyqtgraph rotula ±0,5 Rs como «±500 (x0.001)»."""
    for name in ("left", "bottom"):
        pi.getAxis(name).enableAutoSIPrefix(False)


def _legend(pi, offset=(-8, 8)):
    return pi.addLegend(offset=offset, labelTextColor=T.INK_DIM, labelTextSize="8pt",
                        brush=pg.mkBrush(T.rgba(T.PANEL, 0.9)), pen=pg.mkPen(T.RULE))


# ---------------------------------------------------------------------------
# Instrumentos
# ---------------------------------------------------------------------------

class Stems(QWidget):
    """Canal y canal * ecualizador a tasa de símbolo, normalizados al cursor."""

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        self.plot = _plot()
        self.pi = self.plot.getPlotItem()
        _label(self.pi, "|coeficiente| / cursor", "k  [símbolos respecto al cursor]")
        _no_si(self.pi)
        v.addWidget(self.plot)
        self.leg = _legend(self.pi, offset=(8, 8))
        self.items = {}
        for key, col in (("c", T.S2), ("q", T.INK)):
            ln = pg.PlotCurveItem(pen=pg.mkPen(col, width=2.2), connect="pairs")
            dot = pg.ScatterPlotItem(size=8, pen=pg.mkPen(T.PANEL, width=1.2),
                                     brush=pg.mkBrush(col))
            self.pi.addItem(ln)
            self.pi.addItem(dot)
            self.items[key] = (ln, dot)
        self.pi.addItem(pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen(T.RULE_STRONG)))

    def show(self, c: np.ndarray, q: np.ndarray, eq_name: str) -> None:
        self.leg.clear()
        lo, hi = 0, 0
        for key, v, dx, name in (("c", c, -0.13, "canal h"),
                                 ("q", q, 0.13, f"canal * {eq_name}" if eq_name else "")):
            ln, dot = self.items[key]
            if not name or v is None or not np.size(v):
                ln.setData([], [])
                dot.setData([], [])
                continue
            a = np.abs(v) / (np.abs(v).max() + 1e-12)
            k = np.arange(v.size) - int(np.argmax(a))
            keep = a > 0.02                     # colas despreciables fuera
            k, a = k[keep], a[keep]
            x = np.repeat(k + dx, 2)
            y = np.column_stack([np.zeros_like(a), a]).ravel()
            ln.setData(x, y)
            dot.setData(k + dx, a)
            self.leg.addItem(dot, name)
            lo, hi = min(lo, k.min()), max(hi, k.max())
        self.pi.setXRange(lo - 0.8, hi + 0.8, padding=0)
        self.pi.setYRange(-0.03, 1.12, padding=0)


class Freq(QWidget):
    """|C(f)|, |F(f)| y |C·F|: el ecualizador como inverso del canal."""

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        self.plot = _plot()
        self.pi = self.plot.getPlotItem()
        _label(self.pi, "dB", "frecuencia [Rs]")
        _no_si(self.pi)
        v.addWidget(self.plot)
        self.pi.addItem(pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen(
            T.INK_GHOST, width=1, style=Qt.PenStyle.DashLine)))
        self.C = pg.PlotCurveItem(pen=pg.mkPen(T.S2, width=1.8))
        self.F = pg.PlotCurveItem(pen=pg.mkPen(T.S1, width=1.8))
        self.Q = pg.PlotCurveItem(pen=pg.mkPen(T.INK, width=1.8))
        for c in (self.C, self.F, self.Q):
            self.pi.addItem(c)
        self.leg = _legend(self.pi, offset=(-8, -8))
        self.pi.setXRange(-0.5, 0.5, padding=0)
        # hueco abajo para la leyenda: los nulos del canal llegan a ~-15 dB
        self.pi.setYRange(-42, 15, padding=0)

    def show(self, res: IsiResult) -> None:
        self.leg.clear()
        self.C.setData(res.freq, res.C_db)
        self.leg.addItem(self.C, "canal  |C|")
        if res.eq_name:
            self.F.setData(res.freq, res.F_db)
            self.Q.setData(res.freq, res.Q_db)
            self.leg.addItem(self.F, f"{res.eq_name}  |F|")
            self.leg.addItem(self.Q, "conjunto  |C·F|")
        else:
            self.F.setData([], [])
            self.Q.setData([], [])


class Breakdown(QWidget):
    """Error de cada enlace repartido en ISI residual y ruido.

    Diagrama de puntos, no barras apiladas: las dos componentes difieren en
    decenas de dB y solo en escala logarítmica se leen juntas.
    """

    ROWS = (("ideal", "none"), ("ideal", "eq"), ("h", "none"), ("h", "eq"))

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        self.plot = _plot()
        self.pi = self.plot.getPlotItem()
        _label(self.pi, "", "potencia respecto a la señal útil [dB]")
        _no_si(self.pi)
        self.pi.getAxis("left").setWidth(172)
        self.pi.showGrid(x=True, y=False, alpha=0.12)
        # La leyenda va encima del lienzo, no dentro: dentro tapaba los puntos
        # del canal h, que son justo los que hay que leer.
        # Muestras de color como bloques, no como glifos: IBM Plex no trae
        # ● ■ ✕ y Qt los pintaba como cajas vacias.
        def chip(col):
            return f"<span style='background:{col}'>&nbsp;&nbsp;&nbsp;</span>"
        key = text_label(
            f"{chip(T.S2)} ISI residual&nbsp;&nbsp;&nbsp;&nbsp;"
            f"{chip(T.INK_FAINT)} ruido&nbsp;&nbsp;&nbsp;&nbsp;"
            f"<b style='color:{T.INK}'>x</b> error total medido",
            T.f_small(), T.INK_DIM)
        key.setContentsMargins(8, 4, 0, 2)
        v.addWidget(key)
        v.addWidget(self.plot)
        self.guides = pg.PlotCurveItem(pen=pg.mkPen(T.RULE, width=1), connect="pairs")
        self.pi.addItem(self.guides)
        self.isi = pg.ScatterPlotItem(size=11, symbol="o", brush=pg.mkBrush(T.S2),
                                      pen=pg.mkPen(T.PANEL, width=1.5))
        self.noise = pg.ScatterPlotItem(size=10, symbol="s",
                                        brush=pg.mkBrush(T.INK_FAINT),
                                        pen=pg.mkPen(T.PANEL, width=1.5))
        self.total = pg.ScatterPlotItem(size=11, symbol="x", brush=pg.mkBrush(T.INK),
                                        pen=pg.mkPen(T.INK, width=1.2))
        for it in (self.isi, self.noise, self.total):
            self.pi.addItem(it)

    def show(self, res: IsiResult) -> None:
        eq = res.req.eq_kind
        rows = []
        for c, r in self.ROWS:
            k = (c, eq if r == "eq" else "none")
            if k in res.links and k not in rows:   # eq "none": ("ideal","eq") repetiria
                rows.append(k)
        # sin ecualizador en el rail solo hay dos filas: no se inventan las otras
        ys, isi, noise, tot, ticks = [], [], [], [], []
        name = res.eq_name or "sin ecualizar"
        for i, (canal, rx) in enumerate(rows):
            y = len(rows) - 1 - i
            lv = res.links[(canal, rx)]
            ys.append(y)
            isi.append(lv.isi_db)
            noise.append(lv.noise_db)
            tot.append(lv.mse_db)
            rx_txt = "sin ecualizar" if rx == "none" else name
            ticks.append((y, f"{'ideal' if canal == 'ideal' else 'h'} · {rx_txt}"))
        lo = -45.0
        self.isi.setData([max(v, lo) for v in isi], ys)
        self.noise.setData(noise, ys)
        self.total.setData(tot, ys)
        gx = np.repeat([[lo, 2.0]], len(ys), axis=0).ravel()
        gy = np.repeat(ys, 2)
        self.guides.setData(gx, gy)
        self.pi.getAxis("left").setTicks([ticks])
        self.pi.setXRange(lo, 2, padding=0)
        self.pi.setYRange(-0.6, len(rows) - 0.4, padding=0)


# ---------------------------------------------------------------------------
# Vista
# ---------------------------------------------------------------------------

class IsiView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.res: Optional[IsiResult] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        center = QWidget()
        cv = QVBoxLayout(center)
        cv.setContentsMargins(18, 16, 18, 16)
        cv.setSpacing(12)

        # -- el canal h y la lectura ------------------------------------------
        cap = QWidget()
        ch = QHBoxLayout(cap)
        ch.setContentsMargins(2, 0, 2, 0)
        ch.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(3)
        left.addWidget(panel_label("Canal h", T.SIGNAL))
        self.h_text = text_label("", T.font(11, 500, mono=True), T.INK)
        left.addWidget(self.h_text)
        self.h_meta = text_label("", T.f_small(), T.INK_DIM)
        left.addWidget(self.h_meta)
        ch.addLayout(left, 0)
        story = text_label(STORY, T.f_body(), T.INK_DIM, wrap=True)
        # Altura fija e independiente del ancho: un QLabel con wordWrap trae
        # altura-para-ancho y, junto al aspecto bloqueado de las constelaciones,
        # el maquetado oscilaba para siempre (cuelgue a ciertos tamanos).
        pol = story.sizePolicy()
        pol.setHeightForWidth(False)
        pol.setVerticalPolicy(QSizePolicy.Policy.Fixed)
        story.setSizePolicy(pol)
        story.setFixedHeight(story.fontMetrics().lineSpacing() * 4 + 4)
        story.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        ch.addWidget(story, 1)
        cv.addWidget(cap)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        self.const = {}
        self.p_const = {}
        for j, (key, title) in enumerate((("ideal", "Canal ideal  ·  sin ecualizar"),
                                          ("h", "Canal h  ·  sin ecualizar"),
                                          ("heq", "Canal h  ·  ecualizado"))):
            p = Panel(title)
            c = Constellation()
            p.set_content(c)
            grid.addWidget(p, 0, j)
            self.const[key] = c
            self.p_const[key] = p

        self.p_stems = Panel("Respuesta al impulso")
        self.stems = Stems()
        self.p_stems.set_content(_host(self.stems))
        self.p_freq = Panel("Respuesta en frecuencia")
        self.freq = Freq()
        self.p_freq.set_content(_host(self.freq))
        self.p_break = Panel("¿De qué está hecho el error?")
        self.brk = Breakdown()
        self.p_break.set_content(_host(self.brk))
        grid.addWidget(self.p_stems, 1, 0)
        grid.addWidget(self.p_freq, 1, 1)
        grid.addWidget(self.p_break, 1, 2)
        for j in range(3):
            grid.setColumnStretch(j, 1)
        grid.setRowStretch(0, 3)
        grid.setRowStretch(1, 2)
        cv.addLayout(grid, 1)
        root.addWidget(center, 1)

        # -- barra de SNR: medidas junto a sus cotas ---------------------------
        bar = QWidget()
        bar.setObjectName("ReadoutBar")
        bh = QHBoxLayout(bar)
        bh.setContentsMargins(20, 12, 20, 13)
        bh.setSpacing(0)
        self.r_ceiling = Readout("Techo · canal ideal", "dB", large=True,
                                 tip="Es/N0: la SNR del canal sin ISI. Ningún\n"
                                     "receptor lineal la supera con ningún canal.")
        self.r_bound = Readout("Límite ecualizador lineal", "dB",
                               tip="Lo mejor que puede hacer CUALQUIER ecualizador\n"
                                   "lineal (MMSE con infinitos taps) con este h.\n"
                                   "La distancia al techo es el precio de la ISI.")
        self.r_eq = Readout("h ecualizado", "dB",
                            tip="SNR efectiva medida (1/EVM²) a la salida del\n"
                                "ecualizador del rail sobre el canal h.")
        self.r_raw = Readout("h sin ecualizar", "dB",
                             tip="SNR efectiva sin ecualizar. Con Eb/N0 alto se\n"
                                 "aplana en la SIR del canal: subir potencia no\n"
                                 "arregla la ISI.")
        self.r_gain = Readout("Ganancia de ruido", "dB",
                              tip="Σ|f|² del ecualizador. Positiva: amplifica el\n"
                                  "ruido donde el canal tiene nulos.")
        items = (self.r_ceiling, self.r_bound, self.r_eq, self.r_raw, self.r_gain)
        for i, r in enumerate(items):
            if i:
                sep = QWidget()
                sep.setFixedWidth(1)
                sep.setStyleSheet(f"background: {T.RULE_STRONG};")
                bh.addSpacing(14)
                bh.addWidget(sep)
                bh.addSpacing(14)
            bh.addWidget(r)
        bh.addStretch(1)
        self.status = StatusDot()
        bh.addWidget(self.status, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(bar)

    # -- ciclo ---------------------------------------------------------------
    def set_busy(self, busy: bool) -> None:
        if busy:
            self.status.set_state("busy")
        elif self.res is not None:
            self.status.set_state("locked" if self._all_locked() else "unlock")

    def set_error(self, msg: str) -> None:
        self.status.set_state("error", msg[:70])

    def _all_locked(self) -> bool:
        return all(lv.locked for lv in self.res.links.values())

    def apply(self, res: IsiResult) -> None:
        first = self.res is None
        self.res = res
        eqn = res.eq_name
        eq = res.req.eq_kind

        self.h_text.setText(res.h_text)
        D = res.peak_distortion
        estado = ("ojo cerrado sin ecualizar" if D > 1.005 else
                  "ojo justo en el límite" if D >= 0.995 else "ojo abierto sin ecualizar")
        sir = "∞" if not math.isfinite(res.sir_db) else f"{res.sir_db:.1f}"
        self.h_meta.setText(f"SIR {sir} dB   ·   distorsión de pico D = {D:.2f}   ·   {estado}")

        # misma escala en las tres: si no, la comparación visual engaña
        allp = np.concatenate([lv.pts for lv in res.links.values()])
        panels = (("ideal", ("ideal", "none")), ("h", ("h", "none")),
                  ("heq", ("h", eq)))
        for key, lk in panels:
            c, p = self.const[key], self.p_const[key]
            c.set_reference(res.ideal)
            c.autoscale(allp)
            lv = res.links.get(lk) if (key != "heq" or eqn) else None
            if key == "heq":
                p.set_title(f"Canal h  ·  {eqn}" if eqn else "Canal h  ·  ecualizado")
            if lv is None:
                c.show_tap(np.array([], complex), SYMBOL, animate=False)
                p.set_note("elige un ecualizador en el rail", T.INK_FAINT)
                continue
            c.show_tap(lv.pts, SYMBOL, animate=not first)
            txt, cota = fmt_ber(lv.ber, lv.bits)
            col = T.GOOD if lv.ber < 1e-3 else (T.WARNING if lv.ber < 5e-2 else T.CRITICAL)
            p.set_note(f"BER {txt}{' (cota)' if cota else ''}   ·   EVM {lv.evm:.1f} %", col)

        self.stems.show(res.c, res.q, eqn)
        self.freq.show(res)
        self.brk.show(res)
        self.p_stems.set_note("canal medido sobre la señal recibida")
        self.p_freq.set_note(f"ganancia de ruido {res.noise_gain_db:+.1f} dB" if eqn
                             else "sin ecualizador")
        self.p_break.set_note(f"Eb/N0 = {res.req.ebn0_db:.1f} dB")

        self.r_ceiling.set(f"{res.esn0_db:.1f}", T.INK)
        self.r_bound.set(f"{res.bound_db:.1f}", T.INK_DIM)
        heq = res.links.get(("h", eq)) if eqn else None
        self.r_eq.set(f"{heq.snr_db:.1f}" if heq else "--", T.INK if heq else T.INK_GHOST)
        self.r_eq.name.setText(f"h + {eqn}" if eqn else "h ecualizado")
        self.r_raw.set(f"{res.links[('h', 'none')].snr_db:.1f}", T.INK)
        self.r_gain.set(f"{res.noise_gain_db:+.1f}" if eqn else "--",
                        T.INK if eqn else T.INK_GHOST)
        self.status.set_state("locked" if self._all_locked() else "unlock")

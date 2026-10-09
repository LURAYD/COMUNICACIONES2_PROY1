"""Los cuatro instrumentos: constelacion, ojo, espectro y convergencia.

Dos decisiones de dibujo que no son decorativas.

**El morfeo de la constelacion.** Los cinco puntos a tasa de simbolo contienen
los MISMOS simbolos, indice a indice. Al cambiar de etapa, cada punto se
interpola desde su posicion anterior hasta la nueva: se ve el simbolo k salir
del borron de ISI y aterrizar en su punto de la constelacion. Entre puntos que
no se corresponden (sobremuestreado frente a tasa de simbolo) no hay morfeo
posible y se hace un fundido, que es lo honesto.

**El fosforo del ojo.** Las trazas se dibujan superpuestas con alfa baja, de
modo que el brillo se acumula donde muchas trazas coinciden. No es un efecto
anadido: es como funciona una pantalla de fosforo, y por eso el instante de
muestreo aparece solo, sin tener que senalarlo.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QEasingCurve, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QPen
from PySide6.QtWidgets import QVBoxLayout, QWidget

from . import theme as T
from .engine import STAGE_BY_KEY, SYMBOL, SimResult

pg.setConfigOptions(antialias=True, useOpenGL=False)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

def _plot() -> pg.PlotWidget:
    """Lienzo con la piel del instrumento aplicada, ejes incluidos."""
    w = pg.PlotWidget(background=T.PANEL)
    pi = w.getPlotItem()
    pi.setMenuEnabled(False)
    pi.hideButtons()
    pi.showGrid(x=True, y=True, alpha=0.12)
    pi.setContentsMargins(2, 6, 10, 2)

    axis_font = QFont(T.MONO)
    axis_font.setPointSizeF(8.0)
    for name in ("left", "bottom"):
        ax = pi.getAxis(name)
        ax.setPen(pg.mkPen(T.RULE_STRONG, width=1))
        ax.setTextPen(pg.mkPen(T.INK_FAINT))
        ax.setTickFont(axis_font)
        ax.setStyle(tickLength=-3, tickTextOffset=5)
    for name in ("right", "top"):
        pi.showAxis(name)
        ax = pi.getAxis(name)
        ax.setPen(pg.mkPen(T.RULE_STRONG, width=1))
        ax.setStyle(showValues=False, tickLength=0)
    return w


def _label(pi, left: str = "", bottom: str = "") -> None:
    style = {"color": T.INK_FAINT, "font-size": "8pt", "font-family": T.SANS}
    if left:
        pi.setLabel("left", left, **style)
    if bottom:
        pi.setLabel("bottom", bottom, **style)


class Display(QWidget):
    """Contenedor comun: un lienzo y una nota con la medida de ese panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 4, 6, 6)
        v.setSpacing(0)
        self.plot = _plot()
        v.addWidget(self.plot)
        self.pi = self.plot.getPlotItem()
        self.note = ""
        self.title = ""


# ---------------------------------------------------------------------------
# Constelacion
# ---------------------------------------------------------------------------

MORPH_MS = 460
FRAME_MS = 16


class Constellation(Display):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pi.setAspectLocked(True)
        # Ejes de tamano fijo: con el aspecto bloqueado, el ancho de los rotulos
        # cambia el area util, esta cambia el rango y el rango cambia los
        # rotulos; en la rejilla de 3 constelaciones eso no convergia nunca.
        self.pi.getAxis("left").setWidth(34)
        self.pi.getAxis("bottom").setHeight(30)
        self.pi.setXRange(-1.75, 1.75, padding=0)
        self.pi.setYRange(-1.75, 1.75, padding=0)
        _label(self.pi, "Q", "I")

        # ejes por el origen: la constelacion se lee respecto a ellos
        for ang in (0, 90):
            ln = pg.InfiniteLine(pos=0, angle=ang,
                                 pen=pg.mkPen(T.INK_GHOST, width=1))
            ln.setZValue(-10)
            self.pi.addItem(ln)

        self.ref = pg.ScatterPlotItem(size=11, symbol="+", pxMode=True,
                                      pen=pg.mkPen(T.REFERENCE, width=1.3),
                                      brush=None)
        self.ref.setZValue(5)
        self.pi.addItem(self.ref)

        # Dos capas del mismo dato: halo ancho y difuso + nucleo fino. Asi la
        # densidad de simbolos se lee como brillo, igual que en un fosforo.
        self.halo = pg.ScatterPlotItem(size=7, pxMode=True, pen=None,
                                       brush=T.rgba(T.SIGNAL, T.HALO_ALPHA))
        self.core = pg.ScatterPlotItem(size=2.4, pxMode=True, pen=None,
                                       brush=T.rgba(T.SIGNAL_HI, T.CORE_ALPHA))
        self.halo.setZValue(1)
        self.core.setZValue(2)
        self.pi.addItem(self.halo)
        self.pi.addItem(self.core)

        self._from: Optional[np.ndarray] = None
        self._to: Optional[np.ndarray] = None
        self._kind_from = ""
        self._kind_to = ""
        self._t = 1.0
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._step)
        self._ease = QEasingCurve(QEasingCurve.Type.OutExpo)

    def set_reference(self, pts: np.ndarray) -> None:
        self.ref.setData(x=np.real(pts), y=np.imag(pts))

    def show_tap(self, pts: np.ndarray, kind: str, animate: bool = True) -> None:
        pts = np.asarray(pts)
        if self._to is None or not animate:
            self._from = self._to = pts
            self._t = 1.0
            self._draw(pts, 1.0)
            self._kind_to = kind
            return

        morphable = (kind == SYMBOL and self._kind_to == SYMBOL
                     and self._to.size == pts.size)
        self._from = self._to if morphable else None
        self._to = pts
        self._kind_from, self._kind_to = self._kind_to, kind
        self._t = 0.0
        self._timer.start()

    def _step(self) -> None:
        self._t = min(1.0, self._t + FRAME_MS / MORPH_MS)
        e = self._ease.valueForProgress(self._t)
        if self._from is not None:
            # morfeo posicional: cada simbolo viaja a su posicion corregida
            cur = self._from + (self._to - self._from) * e
            self._draw(cur, 1.0)
        else:
            # sin correspondencia entre puntos: fundido
            self._draw(self._to, e)
        if self._t >= 1.0:
            self._timer.stop()
            self._from = None

    def _draw(self, pts: np.ndarray, alpha: float) -> None:
        x, y = np.real(pts), np.imag(pts)
        self.halo.setBrush(T.rgba(T.SIGNAL, T.HALO_ALPHA * alpha))
        self.core.setBrush(T.rgba(T.SIGNAL_HI, T.CORE_ALPHA * alpha))
        self.halo.setData(x=x, y=y)
        self.core.setData(x=x, y=y)

    def autoscale(self, pts: np.ndarray) -> None:
        m = float(np.percentile(np.abs(pts), 99.5)) if pts.size else 1.5
        m = max(1.4, min(4.0, m * 1.25))
        self.pi.setXRange(-m, m, padding=0)
        self.pi.setYRange(-m, m, padding=0)


# ---------------------------------------------------------------------------
# Diagrama de ojo
# ---------------------------------------------------------------------------

EYE_UPSAMPLE = 4
EYE_W, EYE_H = 420, 240     # resolucion de la imagen de densidad del ojo
EYE_SUB = 3                 # subpasos por columna: rellena los flancos empinados


def _eye_density(t: np.ndarray, seg: np.ndarray, lim: float) -> np.ndarray:
    """Histograma 2D de las trazas del ojo, como imagen RGBA [x, y].

    Es lo mismo que hace una pantalla de fosforo: el brillo de cada pixel es
    cuantas trazas pasan por el. Pintarlo como imagen cuesta milisegundos; las
    300 trazas con pincel ancho y alfa costaban ~0,7 s por ojo en QPainter.
    """
    from scipy.ndimage import gaussian_filter

    n_col = EYE_W * EYE_SUB
    pos = np.linspace(0.0, t.size - 1.0, n_col)
    i0 = np.minimum(pos.astype(int), t.size - 2)
    fr = pos - i0
    y = seg[:, i0] * (1.0 - fr) + seg[:, i0 + 1] * fr          # (trazas, n_col)
    yi = np.clip(((y + lim) / (2 * lim) * EYE_H).astype(int), 0, EYE_H - 1)
    xi = np.broadcast_to(np.arange(n_col) // EYE_SUB, yi.shape)
    hist = np.bincount((xi * EYE_H + yi).ravel(),
                       minlength=EYE_W * EYE_H).reshape(EYE_W, EYE_H).astype(float)

    # nucleo nitido + halo difuso, como las dos capas de la constelacion
    core = hist / (hist.max() + 1e-12)
    bloom = gaussian_filter(hist, 2.2)
    bloom /= bloom.max() + 1e-12
    d = np.clip(0.85 * core ** 0.55 + 0.45 * bloom ** 0.7, 0.0, 1.0)

    # Color del ojo: T.EYE (rojo en claro, amarillo en oscuro); la densidad va en el alfa.
    lo, hi = QColor(T.EYE), QColor(T.EYE)
    c0 = np.array([lo.red(), lo.green(), lo.blue()], float)
    c1 = np.array([hi.red(), hi.green(), hi.blue()], float)
    rgba = np.empty((EYE_W, EYE_H, 4), np.uint8)
    rgba[..., :3] = (c0 + (c1 - c0) * d[..., None]).astype(np.uint8)
    rgba[..., 3] = (255 * d).astype(np.uint8)
    return rgba


class Eye(Display):
    def __init__(self, parent=None):
        super().__init__(parent)
        _label(self.pi, "amplitud (I)", "tiempo [T]")
        self.pi.setXRange(-1, 1, padding=0)

        # Imagen de densidad en lugar de trazas: ver `_eye_density`.
        self.img = pg.ImageItem(axisOrder="col-major")
        self.img.setZValue(1)
        self.pi.addItem(self.img)

        self.mark = pg.InfiniteLine(pos=0, angle=90,
                                    pen=pg.mkPen(T.INK_FAINT, width=1,
                                                 style=Qt.PenStyle.DashLine))
        self.mark.setZValue(10)
        self.pi.addItem(self.mark)

        self.msg = pg.TextItem("", color=T.INK_FAINT, anchor=(0.5, 0.5))
        self.msg.setFont(T.font(9.5, 400))
        self.pi.addItem(self.msg)
        self.msg.setVisible(False)

    def set_caption(self, text: str, color: Optional[str] = None) -> None:
        """Rotulo sobre el lienzo; vacio lo retira (ojo unico)."""
        if text:
            self.pi.setTitle(text, color=color or T.INK_DIM, size="9pt")
        else:
            self.pi.setTitle(None)

    def show_wave(self, wave: Optional[np.ndarray], sps: int, opening: float) -> None:
        if wave is None:
            self._unavailable("Este punto ya está a tasa de símbolo.\n"
                              "El ojo necesita señal sobremuestreada.")
            return
        from comm2 import metrics
        # Normalizacion a potencia unitaria: la ganancia absoluta depende del
        # filtro y del canal, y sin normalizar el eje vertical acaba en
        # milesimas o en millares y el ojo deja de ser comparable entre etapas.
        wave = np.asarray(wave)
        rms = float(np.sqrt(np.mean(np.abs(wave) ** 2))) + 1e-15
        wave = wave / rms
        # Interpolacion x4 solo para dibujar: con 8 muestras por simbolo cada
        # traza es una quebrada de 16 segmentos y el ojo se ve dentado.
        from scipy.signal import resample_poly
        wave = resample_poly(wave, EYE_UPSAMPLE, 1)
        sps = sps * EYE_UPSAMPLE

        off = metrics.best_sampling_phase(wave, sps)
        # t=0 (la marca) cae en el instante de muestreo optimo: eye_data pone
        # t=0 en el indice sps de cada traza, congruente con `off` modulo sps.
        t, seg = metrics.eye_data(np.real(wave), sps, n_traces=300, span=2,
                                  offset=int(off) % sps)
        if seg.shape[0] == 0:
            self._unavailable("Tramo demasiado corto para trazar el ojo.")
            return

        self._set_axes(True)
        self.msg.setVisible(False)

        lim = float(np.nanpercentile(np.abs(seg), 99.5)) * 1.2 + 1e-9
        self.img.setImage(_eye_density(t, seg, lim), autoLevels=False)
        self.img.setRect(QRectF(float(t[0]), -lim, float(t[-1] - t[0]), 2 * lim))
        self.pi.setYRange(-lim, lim, padding=0)
        self.pi.setXRange(t[0], t[-1], padding=0)
        self.img.setVisible(True)
        self.mark.setVisible(True)

    def _set_axes(self, on: bool) -> None:
        """Un panel sin medida no debe mostrar una rejilla vacia: eso se lee
        como grafica rota. Se retiran los ejes y queda solo el mensaje."""
        self.pi.showGrid(x=on, y=on, alpha=0.12 if on else 0.0)
        for name in ("left", "bottom"):
            self.pi.getAxis(name).setStyle(showValues=on)
        for name in ("left", "bottom", "right", "top"):
            self.pi.getAxis(name).setPen(
                pg.mkPen(T.RULE_STRONG if on else T.PANEL, width=1))
        self.pi.getViewBox().setBackgroundColor(T.PANEL)

    def _unavailable(self, text: str) -> None:
        self.img.setVisible(False)
        self.mark.setVisible(False)
        self._set_axes(False)
        self.msg.setText(text)
        self.msg.setVisible(True)
        self.pi.setXRange(-1, 1, padding=0)
        self.pi.setYRange(-1, 1, padding=0)
        self.msg.setPos(0, 0)


# ---------------------------------------------------------------------------
# Espectro
# ---------------------------------------------------------------------------

class Spectrum(Display):
    def __init__(self, parent=None):
        super().__init__(parent)
        _label(self.pi, "PSD [dB]", "frecuencia [Rs]")
        self.pi.setXRange(-1.5, 1.5, padding=0)
        self.pi.setYRange(-70, 6, padding=0)

        self.tx = pg.PlotCurveItem(pen=pg.mkPen(T.S1, width=1.6))
        self.rx = pg.PlotCurveItem(pen=pg.mkPen(T.S2, width=1.6))
        self.pi.addItem(self.tx)
        self.pi.addItem(self.rx)

        self.band = pg.LinearRegionItem(values=(-0.675, 0.675), movable=False,
                                        brush=T.rgba(T.INK_FAINT, 0.05),
                                        pen=pg.mkPen(T.INK_GHOST, width=1))
        self.band.setZValue(-20)
        self.pi.addItem(self.band)

        self.leg = self.pi.addLegend(offset=(-8, -8), labelTextColor=T.INK_DIM,
                                     labelTextSize="8pt",
                                     brush=pg.mkBrush(T.rgba(T.PANEL, 0.92)),
                                     pen=pg.mkPen(T.RULE))
        self.leg.addItem(self.tx, "transmitido")
        self.leg.addItem(self.rx, "tras el canal")

    def show(self, psd: dict, beta: float, rx: bool = True) -> None:
        """`rx=False` en la seccion de generacion: ahi aun no hay canal."""
        if "rrc" in psd:
            f, y = psd["rrc"]
            self.tx.setData(f, y)
        if "chan" in psd and rx:
            f, y = psd["chan"]
            self.rx.setData(f, y)
        else:
            self.rx.setData([], [])
        self.leg.clear()
        self.leg.addItem(self.tx, "transmitido")
        if rx:
            self.leg.addItem(self.rx, "tras el canal")
        half = (1.0 + beta) / 2.0
        self.band.setRegion((-half, half))


# ---------------------------------------------------------------------------
# Convergencia del ecualizador
# ---------------------------------------------------------------------------

class Convergence(Display):
    def __init__(self, parent=None):
        super().__init__(parent)
        _label(self.pi, "MSE [dB]", "símbolo")

        self.ref = pg.PlotCurveItem(pen=pg.mkPen(T.S2, width=1.4))
        self.cur = pg.PlotCurveItem(pen=pg.mkPen(T.S1, width=1.8))
        self.pi.addItem(self.ref)
        self.pi.addItem(self.cur)

        # Sin `rotateAxis`: el rotulo vertical se recortaba contra el borde
        # del panel y perdia las ultimas letras.
        self.split = pg.InfiniteLine(
            pos=0, angle=90, pen=pg.mkPen(T.INK_GHOST, width=1,
                                          style=Qt.PenStyle.DashLine),
            label="fin del entrenamiento",
            labelOpts={"color": T.INK_FAINT, "position": 0.94,
                       "fill": pg.mkBrush(T.rgba(T.PANEL, 0.9))})
        self.pi.addItem(self.split)

        self.leg = self.pi.addLegend(offset=(-8, 8), labelTextColor=T.INK_DIM,
                                     labelTextSize="8pt",
                                     brush=pg.mkBrush(T.rgba(T.PANEL, 0.85)),
                                     pen=pg.mkPen(T.RULE))
        self._named = False

    def show(self, res: SimResult) -> None:
        name = res.req.eq_kind.upper()
        y = res.learning
        if not y.size:
            self.cur.setData([], [])
            self.ref.setData([], [])
            return

        # Suavizado corto: la curva instantanea es demasiado ruidosa para leer
        # la velocidad de convergencia, que es lo que este panel mide.
        def smooth(v, k=24):
            if v.size < k:
                return v
            ker = np.ones(k) / k
            return np.convolve(v, ker, mode="valid")

        ys = smooth(y)
        self.cur.setData(np.arange(ys.size), ys)

        if res.learning_ref is not None and res.learning_ref.size:
            yr = smooth(res.learning_ref)
            self.ref.setData(np.arange(yr.size), yr)
            self.ref.setVisible(True)
        else:
            self.ref.setVisible(False)

        self.leg.clear()
        self.leg.addItem(self.cur, f"{name} (activo)")
        if self.ref.isVisible():
            self.leg.addItem(self.ref, res.learning_ref_name)

        self.split.setPos(res.n_train)
        n = max(ys.size, 1)
        self.pi.setXRange(0, min(n, max(res.n_train * 2, 900)), padding=0)
        lo = float(np.nanmin(ys)) if ys.size else -20
        self.pi.setYRange(max(lo - 3, -45), 8, padding=0)

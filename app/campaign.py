"""Campana: los experimentos de la guia, ejecutados en vivo.

Cada barrido se dibuja **mientras se calcula**, punto a punto, en vez de
aparecer al final: se ve la curva construirse y se puede detener en cuanto la
tendencia es clara.

Sobre los puntos sin errores. Cuando una configuracion no comete ni un error en
la carga util, la BER medida no es cero: es una cota superior, 1/(k*N). Esos
puntos se dibujan sobre la linea de suelo, marcados como cota y no como valor.
Fingir un cero en un eje logaritmico seria mentir sobre lo medido.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (QHBoxLayout, QProgressBar, QPushButton,
                               QVBoxLayout, QWidget)

from comm2 import SystemParams
from comm2.channel import PROFILES
from comm2.link import run_link
from comm2.modulation import Modulation

from . import theme as T
from .displays import _label, _plot
from .engine import Request, build
from .widgets import (HRule, LabeledCombo, Panel, SliderRow, panel_label,
                      text_label)


# ---------------------------------------------------------------------------
# Definicion de los barridos
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Series:
    name: str
    color: str
    mutate: Callable[[Request], Request]


@dataclass(frozen=True)
class Sweep:
    key: str
    title: str
    guide: str            # a que experimento de la guia corresponde
    xlabel: str
    question: str         # que se responde mirando esta grafica
    xs: tuple[float, ...]
    apply: Callable[[Request, float], Request]
    series: tuple[Series, ...]
    theory: bool = False
    logx: bool = False


EB = tuple(float(v) for v in range(0, 21, 2))
PROF_ORDER = ("flat", "mild", "moderate", "severe")


def _eq(kind: str, **kw):
    return lambda r: replace(r, eq_kind=kind, **kw)


SWEEPS: tuple[Sweep, ...] = (
    Sweep(
        key="exp1", title="BER teórica frente a simulada",
        guide="Experimento 1  ·  canal de referencia",
        xlabel="Eb/N0 [dB]",
        question="Si la cadena está bien construida, la BER simulada en AWGN debe "
                 "caer sobre la curva teórica. Cualquier separación sistemática "
                 "delata un error en la contabilidad de Eb/N0, en la normalización "
                 "del RRC o en el mapeo Gray.",
        xs=EB,
        apply=lambda r, x: replace(r, ebn0_db=x, scenario="A", eq_kind="none"),
        series=(
            Series("QPSK", T.S1, lambda r: replace(r, mod="qpsk")),
            Series("16-QAM", T.S2, lambda r: replace(r, mod="16qam")),
        ),
        theory=True,
    ),
    Sweep(
        key="exp3", title="Comparación de ecualizadores",
        guide="Experimento 3  ·  sección 8 de la guía",
        xlabel="Eb/N0 [dB]",
        question="Los dos métodos exigidos, LMS y RLS, frente al receptor sin "
                 "ecualizar y frente a ZF y MMSE calculados con canal conocido. "
                 "La distancia entre las curvas adaptativas y las de canal "
                 "conocido es lo que cuesta no conocer el canal.",
        xs=EB,
        apply=lambda r, x: replace(r, ebn0_db=x, scenario="B"),
        series=(
            Series("Sin ecualizar", T.S1, _eq("none")),
            Series("LMS (método A)", T.S2, _eq("lms")),
            Series("RLS (método B)", T.S3, _eq("rls")),
            Series("Zero-Forcing", T.S4, _eq("zf")),
            Series("MMSE", T.S5, _eq("mmse")),
        ),
    ),
    Sweep(
        key="exp5", title="Coste de la eficiencia espectral",
        guide="Experimento 5  ·  comparación de modulaciones",
        xlabel="Eb/N0 [dB]",
        question="Subir el orden de modulación multiplica la eficiencia espectral "
                 "y cuesta potencia. En el canal degradado el precio crece más "
                 "rápido, porque la ISI residual que deja un ecualizador lineal "
                 "pesa más cuanto menor es la distancia mínima de la constelación.",
        xs=tuple(float(v) for v in range(2, 27, 2)),
        apply=lambda r, x: replace(r, ebn0_db=x, scenario="C", eq_kind="lms"),
        series=(
            Series("QPSK", T.S1, lambda r: replace(r, mod="qpsk")),
            Series("8PSK", T.S2, lambda r: replace(r, mod="8psk")),
            Series("16-QAM", T.S3, lambda r: replace(r, mod="16qam")),
            Series("64-QAM", T.S4, lambda r: replace(r, mod="64qam")),
        ),
    ),
    Sweep(
        key="exp4cfo", title="Límite de adquisición de frecuencia",
        guide="Experimento 4  ·  robustez",
        xlabel="offset de frecuencia [fracción de Rs]",
        question="El estimador de Schmidl-Cox solo puede adquirir |f| < Rs/(2L). "
                 "Con L = 64 eso son 0,78 % de Rs: por debajo el receptor engancha "
                 "y la BER no se entera; por encima colapsa de golpe. No es una "
                 "degradación suave, es un acantilado.",
        xs=(0.0, 0.001, 0.002, 0.003, 0.004, 0.005, 0.006, 0.007, 0.0075,
            0.008, 0.009, 0.010),
        apply=lambda r, x: replace(r, cfo_frac_rs=x, scenario="C"),
        series=(
            Series("LMS (método A)", T.S2, _eq("lms")),
            Series("RLS (método B)", T.S3, _eq("rls")),
        ),
    ),
    Sweep(
        key="exp2", title="Severidad de la multitrayectoria",
        guide="Experimento 2  ·  efecto de la ISI",
        xlabel="perfil de canal",
        question="Los cuatro perfiles están normalizados a energía unitaria, de "
                 "modo que la SNR media no cambia entre ellos. Todo lo que se "
                 "degrada al avanzar por el eje es distorsión, no pérdida de "
                 "potencia: es la definición operativa de la ISI.",
        xs=(0.0, 1.0, 2.0, 3.0),
        apply=lambda r, x: replace(r, profile=PROF_ORDER[int(x)], scenario="B"),
        series=(
            Series("Sin ecualizar", T.S1, _eq("none")),
            Series("LMS (método A)", T.S2, _eq("lms")),
            Series("RLS (método B)", T.S3, _eq("rls")),
        ),
    ),
)

SWEEP_BY_KEY = {s.key: s for s in SWEEPS}


# ---------------------------------------------------------------------------
# Trabajador
# ---------------------------------------------------------------------------

class _SweepWorker(QObject):
    point = Signal(int, float, float, int)     # serie, x, ber, bits
    progress = Signal(int, int)
    finished = Signal(bool)                    # True si termino entero

    def __init__(self):
        super().__init__()
        self._stop = False

    def cancel(self) -> None:
        self._stop = True

    @Slot(object)
    def run(self, job: tuple) -> None:
        sweep, base, n_payload = job
        self._stop = False
        total = len(sweep.series) * len(sweep.xs)
        done = 0
        for si, ser in enumerate(sweep.series):
            for x in sweep.xs:
                if self._stop:
                    self.finished.emit(False)
                    return
                req = ser.mutate(sweep.apply(replace(base, compare=False,
                                                     n_payload=n_payload), x))
                try:
                    p, chan, rx = build(req)
                    r = run_link(p, chan, rx)
                    self.point.emit(si, x, float(r.stats["ber"]),
                                    int(r.stats["ber_bits"]))
                except Exception:
                    self.point.emit(si, x, float("nan"), 0)
                done += 1
                self.progress.emit(done, total)
        self.finished.emit(True)


# ---------------------------------------------------------------------------
# Vista
# ---------------------------------------------------------------------------

class Campaign(QWidget):
    _launch = Signal(object)

    def __init__(self, controls, parent=None):
        super().__init__(parent)
        self.controls = controls
        self._running = False
        self._curves: list = []
        self._data: list[tuple[list, list]] = []
        self._floor = 1.0

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        # -- barra de mando ---------------------------------------------------
        bar = QWidget()
        bh = QHBoxLayout(bar)
        bh.setContentsMargins(0, 0, 0, 0)
        bh.setSpacing(16)

        self.pick = LabeledCombo(
            "Experimento", [(s.key, s.title) for s in SWEEPS], "exp3")
        self.pick.setFixedWidth(320)
        bh.addWidget(self.pick)

        self.depth = SliderRow(
            "Símbolos por punto", 2000, 40000, 8000, 2000, "{:.0f}", "",
            tip="Más símbolos bajan el suelo de BER medible y alargan el barrido.\n"
                "El suelo 1/(k·N) se dibuja en la gráfica.")
        self.depth.setFixedWidth(210)
        bh.addWidget(self.depth)

        bh.addStretch(1)

        notes = QVBoxLayout()
        notes.setContentsMargins(0, 0, 0, 0)
        notes.setSpacing(2)
        notes.addWidget(text_label(
            "Toma del rail el resto de parámetros del receptor.",
            T.f_small(), T.INK_FAINT))
        self.floor_note = text_label("", T.f_small(), T.INK_FAINT)
        notes.addWidget(self.floor_note)
        bh.addLayout(notes)

        self.run_btn = QPushButton("Ejecutar barrido")
        self.run_btn.setObjectName("Primary")
        self.run_btn.setMinimumWidth(148)
        bh.addWidget(self.run_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(bar)

        self.prog = QProgressBar()
        self.prog.setTextVisible(False)
        self.prog.setValue(0)
        # Oculta en reposo: una barra vacia permanente se lee como un contenedor
        # roto, no como "sin progreso".
        self.prog.setVisible(False)
        root.addWidget(self.prog)

        # -- grafica ----------------------------------------------------------
        self.panel = Panel("Barrido")
        holder = QWidget()
        hv = QVBoxLayout(holder)
        hv.setContentsMargins(6, 4, 6, 6)
        hv.setSpacing(0)
        self.plot = _plot()
        self.pi = self.plot.getPlotItem()
        self.pi.setLogMode(x=False, y=True)
        _label(self.pi, "BER", "Eb/N0 [dB]")
        hv.addWidget(self.plot)
        self.panel.set_content(holder)
        root.addWidget(self.panel, 1)

        self.floor_line = pg.InfiniteLine(
            pos=0, angle=0, pen=pg.mkPen(T.INK_GHOST, width=1,
                                         style=Qt.PenStyle.DashLine),
            label="suelo medible  1/(k·N)",
            labelOpts={"color": T.INK_FAINT, "position": 0.46})
        self.pi.addItem(self.floor_line)

        self.empty = pg.TextItem("", color=T.INK_FAINT, anchor=(0.5, 0.5))
        self.empty.setFont(T.font(10, 400))
        self.pi.addItem(self.empty)

        self.theory_curves: list = []
        self.legend = self.pi.addLegend(offset=(-10, 10), labelTextColor=T.INK_DIM,
                                        labelTextSize="8pt",
                                        brush=pg.mkBrush(T.rgba(T.PANEL, 0.88)),
                                        pen=pg.mkPen(T.RULE))

        # -- lectura del experimento ------------------------------------------
        caption = QWidget()
        cv = QVBoxLayout(caption)
        cv.setContentsMargins(2, 0, 2, 0)
        cv.setSpacing(5)
        self.guide_tag = panel_label("", T.SIGNAL)
        cv.addWidget(self.guide_tag)
        self.question = text_label("", T.f_body(), T.INK_DIM, wrap=True)
        cv.addWidget(self.question)
        root.addWidget(caption)

        # -- hilo --------------------------------------------------------------
        self._thread = QThread()
        self._thread.setObjectName("comm2-sweep")
        self._worker = _SweepWorker()
        self._worker.moveToThread(self._thread)
        self._launch.connect(self._worker.run)
        self._worker.point.connect(self._on_point)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._thread.start()

        self.pick.changed.connect(lambda _k: self._prepare())
        self.depth.moved.connect(lambda _v: self._update_floor())
        self.controls.settled.connect(
            lambda: None if self._running else self._update_floor())
        self.run_btn.clicked.connect(self._toggle)
        self._prepare()

    # -- preparacion ---------------------------------------------------------
    def _sweep(self) -> Sweep:
        return SWEEP_BY_KEY[self.pick.value()]

    def _prepare(self) -> None:
        sw = self._sweep()
        self.panel.set_title(sw.title)
        self.guide_tag.setText(sw.guide)
        self.question.setText(sw.question)
        _label(self.pi, "BER", sw.xlabel)

        for c in self._curves + self.theory_curves:
            self.pi.removeItem(c)
        self._curves, self.theory_curves = [], []
        self.legend.clear()
        self._data = [([], []) for _ in sw.series]

        for ser in sw.series:
            c = self.pi.plot([], [], pen=pg.mkPen(ser.color, width=1.9),
                             symbol="o", symbolSize=6,
                             symbolBrush=pg.mkBrush(ser.color),
                             symbolPen=pg.mkPen(T.PANEL, width=1.4))
            self._curves.append(c)
            self.legend.addItem(c, ser.name)

        if sw.key == "exp2":
            ax = self.pi.getAxis("bottom")
            ax.setTicks([[(i, n) for i, n in enumerate(
                ("Plano", "Leve", "Moderado", "Severo"))]])
        else:
            self.pi.getAxis("bottom").setTicks(None)

        self.pi.setXRange(min(sw.xs), max(sw.xs), padding=0.04)
        self.pi.setYRange(-6, 0, padding=0)
        # Eje de Eb/N0 cada 4 dB: una marca por punto simulado satura la regla.
        if sw.key != "exp2":
            step = (max(sw.xs) - min(sw.xs)) / 5.0
            self.pi.getAxis("bottom").setTickSpacing(
                max(step, 0.001), max(step / 2, 0.0005))
        self._show_empty(True)
        self._update_floor()

    def _show_empty(self, on: bool) -> None:
        self.empty.setText(
            "Pulsa «Ejecutar barrido» para calcular estas curvas.\n"
            "Cada punto es una simulación completa del enlace." if on else "")
        self.empty.setVisible(on)
        if on:
            sw = self._sweep()
            self.empty.setPos((min(sw.xs) + max(sw.xs)) / 2, -3.0)

    def _update_floor(self) -> None:
        req = self.controls.request()
        sw = self._sweep()
        mods = {ser.mutate(sw.apply(req, sw.xs[0])).mod for ser in sw.series}
        k = max(Modulation(m).bits_per_symbol for m in mods)
        n = int(self.depth.value())
        self._floor = 1.0 / max(k * n, 1)
        # En modo log, InfiniteLine.setPos trabaja en coordenadas de vista (log10).
        self.floor_line.setPos(np.log10(self._floor))
        origen = (f"{k} bits/símbolo, la modulación más densa del barrido"
                  if len(mods) > 1 else f"{k} bits/símbolo")
        self.floor_note.setText(
            f"suelo medible {self._floor:.1e} ({origen})".replace("e-0", "e-"))

    # -- ejecucion -----------------------------------------------------------
    def _toggle(self) -> None:
        if self._running:
            self._worker.cancel()
            self.run_btn.setText("Deteniendo...")
            self.run_btn.setEnabled(False)
            return
        sw = self._sweep()
        self._data = [([], []) for _ in sw.series]
        for c in self._curves:
            c.setData([], [])
        self._draw_theory(sw)
        self._update_floor()
        self._running = True
        self._show_empty(False)
        self.run_btn.setText("Detener")
        self.run_btn.setObjectName("")
        self.run_btn.style().unpolish(self.run_btn)
        self.run_btn.style().polish(self.run_btn)
        self.prog.setValue(0)
        self.prog.setVisible(True)
        self.pick.setEnabled(False)
        self.depth.setEnabled(False)
        self._launch.emit((sw, self.controls.request(), int(self.depth.value())))

    def _draw_theory(self, sw: Sweep) -> None:
        for c in self.theory_curves:
            self.pi.removeItem(c)
        self.theory_curves = []
        if not sw.theory:
            return
        xs = np.linspace(min(sw.xs), max(sw.xs), 120)
        base = self.controls.request()
        for ser in sw.series:
            req = ser.mutate(base)
            y = Modulation(req.mod).ber_theory(xs)
            c = self.pi.plot(xs, np.maximum(y, 1e-12),
                             pen=pg.mkPen(ser.color, width=1.1,
                                          style=Qt.PenStyle.DashLine))
            c.setZValue(-5)
            self.theory_curves.append(c)
        if self.theory_curves:
            self.legend.addItem(self.theory_curves[0], "teórica (discontinua)")

    @Slot(int, float, float, int)
    def _on_point(self, si: int, x: float, ber: float, bits: int) -> None:
        if not np.isfinite(ber):
            return
        # Sin errores: la medida es una cota, y se dibuja en el suelo.
        y = ber if ber > 0 else (1.0 / bits if bits else self._floor)
        xs, ys = self._data[si]
        xs.append(x)
        ys.append(max(y, 1e-12))          # BER lineal: pyqtgraph aplica el log10
        self._curves[si].setData(xs, ys)
        lo = min([np.log10(min(d[1])) for d in self._data if d[1]]
                 + [np.log10(self._floor), -1.0])
        self.pi.setYRange(max(lo - 0.4, -7.5), 0.1, padding=0)  # vista: log10

    @Slot(int, int)
    def _on_progress(self, done: int, total: int) -> None:
        self.prog.setMaximum(total)
        self.prog.setValue(done)

    @Slot(bool)
    def _on_finished(self, complete: bool) -> None:
        self._running = False
        self.run_btn.setText("Ejecutar barrido")
        self.run_btn.setObjectName("Primary")
        self.run_btn.setEnabled(True)
        self.run_btn.style().unpolish(self.run_btn)
        self.run_btn.style().polish(self.run_btn)
        self.pick.setEnabled(True)
        self.depth.setEnabled(True)
        if complete:
            self.prog.setValue(self.prog.maximum())
        self.prog.setVisible(False)

    def stop(self) -> None:
        self._worker.cancel()
        self._thread.quit()
        self._thread.wait(3000)

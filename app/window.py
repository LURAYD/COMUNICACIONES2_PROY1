"""Ventana principal: chasis, cabecera y conmutacion de vistas."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QStackedWidget,
                               QVBoxLayout, QWidget)

from . import theme as T
from .backdrop import Backdrop
from .bench import Bench
from .campaign import Campaign
from .controls import Controls
from .engine import SimController, compare_isi
from .isiview import IsiView
from .widgets import HRule, Segmented, panel_label, text_label

VIEWS = [("bench", "Banco de pruebas"), ("isi", "ISI y ecualizador"),
         ("camp", "Campaña")]
VIEW_INDEX = {"bench": 0, "isi": 1, "camp": 2}


class Header(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Header")
        self.setFixedHeight(68)
        h = QHBoxLayout(self)
        h.setContentsMargins(22, 0, 22, 0)
        h.setSpacing(26)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(1)
        title = QLabel("Receptor digital adaptativo")
        title.setFont(T.f_title())
        title.setStyleSheet(f"color: {T.INK}")
        left.addWidget(title)
        sub = text_label("Proyecto 1  ·  Comunicaciones II 2026", T.f_small(),
                         T.INK_DIM)
        left.addWidget(sub)
        h.addLayout(left)

        h.addStretch(1)
        self.views = Segmented(VIEWS, "bench", height=32, min_seg=124)
        self.views.setMaximumWidth(560)
        h.addWidget(self.views)
        h.addStretch(1)

        self.spec = QLabel("")
        self.spec.setFont(T.font(9.5, 400, mono=True))
        self.spec.setStyleSheet(f"color: {T.INK_DIM}")
        self.spec.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(self.spec)

    def set_spec(self, text: str) -> None:
        self.spec.setText(text)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Receptor digital adaptativo — Comunicaciones II 2026")
        self.resize(1600, 1000)
        self.setMinimumSize(1200, 780)

        self.sim = SimController(self)
        # La vista de ISI tiene su propio hilo: cuatro enlaces por petición, y
        # no debe retener ni descartar las peticiones del banco.
        self.isi_sim = SimController(self, fn=compare_isi, name="comm2-isi")

        root = Backdrop()
        rv = QVBoxLayout(root)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)

        self.header = Header()
        rv.addWidget(self.header)

        body = QWidget()
        bh = QHBoxLayout(body)
        bh.setContentsMargins(0, 0, 0, 0)
        bh.setSpacing(0)

        self.controls = Controls()
        bh.addWidget(self.controls)

        self.stack = QStackedWidget()
        self.stack.setObjectName("Stack")
        self.stack.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.bench = Bench()
        self.isi = IsiView()
        self.campaign = Campaign(self.controls)
        self.stack.addWidget(self.bench)
        self.stack.addWidget(self.isi)
        self.stack.addWidget(self.campaign)
        bh.addWidget(self.stack, 1)

        rv.addWidget(body, 1)
        self.setCentralWidget(root)

        # -- cableado --------------------------------------------------------
        self.controls.changed.connect(lambda: self._run(compare=False))
        self.controls.settled.connect(lambda: self._run(compare=True))
        self.sim.result.connect(self._on_result)
        self.sim.error.connect(self.bench.set_error)
        self.sim.busy.connect(self.bench.set_busy)
        self.isi_sim.result.connect(self.isi.apply)
        self.isi_sim.error.connect(self.isi.set_error)
        self.isi_sim.busy.connect(self.isi.set_busy)
        self.header.views.changed.connect(self._on_view)

        self._update_spec()
        QTimer.singleShot(60, lambda: self._run(compare=True))

    # -- ciclo ---------------------------------------------------------------
    def _run(self, compare: bool) -> None:
        cur = self.stack.currentWidget()
        if cur is self.bench:
            self.sim.submit(self.controls.request(compare=compare))
        elif cur is self.isi:
            self.isi_sim.submit(self.controls.request(compare=compare))
        else:
            return
        self._update_spec()

    def _on_result(self, res) -> None:
        self.bench.apply(res)

    def _on_view(self, key: str) -> None:
        self.stack.setCurrentIndex(VIEW_INDEX[key])
        # El rail sigue vivo en la campana porque el barrido USA sus valores
        # (taps, paso, perfil, entrenamiento) para todo salvo el eje que barre.
        self.controls.set_view(key)
        # Al volver a una vista se recalcula: el rail pudo cambiar mientras
        # tanto y la vista no puede enseñar un resultado de otros parámetros.
        if key in ("bench", "isi"):
            self._run(compare=True)

    def _update_spec(self) -> None:
        from comm2 import SystemParams
        r = self.controls.request()
        p = SystemParams(mod=r.mod, beta=r.beta)
        self.header.set_spec(
            f"Rs {p.rs / 1e3:.0f} kBd   Rb {p.rb / 1e3:.0f} kb/s   "
            f"B {p.bw / 1e3:.1f} kHz   η {p.spectral_efficiency:.2f} b/s/Hz")

    def closeEvent(self, e):  # noqa: N802
        self.campaign.stop()
        self.sim.shutdown()
        self.isi_sim.shutdown()
        super().closeEvent(e)

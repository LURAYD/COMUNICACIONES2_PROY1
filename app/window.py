"""Ventana principal: chasis, cabecera y conmutacion de secciones.

Cuatro secciones en el orden del enlace: generacion de onda, canal, analisis
(receptor, ISI y campana como sub-pestanas) y exportar. Generacion, canal y
receptor comparten la MISMA corrida de `run_link`: cambiar de seccion no
recalcula, solo cambia que instrumentos se ven.
"""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QStackedWidget,
                               QVBoxLayout, QWidget)

from . import theme as T
from .backdrop import Backdrop
from .bench import Bench
from .campaign import Campaign
from .controls import Controls
from .engine import Request, SimController, compare_isi
from .isiview import IsiView
from .sections import AnalysisView, ChanView, ExportView, GenView
from .widgets import Segmented, text_label

SECTIONS = [("gen", "1  Generación de onda"), ("chan", "2  Canal"),
            ("ana", "3  Análisis"), ("export", "4  Exportar")]
# Vistas que corren la simulacion del banco: las tres leen el mismo resultado.
LIVE = ("gen", "chan", "bench")
# Mientras se arrastra un control se simula con menos simbolos: la forma de las
# graficas ya se ve, y al soltar llega la corrida completa con la que se mide.
PREVIEW_SYMBOLS = 1000
FULL_SYMBOLS = Request().n_payload


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
        self.views = Segmented(SECTIONS, "gen", height=32, min_seg=150)
        self.views.setMaximumWidth(760)
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
        self.gen = GenView()
        self.chan = ChanView()
        self.bench = Bench()
        self.isi = IsiView()
        self.campaign = Campaign(self.controls)
        self.analysis = AnalysisView(self.bench, self.isi, self.campaign)
        self.export = ExportView(self.controls.request)
        self.pages = {"gen": self.gen, "chan": self.chan, "ana": self.analysis,
                      "export": self.export}
        for w in self.pages.values():
            self.stack.addWidget(w)
        bh.addWidget(self.stack, 1)

        rv.addWidget(body, 1)
        self.setCentralWidget(root)

        # -- cableado --------------------------------------------------------
        self.controls.changed.connect(lambda: self._run(compare=False, preview=True))
        self.controls.settled.connect(lambda: self._run(compare=True))
        self.controls.jump.connect(self._jump)
        self.sim.result.connect(self._on_result)
        self.sim.error.connect(self._on_error)
        self.sim.busy.connect(self.bench.set_busy)
        self.isi_sim.result.connect(self.isi.apply)
        self.isi_sim.error.connect(self.isi.set_error)
        self.isi_sim.busy.connect(self.isi.set_busy)
        self.header.views.changed.connect(self._on_section)
        self.analysis.changed.connect(lambda _k: self._on_view())

        self._last = None           # ultimo resultado del banco
        self._drawn: set[str] = set()   # vistas que ya lo tienen dibujado
        self._on_view()

    # -- vista activa --------------------------------------------------------
    def _view(self) -> str:
        """gen, chan, bench, isi, camp o export."""
        sec = self.header.views.current
        return self.analysis.current if sec == "ana" else sec

    def _on_section(self, key: str) -> None:
        self.stack.setCurrentWidget(self.pages[key])
        self._on_view()

    def _jump(self, view: str) -> None:
        """Desde el resumen del rail: `view` es gen, chan o bench."""
        sec = "ana" if view == "bench" else view
        if sec == "ana":
            self.analysis.tabs.set_value("bench")
            self.analysis._on_tab("bench")
        self.header.views.set_value(sec)
        self._on_section(sec)

    def _on_view(self) -> None:
        key = self._view()
        # Exportar no tiene controles propios: el rail no tiene nada que hacer.
        self.controls.setVisible(key != "export")
        # El rail sigue vivo en la campana porque el barrido USA sus valores
        # (taps, paso, perfil, entrenamiento) para todo salvo el eje que barre.
        self.controls.set_view(key)
        if key == "export":
            self.export.refresh()
        # Generacion, canal y receptor comparten la corrida: si el ultimo
        # resultado ya corresponde al rail, solo se dibuja en la vista nueva.
        # Si el rail cambio entretanto (en ISI o campana), se recalcula: la
        # vista no puede ensenar un resultado de otros parametros.
        if key in LIVE and self._last is not None and self._covers(self._last.req):
            self._draw(key)
            return
        self._run(compare=True)

    # -- ciclo ---------------------------------------------------------------
    def _wanted(self, compare: bool) -> Request:
        req = self.controls.request(compare=compare)
        # La curva del metodo contrario (LMS <-> RLS) cuesta una segunda
        # corrida entera y solo se dibuja en el receptor.
        if self._view() != "bench" or req.eq_kind not in ("lms", "rls"):
            req.compare = False
        return req

    def _covers(self, done: Request) -> bool:
        """El resultado `done` sirve para lo que pide ahora el rail."""
        want = self._wanted(True)
        if done.n_payload != FULL_SYMBOLS or (want.compare and not done.compare):
            return False
        return replace(done, seq=0, compare=False) == replace(want, seq=0, compare=False)

    def _run(self, compare: bool, preview: bool = False) -> None:
        key = self._view()
        req = self._wanted(compare)
        if preview:
            req = replace(req, n_payload=PREVIEW_SYMBOLS, compare=False)
        if key in LIVE:
            self.sim.submit(req)
        elif key == "isi":
            self.isi_sim.submit(req)
        else:
            return
        self._update_spec()

    def _on_result(self, res) -> None:
        # Solo se dibuja la vista visible; las otras lo haran al mostrarse.
        self._last = res
        self._drawn = set()
        key = self._view()
        if key in LIVE:
            self._draw(key)

    def _draw(self, key: str) -> None:
        if key not in self._drawn and self._last is not None:
            {"gen": self.gen, "chan": self.chan, "bench": self.bench}[key].apply(self._last)
            self._drawn.add(key)

    def _on_error(self, msg: str) -> None:
        self.gen.set_error(msg)
        self.chan.set_error(msg)
        self.bench.set_error(msg)

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

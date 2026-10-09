"""Las secciones del flujo: generación, canal, análisis y exportación.

Cada sección enseña SOLO los instrumentos y las medidas de su tramo del enlace.
Las de generación y canal no simulan nada propio: leen el mismo `SimResult` que
el análisis del receptor (una sola corrida de `run_link`), de modo que las tres
dicen lo mismo de la misma señal.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QFileDialog, QGridLayout, QHBoxLayout, QPlainTextEdit,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from . import theme as T
from .displays import Constellation, Eye, Spectrum
from .engine import SYMBOL, Request, SimResult
from .isiview import Stems
from .widgets import Panel, Readout, SectionHead, Segmented, text_label

PROJECT = Path(__file__).resolve().parent.parent


def _col(op: float) -> str:
    return T.GOOD if op > 0.5 else (T.WARNING if op > 0.2 else T.CRITICAL)


class _Readouts(QWidget):
    """Fila de medidas de una sección."""

    def __init__(self, items: list[Readout], parent=None):
        super().__init__(parent)
        self.setObjectName("ReadoutBar")
        h = QHBoxLayout(self)
        h.setContentsMargins(20, 12, 20, 12)
        h.setSpacing(0)
        self.cells = {}
        for i, r in enumerate(items):
            cell = QWidget()
            ch = QHBoxLayout(cell)
            ch.setContentsMargins(0, 0, 0, 0)
            ch.setSpacing(0)
            if i:
                sep = QWidget()
                sep.setFixedWidth(1)
                sep.setStyleSheet(f"background: {T.RULE_STRONG};")
                ch.addSpacing(16)
                ch.addWidget(sep)
                ch.addSpacing(16)
            r.setMinimumWidth(r.sizeHint().width())
            ch.addWidget(r)
            h.addWidget(cell)
            self.cells[r] = cell
        h.addStretch(1)


def _body(head: SectionHead) -> tuple[QWidget, QVBoxLayout, QGridLayout]:
    center = QWidget()
    cv = QVBoxLayout(center)
    cv.setContentsMargins(18, 16, 18, 16)
    cv.setSpacing(12)
    cv.addWidget(head)
    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(12)
    cv.addLayout(grid, 1)
    return center, cv, grid


# ---------------------------------------------------------------------------
# 1 · Generación de onda
# ---------------------------------------------------------------------------

class GenView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        center, _cv, grid = _body(SectionHead(
            "1", "Generación de onda",
            "Mapeo de bits a símbolos y conformación con el filtro RRC. "
            "Aquí todavía no hay canal: es la señal tal como sale del transmisor."))

        self.p_const = Panel("Constelación  ·  símbolos transmitidos")
        self.const = Constellation()
        self.p_const.set_content(self.const)
        self.p_eye = Panel("Diagrama de ojo  ·  tras el RRC")
        self.eye = Eye()
        self.p_eye.set_content(self.eye)
        self.p_spec = Panel("Densidad espectral  ·  señal transmitida")
        self.spec = Spectrum()
        self.p_spec.set_content(self.spec)

        grid.addWidget(self.p_const, 0, 0)
        grid.addWidget(self.p_eye, 0, 1)
        grid.addWidget(self.p_spec, 1, 0, 1, 2)
        grid.setRowStretch(0, 3)
        grid.setRowStretch(1, 2)
        root.addWidget(center, 1)

        self.rs = Readout("Tasa de símbolo", "kBd")
        self.rb = Readout("Tasa de bit", "kb/s")
        self.k = Readout("Bits por símbolo", "")
        self.bw = Readout("Ancho de banda", "kHz", tip="B = Rs(1 + β)")
        self.eta = Readout("Eficiencia", "b/s/Hz", tip="Rb / B = k / (1 + roll-off).")
        self.papr = Readout("PAPR", "dB",
                            tip="Relación potencia de pico a potencia media de la\n"
                                "forma de onda transmitida (con el preámbulo).")
        root.addWidget(_Readouts([self.rs, self.rb, self.k, self.bw, self.eta, self.papr]))

    def apply(self, res: SimResult) -> None:
        from comm2 import SystemParams
        tx = res.taps["tx"]
        self.const.set_reference(res.ideal)
        self.const.autoscale(tx.pts)
        self.const.show_tap(tx.pts, SYMBOL, animate=False)
        self.p_const.set_note(f"{res.req.mod.upper()}  ·  {res.ideal.size} puntos")

        rrc = res.taps["rrc"]
        self.eye.set_caption("")
        self.eye.show_wave(rrc.wave, res.sps, rrc.opening)
        self.p_eye.set_note(f"apertura {rrc.opening:.3f}", _col(rrc.opening))

        self.spec.show(res.psd, res.req.beta, rx=False)
        self.p_spec.set_note(f"B = {1.0 + res.req.beta:.2f} Rs")

        p = SystemParams(mod=res.req.mod, beta=res.req.beta)
        self.rs.set(f"{p.rs / 1e3:.0f}")
        self.rb.set(f"{p.rb / 1e3:.0f}")
        self.k.set(f"{p.bits_per_symbol}")
        self.bw.set(f"{p.bw / 1e3:.1f}")
        self.eta.set(f"{p.spectral_efficiency:.2f}")
        self.papr.set(f"{res.papr_db:.2f}" if math.isfinite(res.papr_db) else "--")

    def set_error(self, msg: str) -> None:
        self.p_const.set_note(msg[:60], T.CRITICAL)


# ---------------------------------------------------------------------------
# 2 · Canal
# ---------------------------------------------------------------------------

class ChanView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        center, _cv, grid = _body(SectionHead(
            "2", "Configuración del canal",
            "Multitrayecto, ruido y errores de sincronismo. Lo que se ve es la "
            "señal a la entrada del receptor, antes de corregir nada."))

        self.p_h = Panel("Respuesta al impulso  ·  canal equivalente a tasa de símbolo")
        self.stems = Stems()
        self.p_h.set_content(self.stems)
        self.p_const = Panel("Constelación  ·  tras el canal")
        self.const = Constellation()
        self.p_const.set_content(self.const)
        self.p_eye = Panel("Diagrama de ojo  ·  tras el canal")
        self.eye = Eye()
        self.p_eye.set_content(self.eye)
        self.p_spec = Panel("Densidad espectral  ·  antes y después del canal")
        self.spec = Spectrum()
        self.p_spec.set_content(self.spec)

        grid.addWidget(self.p_h, 0, 0)
        grid.addWidget(self.p_const, 0, 1)
        grid.addWidget(self.p_eye, 1, 0)
        grid.addWidget(self.p_spec, 1, 1)
        root.addWidget(center, 1)

        self.ebn0 = Readout("Eb/N0", "dB")
        self.esn0 = Readout("Es/N0", "dB")
        self.sir = Readout("SIR del canal", "dB",
                           tip="Potencia del cursor entre potencia de la ISI,\n"
                               "del canal sin ecualizar.")
        self.dist = Readout("Distorsión de pico", "",
                            tip="D = Σ|c_k| / |c_0| fuera del cursor.\n"
                                "D ≥ 1 cierra el ojo de BPSK aun sin ruido.")
        self.cfo = Readout("Offset de frecuencia", "Hz")
        self.bar = _Readouts([self.ebn0, self.esn0, self.sir, self.dist, self.cfo])
        root.addWidget(self.bar)

    def apply(self, res: SimResult) -> None:
        req = res.req
        h = res.h_sym if res.h_sym is not None else []
        self.stems.show(h, [], "")
        self.p_h.set_note("canal plano: sin ISI" if req.scenario == "A"
                          else f"{len(h)} coeficientes")

        ch = res.taps["chan"]
        self.const.set_reference(res.ideal)
        self.const.autoscale(ch.pts)
        self.const.show_tap(ch.pts, ch.kind, animate=False)
        self.p_const.set_note("muestreada en el instante óptimo")
        self.eye.set_caption("")
        self.eye.show_wave(ch.wave, res.sps, ch.opening)
        self.p_eye.set_note(f"apertura {ch.opening:.3f}", _col(ch.opening))
        self.spec.show(res.psd, req.beta, rx=True)
        self.p_spec.set_note(f"B = {1.0 + req.beta:.2f} Rs")

        from comm2.modulation import Modulation
        k = Modulation(req.mod).bits_per_symbol
        self.ebn0.set(f"{req.ebn0_db:.1f}")
        self.esn0.set(f"{req.ebn0_db + 10 * math.log10(k):.1f}")
        if math.isfinite(res.sir_db):
            self.sir.set(f"{res.sir_db:.2f}", unit="dB")
            self.dist.set(f"{res.peak_distortion:.3f}",
                          T.CRITICAL if res.peak_distortion >= 1 else T.INK)
        else:
            self.sir.set("sin ISI", T.INK_DIM, unit="")
            self.dist.set("0", T.INK_DIM)
        # El offset de frecuencia solo existe en los escenarios C y D.
        has_cfo = req.scenario in ("C", "D")
        self.bar.cells[self.cfo].setVisible(has_cfo)
        if has_cfo:
            from comm2 import SystemParams
            rs = SystemParams(mod=req.mod, beta=req.beta).rs
            self.cfo.set(f"{req.cfo_frac_rs * rs:.0f}")

    def set_error(self, msg: str) -> None:
        self.p_h.set_note(msg[:60], T.CRITICAL)


# ---------------------------------------------------------------------------
# 3 · Análisis: receptor, ISI y campaña bajo una misma sección
# ---------------------------------------------------------------------------

ANALYSIS = [("bench", "Receptor"), ("isi", "ISI y ecualizador"), ("camp", "Campaña")]


class AnalysisView(QWidget):
    """Sub-pestañas de análisis. `changed` emite la clave de la sub-vista."""

    changed = Signal(str)

    def __init__(self, bench: QWidget, isi: QWidget, camp: QWidget, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        top = QWidget()
        th = QHBoxLayout(top)
        th.setContentsMargins(18, 14, 18, 0)
        th.setSpacing(16)
        th.addWidget(SectionHead("3", "Análisis"), 0)
        th.addStretch(1)
        self.tabs = Segmented(ANALYSIS, "bench", height=30, min_seg=130)
        self.tabs.setMaximumWidth(460)
        th.addWidget(self.tabs)
        v.addWidget(top)

        self.stack = QStackedWidget()
        self.stack.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.pages = {"bench": bench, "isi": isi, "camp": camp}
        for w in self.pages.values():
            self.stack.addWidget(w)
        v.addWidget(self.stack, 1)
        self.tabs.changed.connect(self._on_tab)

    @property
    def current(self) -> str:
        return self.tabs.current

    def _on_tab(self, key: str) -> None:
        self.stack.setCurrentWidget(self.pages[key])
        self.changed.emit(key)


# ---------------------------------------------------------------------------
# 4 · Exportar
# ---------------------------------------------------------------------------

class ExportView(QWidget):
    """JSON de variables para GNU Radio, más las imágenes y medidas de siempre."""

    def __init__(self, request: Callable[[], Request], parent=None):
        super().__init__(parent)
        self._request = request
        self._path: Optional[Path] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)
        root.addWidget(SectionHead(
            "4", "Exportar",
            "La configuración actual de las tres secciones como variables de "
            "GNU Radio Companion, o las figuras y medidas del análisis."))

        body = QHBoxLayout()
        body.setSpacing(12)

        self.p_json = Panel("Configuración  ·  JSON de variables")
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setObjectName("Code")
        self.p_json.set_content(self.text)
        body.addWidget(self.p_json, 3)

        side = QVBoxLayout()
        side.setSpacing(12)
        actions = Panel("Acciones")
        aw = QWidget()
        av = QVBoxLayout(aw)
        av.setContentsMargins(12, 12, 12, 12)
        av.setSpacing(10)
        self.save_btn = QPushButton("Guardar JSON…")
        self.save_btn.setObjectName("Primary")
        self.copy_btn = QPushButton("Copiar JSON al portapapeles")
        self.img_btn = QPushButton("Exportar figuras y medidas…")
        self.img_btn.setToolTip("Las mismas imágenes y el medidas.csv que\n"
                                "python -m app --export, en la carpeta que elijas.")
        for b in (self.save_btn, self.copy_btn, self.img_btn):
            av.addWidget(b)
        self.status = text_label("", T.f_small(), T.INK_DIM, wrap=True)
        av.addWidget(self.status)
        actions.set_content(aw)
        side.addWidget(actions)

        self.p_grc = Panel("Cómo cargarlo en GNU Radio Companion")
        self.snippet = QPlainTextEdit()
        self.snippet.setReadOnly(True)
        self.snippet.setObjectName("Code")
        self.snippet.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.p_grc.set_content(self.snippet)
        side.addWidget(self.p_grc, 1)
        body.addLayout(side, 2)
        root.addLayout(body, 1)

        self.save_btn.clicked.connect(self._save)
        self.copy_btn.clicked.connect(self._copy)
        self.img_btn.clicked.connect(self._images)

    # -- contenido -----------------------------------------------------------
    def refresh(self) -> None:
        from .gnuradio_json import GRC_SNIPPET, dumps
        try:
            self.text.setPlainText(dumps(self._request()))
            self.p_json.set_note("")
        except Exception as e:  # noqa: BLE001 - se muestra en la interfaz
            self.p_json.set_note(f"{type(e).__name__}: {e}"[:70], T.CRITICAL)
        path = self._path or (PROJECT / "comm2_config.json")
        self.snippet.setPlainText(GRC_SNIPPET.format(path=path))

    # -- acciones ------------------------------------------------------------
    def _save(self) -> None:
        start = str(self._path or (PROJECT / "comm2_config.json"))
        fn, _ = QFileDialog.getSaveFileName(self, "Guardar configuración", start,
                                            "JSON (*.json)")
        if not fn:
            return
        self.refresh()
        Path(fn).write_text(self.text.toPlainText(), encoding="utf-8")
        self._path = Path(fn)
        self.refresh()
        self.status.setText(f"Guardado en {fn}")

    def _copy(self) -> None:
        self.refresh()
        QGuiApplication.clipboard().setText(self.text.toPlainText())
        self.status.setText("JSON copiado al portapapeles.")

    def _images(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Carpeta para figuras y medidas",
                                             str(PROJECT))
        if not d:
            return
        from PySide6.QtWidgets import QApplication

        from .export import run as export_run
        self.status.setText("Exportando…")
        QApplication.processEvents()
        try:
            export_run(self._request(), Path(d), verbose=False)
            self.status.setText(f"Figuras y medidas.csv en {d}")
        except Exception as e:  # noqa: BLE001
            self.status.setText(f"Error: {type(e).__name__}: {e}")

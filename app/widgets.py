"""Primitivos de interfaz del instrumento.

Piezas pequenas y repetidas: la superficie de pantalla con su nomenclatura, la
lectura numerica tabular, la fila de control con su valor, y el selector
segmentado. Se pintan a mano donde Qt no da el control necesario sobre la regla
de un pixel o sobre el estado de foco.
"""

from __future__ import annotations

from typing import Callable, Iterable, Optional

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import (QColor, QFontMetricsF, QPainter, QPainterPath, QPen)
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel,
                               QSizePolicy, QSlider, QVBoxLayout, QWidget)

from . import theme as T


# ---------------------------------------------------------------------------
# Etiquetas
# ---------------------------------------------------------------------------

def panel_label(text: str, color: str | None = None) -> QLabel:
    """Nomenclatura de panel: como la serigrafia del frontal de un instrumento.

    El color se resuelve al LLAMAR, no al definir: un valor por defecto queda
    fijado en el momento de importar el modulo, y ataria el widget al tema que
    estuviera activo entonces en vez de al que pida el usuario.
    """
    lb = QLabel(text)
    lb.setFont(T.f_panel())
    lb.setStyleSheet(f"color: {color or T.INK_FAINT}")
    return lb


def text_label(text: str, font=None, color: str | None = None,
               wrap: bool = False) -> QLabel:
    lb = QLabel(text)
    lb.setFont(font or T.f_body())
    lb.setStyleSheet(f"color: {color or T.INK_DIM}")
    if wrap:
        lb.setWordWrap(True)
    return lb


class HRule(QFrame):
    def __init__(self, color: str | None = None, parent=None):
        super().__init__(parent)
        color = color or T.RULE
        self.setFixedHeight(1)
        self.setObjectName("RuleStrong" if color == T.RULE_STRONG else "Rule")
        self.setStyleSheet(f"background: {color}; border: none;")


# ---------------------------------------------------------------------------
# Superficie de pantalla
# ---------------------------------------------------------------------------

class Panel(QFrame):
    """Superficie con nomenclatura arriba y contenido debajo.

    El anotador de la derecha lleva la medida que corresponde a ese panel, para
    que el numero viva junto a la senal que lo produce y no en otra parte de la
    pantalla.
    """

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setFrameShape(QFrame.Shape.NoFrame)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        head = QWidget()
        hl = QHBoxLayout(head)
        hl.setContentsMargins(11, 8, 11, 7)
        hl.setSpacing(10)
        self.title = panel_label(title)
        self.note = QLabel("")
        self.note.setFont(T.f_unit())
        self.note.setStyleSheet(f"color: {T.INK_FAINT}")
        self.note.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        hl.addWidget(self.title)
        hl.addStretch(1)
        hl.addWidget(self.note)
        outer.addWidget(head)
        outer.addWidget(HRule())

        self.body = QWidget()
        self._bl = QVBoxLayout(self.body)
        self._bl.setContentsMargins(0, 0, 0, 0)
        self._bl.setSpacing(0)
        outer.addWidget(self.body, 1)

    def set_content(self, w: QWidget) -> None:
        self._bl.addWidget(w)

    def set_note(self, text: str, color: str = T.INK_FAINT) -> None:
        self.note.setText(text)
        self.note.setStyleSheet(f"color: {color}")

    def set_title(self, text: str) -> None:
        self.title.setText(text)


# ---------------------------------------------------------------------------
# Lectura numerica
# ---------------------------------------------------------------------------

class Readout(QWidget):
    """Una medida: nombre arriba, cifra tabular abajo, unidad al lado.

    La cifra va en monoespaciada porque es una medida: al cambiar no debe
    desplazar lo que tiene al lado.
    """

    def __init__(self, name: str, unit: str = "", large: bool = False,
                 tip: str = "", parent=None):
        super().__init__(parent)
        if tip:
            self.setToolTip(tip)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)

        self.name = panel_label(name)
        v.addWidget(self.name)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self.value = QLabel("--")
        self.value.setFont(T.f_value_lg() if large else T.f_value())
        self.value.setStyleSheet(f"color: {T.INK}")
        row.addWidget(self.value)
        self.unit = QLabel(unit)
        self.unit.setFont(T.f_unit())
        self.unit.setStyleSheet(f"color: {T.INK_FAINT}")
        row.addWidget(self.unit, 0, Qt.AlignmentFlag.AlignBottom)
        row.addStretch(1)
        v.addLayout(row)

    def set(self, text: str, color: Optional[str] = None, unit: Optional[str] = None) -> None:
        # color=None se resuelve aqui y no en la firma: el valor por defecto se
        # evaluaria al importar y quedaria atado al tema de ese momento (AGENTS 4.4).
        self.value.setText(text)
        self.value.setStyleSheet(f"color: {color or T.INK}")
        if unit is not None:
            self.unit.setText(unit)


# ---------------------------------------------------------------------------
# Controles
# ---------------------------------------------------------------------------

class SliderRow(QWidget):
    """Deslizador con su nombre y su valor en la misma fila.

    Emite `moved` de forma continua (para redibujar mientras se arrastra) y
    `settled` al soltar (para el calculo completo, mas caro).
    """

    moved = Signal(float)
    settled = Signal(float)

    def __init__(self, name: str, lo: float, hi: float, value: float,
                 step: float = 1.0, fmt: str = "{:.0f}", unit: str = "",
                 tip: str = "", parent=None):
        super().__init__(parent)
        self._lo, self._step, self._fmt = lo, step, fmt
        if tip:
            self.setToolTip(tip)

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(3)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self.name = panel_label(name)
        row.addWidget(self.name)
        row.addStretch(1)
        self.val = QLabel("")
        self.val.setFont(T.font(10.5, 500, mono=True, tracking=-0.3))
        self.val.setStyleSheet(f"color: {T.INK}")
        row.addWidget(self.val)
        if unit:
            u = QLabel(unit)
            u.setFont(T.f_unit())
            u.setStyleSheet(f"color: {T.INK_FAINT}")
            row.addWidget(u)
        v.addLayout(row)

        self.sl = QSlider(Qt.Orientation.Horizontal)
        self.sl.setMinimum(0)
        self.sl.setMaximum(int(round((hi - lo) / step)))
        self.sl.setValue(int(round((value - lo) / step)))
        self.sl.setPageStep(max(1, self.sl.maximum() // 12))
        self.sl.valueChanged.connect(self._changed)
        self.sl.sliderReleased.connect(lambda: self.settled.emit(self.value()))
        v.addWidget(self.sl)

        self._sync_text()

    def value(self) -> float:
        return self._lo + self.sl.value() * self._step

    def set_value(self, x: float) -> None:
        self.sl.blockSignals(True)
        self.sl.setValue(int(round((x - self._lo) / self._step)))
        self.sl.blockSignals(False)
        self._sync_text()

    def _sync_text(self) -> None:
        self.val.setText(self._fmt.format(self.value()))

    def _changed(self, _v: int) -> None:
        self._sync_text()
        self.moved.emit(self.value())
        if not self.sl.isSliderDown():      # teclado o rueda: ya esta asentado
            self.settled.emit(self.value())

    def setEnabled(self, on: bool) -> None:  # noqa: N802 - API de Qt
        super().setEnabled(on)
        c = T.INK if on else T.INK_GHOST
        self.val.setStyleSheet(f"color: {c}")
        self.name.setStyleSheet(
            f"color: {T.INK_FAINT if on else T.INK_GHOST}")


class LabeledCombo(QWidget):
    changed = Signal(str)

    def __init__(self, name: str, items: Iterable[tuple[str, str]],
                 current: str = "", tip: str = "", parent=None):
        super().__init__(parent)
        if tip:
            self.setToolTip(tip)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        self.name = panel_label(name)
        v.addWidget(self.name)
        self.combo = QComboBox()
        self.combo.setFont(T.f_body())
        for key, label in items:
            self.combo.addItem(label, key)
        if current:
            i = self.combo.findData(current)
            if i >= 0:
                self.combo.setCurrentIndex(i)
        self.combo.currentIndexChanged.connect(
            lambda _i: self.changed.emit(self.combo.currentData()))
        v.addWidget(self.combo)

    def value(self) -> str:
        return self.combo.currentData()

    def set_value(self, key: str) -> None:
        i = self.combo.findData(key)
        if i >= 0:
            self.combo.blockSignals(True)
            self.combo.setCurrentIndex(i)
            self.combo.blockSignals(False)


class Segmented(QWidget):
    """Selector segmentado pintado a mano.

    Qt no ofrece una regla de un pixel ni un estado de foco con el control que
    hace falta aqui, asi que se pinta: rectangulo unico, divisiones internas, y
    el segmento activo marcado por una barra inferior del color de la senal.
    """

    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]], current: str = "",
                 height: int = 30, min_seg: int = 46, parent=None):
        super().__init__(parent)
        self.options = options
        self.current = current or options[0][0]
        self._hover = -1
        self._focus = -1
        self.setFixedHeight(height)
        self.setMinimumWidth(min_seg * len(options))
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    # -- estado -------------------------------------------------------------
    def set_value(self, key: str) -> None:
        if key != self.current:
            self.current = key
            self.update()

    def _index_at(self, x: float) -> int:
        w = self.width() / len(self.options)
        return max(0, min(len(self.options) - 1, int(x // w)))

    # -- interaccion --------------------------------------------------------
    def mouseMoveEvent(self, e):  # noqa: N802
        i = self._index_at(e.position().x())
        if i != self._hover:
            self._hover = i
            self.update()

    def leaveEvent(self, e):  # noqa: N802
        self._hover = -1
        self.update()

    def mousePressEvent(self, e):  # noqa: N802
        i = self._index_at(e.position().x())
        key = self.options[i][0]
        if key != self.current:
            self.current = key
            self.update()
            self.changed.emit(key)

    def keyPressEvent(self, e):  # noqa: N802
        keys = [o[0] for o in self.options]
        i = keys.index(self.current)
        if e.key() in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            i = max(0, i - 1)
        elif e.key() in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            i = min(len(keys) - 1, i + 1)
        else:
            return super().keyPressEvent(e)
        if keys[i] != self.current:
            self.current = keys[i]
            self.update()
            self.changed.emit(self.current)

    KEY_REASONS = (Qt.FocusReason.TabFocusReason,
                   Qt.FocusReason.BacktabFocusReason,
                   Qt.FocusReason.ShortcutFocusReason)

    def focusInEvent(self, e):  # noqa: N802
        self._focus = 1 if e.reason() in self.KEY_REASONS else -1
        self.update()

    def focusOutEvent(self, e):  # noqa: N802
        self._focus = -1
        self.update()

    # -- pintado ------------------------------------------------------------
    def paintEvent(self, _e):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        n = len(self.options)
        w = self.width() / n
        h = self.height()
        enabled = self.isEnabled()

        p.fillRect(self.rect(), QColor(T.PANEL))

        for i, (key, label) in enumerate(self.options):
            r = QRectF(i * w, 0, w, h)
            active = key == self.current
            if active:
                p.fillRect(r, QColor(T.RAISED_HI))
            elif enabled and i == self._hover:
                p.fillRect(r, QColor(T.BEZEL))

            if not enabled:
                col = T.INK_GHOST
            elif active:
                col = T.INK
            elif i == self._hover:
                col = T.INK_DIM
            else:
                col = T.INK_FAINT
            p.setPen(QPen(QColor(col)))
            p.setFont(T.f_label() if active else T.f_body())
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, label)

            if active:
                bar = QColor(T.SIGNAL if enabled else T.RULE_STRONG)
                p.fillRect(QRectF(i * w, h - 2, w, 2), bar)

            if i:
                p.setPen(QPen(QColor(T.RULE), 1))
                p.drawLine(int(i * w), 5, int(i * w), h - 5)

        p.setPen(QPen(QColor(T.RULE_STRONG), 1))
        p.drawRect(QRectF(0.5, 0.5, self.width() - 1, h - 1))

        if self._focus > 0 and enabled:
            p.setPen(QPen(QColor(T.SIGNAL), 1, Qt.PenStyle.DashLine))
            p.drawRect(QRectF(2.5, 2.5, self.width() - 5, h - 5))
        p.end()


def checkbox(text: str, checked: bool = True, tip: str = "") -> QCheckBox:
    cb = QCheckBox(text)
    cb.setFont(T.f_body())
    cb.setChecked(checked)
    if tip:
        cb.setToolTip(tip)
    return cb


class SectionHead(QWidget):
    """Cabecera de seccion: numero, nombre y que hay que hacer en ella."""

    def __init__(self, num: str, title: str, text: str = "", parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(2, 0, 2, 2)
        h.setSpacing(12)
        n = QLabel(num)
        n.setFont(T.font(15, 600, mono=True))
        n.setStyleSheet(f"color: {T.SIGNAL}")
        h.addWidget(n, 0, Qt.AlignmentFlag.AlignVCenter)
        t = QLabel(title)
        t.setFont(T.f_title())
        t.setStyleSheet(f"color: {T.INK}")
        h.addWidget(t, 0, Qt.AlignmentFlag.AlignVCenter)
        self.text = text_label(text, T.f_body(), T.INK_DIM, wrap=True)
        h.addWidget(self.text, 1, Qt.AlignmentFlag.AlignVCenter)

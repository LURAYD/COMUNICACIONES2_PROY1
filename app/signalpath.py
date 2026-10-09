"""El camino de la senal: la cadena TX -> canal -> RX como barra de navegacion.

Esta es la idea de la aplicacion. En lugar de pestanas con nombres de graficas,
la navegacion es el propio enlace: se elige un punto de derivacion y los
instrumentos muestran la senal *ahi*. Ver el mismo simbolo antes y despues de
una etapa es lo que ensena; comparar dos figuras de un PDF, no.

Bajo los nodos va el **perfil de apertura del ojo** a lo largo de la cadena. Es
una sola magnitud medida en los ocho puntos - un solo eje, sin mezclar escalas -
y dibuja de un vistazo el argumento entero del proyecto: el ojo nace abierto, el
canal lo cierra, y el ecualizador lo vuelve a abrir.
"""

from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QColor, QFontMetricsF, QPainter, QPainterPath, QPen,
                           QPolygonF)
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import theme as T
from .engine import STAGES, SYMBOL


NODE_Y = 21          # linea de nodos
TITLE_Y = 38
SUB_Y = 53
PROF_TOP = 66        # banda del perfil
PROF_H = 46
HEIGHT = PROF_TOP + PROF_H + 20


class SignalPath(QWidget):
    """Ocho etapas seleccionables con su perfil de calidad debajo."""

    selected = Signal(str)

    def __init__(self, stages=STAGES, parent=None):
        super().__init__(parent)
        # Por defecto la cadena entera; la seccion de analisis pasa solo las
        # etapas del receptor.
        self.stages = tuple(stages)
        self.setObjectName("PathBar")
        self.setFixedHeight(HEIGHT)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.current = self.stages[-1].key
        self._hover = -1
        self._focused = False
        self._open: dict[str, float] = {}
        self._live = False

    # -- datos ---------------------------------------------------------------
    def set_openings(self, values: dict[str, float]) -> None:
        self._open = values
        self._live = True
        self.update()

    def clear_data(self) -> None:
        self._live = False
        self.update()

    def set_current(self, key: str) -> None:
        if key != self.current:
            self.current = key
            self.update()

    # -- geometria -----------------------------------------------------------
    def _cell_w(self) -> float:
        return self.width() / len(self.stages)

    def _cx(self, i: int) -> float:
        return (i + 0.5) * self._cell_w()

    def _index_at(self, x: float) -> int:
        return max(0, min(len(self.stages) - 1, int(x // self._cell_w())))

    # -- interaccion ---------------------------------------------------------
    def mouseMoveEvent(self, e):  # noqa: N802
        i = self._index_at(e.position().x())
        if i != self._hover:
            self._hover = i
            self.setToolTip(self.stages[i].story)
            self.update()

    def leaveEvent(self, e):  # noqa: N802
        self._hover = -1
        self.update()

    def mousePressEvent(self, e):  # noqa: N802
        i = self._index_at(e.position().x())
        self._select(self.stages[i].key)

    def keyPressEvent(self, e):  # noqa: N802
        keys = [s.key for s in self.stages]
        i = keys.index(self.current)
        if e.key() in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            i = max(0, i - 1)
        elif e.key() in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            i = min(len(keys) - 1, i + 1)
        elif e.key() == Qt.Key.Key_Home:
            i = 0
        elif e.key() == Qt.Key.Key_End:
            i = len(keys) - 1
        else:
            return super().keyPressEvent(e)
        self._select(keys[i])

    KEY_REASONS = (Qt.FocusReason.TabFocusReason,
                   Qt.FocusReason.BacktabFocusReason,
                   Qt.FocusReason.ShortcutFocusReason)

    def focusInEvent(self, e):  # noqa: N802
        self._focused = e.reason() in self.KEY_REASONS
        self.update()

    def focusOutEvent(self, e):  # noqa: N802
        self._focused = False
        self.update()

    def _select(self, key: str) -> None:
        if key != self.current:
            self.current = key
            self.update()
            self.selected.emit(key)

    # -- pintado -------------------------------------------------------------
    def paintEvent(self, _e):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), QColor(T.PANEL))

        n = len(self.stages)
        cur_i = [s.key for s in self.stages].index(self.current)

        self._paint_profile(p, cur_i)
        self._paint_connector(p, n, cur_i)
        self._paint_nodes(p, cur_i)

        p.setPen(QPen(QColor(T.RULE), 1))
        p.drawRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1))
        p.end()

    # ---- conector ----------------------------------------------------------
    def _paint_connector(self, p: QPainter, n: int, cur_i: int) -> None:
        x0, x1 = self._cx(0), self._cx(n - 1)
        p.setPen(QPen(QColor(T.RULE_STRONG), 1))
        p.drawLine(QPointF(x0, NODE_Y), QPointF(x1, NODE_Y))
        # El tramo ya recorrido se marca con el color de la senal: la senal ha
        # pasado por ahi.
        if cur_i > 0:
            p.setPen(QPen(QColor(T.SIGNAL), 1))
            p.drawLine(QPointF(x0, NODE_Y), QPointF(self._cx(cur_i), NODE_Y))

    # ---- nodos y rotulos ---------------------------------------------------
    def _paint_nodes(self, p: QPainter, cur_i: int) -> None:
        w = self._cell_w()
        for i, st in enumerate(self.stages):
            cx = self._cx(i)
            active = i == cur_i
            hover = i == self._hover and not active
            passed = i < cur_i

            # nodo
            r = 4.5 if active else 3.0
            if active:
                p.setBrush(QColor(T.SIGNAL))
                p.setPen(QPen(QColor(T.PANEL), 2))
            elif passed:
                p.setBrush(QColor(T.SIGNAL))
                p.setPen(QPen(QColor(T.PANEL), 1.5))
            else:
                p.setBrush(QColor(T.PANEL))
                p.setPen(QPen(QColor(T.INK_FAINT if hover else T.RULE_STRONG), 1.5))
            p.drawEllipse(QPointF(cx, NODE_Y), r, r)
            p.setBrush(Qt.BrushStyle.NoBrush)

            # halo del nodo activo: el unico adorno, y marca el foco de lectura
            if active:
                p.setPen(QPen(T.rgba(T.SIGNAL, 0.30), 1))
                p.drawEllipse(QPointF(cx, NODE_Y), 8.5, 8.5)

            cell = QRectF(i * w, 0, w, self.height())
            title_r = QRectF(cell.x() + 3, TITLE_Y - 9, w - 6, 15)
            sub_r = QRectF(cell.x() + 3, SUB_Y - 8, w - 6, 13)

            p.setPen(QPen(QColor(
                T.INK if active else (T.INK_DIM if hover or passed else T.INK_FAINT))))
            p.setFont(T.font(9.5, 600 if active else 500))
            p.drawText(title_r, Qt.AlignmentFlag.AlignCenter, st.title)

            p.setPen(QPen(QColor(T.INK_FAINT if active or hover else T.INK_GHOST)))
            p.setFont(T.font(8.2, 400))
            fm = QFontMetricsF(p.font())
            p.drawText(sub_r, Qt.AlignmentFlag.AlignCenter,
                       fm.elidedText(st.sub, Qt.TextElideMode.ElideRight, w - 8))

    # ---- perfil de apertura del ojo ----------------------------------------
    def _paint_profile(self, p: QPainter, cur_i: int) -> None:
        top, h = PROF_TOP, PROF_H
        base = top + h
        w = self._cell_w()

        # Rejilla en 0, 0,5 y 1. Sin rotulos numericos en los ejes: la escala se
        # nombra una sola vez y el valor de la etapa activa se imprime grande.
        # Rotular cada linea obligaria a un margen que desalinearia los escalones
        # de sus etapas, que es justamente lo que este perfil tiene que mostrar.
        for frac in (0.0, 0.5, 1.0):
            y = base - frac * h
            solid = frac in (0.0, 1.0)
            p.setPen(QPen(QColor(T.RULE_STRONG if solid else T.INK_GHOST), 1,
                          Qt.PenStyle.SolidLine if solid else Qt.PenStyle.DotLine))
            p.drawLine(QPointF(7, y), QPointF(self.width() - 7, y))

        # El nombre del eje va FUERA de la banda, en el margen inferior. Dentro
        # chocaba con el valor de la etapa activa cada vez que esa etapa tenia
        # el ojo abierto del todo, que es justo el caso de la primera.
        p.setFont(T.font(7.5, 600, tracking=0.9, caps=True))
        p.setPen(QPen(QColor(T.INK_GHOST)))
        p.drawText(QRectF(10, base + 3, self.width() - 20, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"apertura del ojo  ·  0 a 1  ·  medida en los {len(self.stages)} puntos")

        if not self._live:
            p.setPen(QPen(QColor(T.INK_GHOST)))
            p.setFont(T.font(9, 400))
            p.drawText(QRectF(0, top, self.width(), h), Qt.AlignmentFlag.AlignCenter,
                       "sin medida")
            return

        # escalon: un valor por etapa, constante dentro de su celda
        vals = []
        for st in self.stages:
            v = self._open.get(st.key, float("nan"))
            vals.append(0.0 if (v is None or math.isnan(v)) else max(0.0, min(1.0, v)))

        path = QPainterPath()
        fill = QPainterPath()
        fill.moveTo(0, base)
        for i, v in enumerate(vals):
            y = base - v * h
            x0, x1 = i * w, (i + 1) * w
            if i == 0:
                path.moveTo(x0, y)
            else:
                path.lineTo(x0, y)
            path.lineTo(x1, y)
            fill.lineTo(x0, y)
            fill.lineTo(x1, y)
        fill.lineTo(self.width(), base)
        fill.closeSubpath()

        p.fillPath(fill, T.rgba(T.SIGNAL, T.PROFILE_FILL))
        p.setPen(QPen(QColor(T.SIGNAL_HI), 1.8))
        p.drawPath(path)

        # columna de la etapa activa, y su valor rotulado
        x0 = cur_i * w
        p.fillRect(QRectF(x0, top, w, h), T.rgba(T.SIGNAL, 0.12))
        v = vals[cur_i]
        y = base - v * h
        p.setBrush(QColor(T.SIGNAL))
        p.setPen(QPen(QColor(T.PANEL), 1.5))
        p.drawEllipse(QPointF(self._cx(cur_i), y), 3.4, 3.4)
        p.setBrush(Qt.BrushStyle.NoBrush)

        # El rotulo se coloca del lado que tenga sitio DENTRO de la banda: si el
        # escalon esta arriba, debajo del punto; si esta abajo, encima. Asi nunca
        # invade la fila de subtitulos ni se sale del perfil.
        p.setPen(QPen(QColor(T.INK)))
        p.setFont(T.font(9.5, 500, mono=True, tracking=-0.3))
        above = y - top > 20
        lab_y = (y - 17) if above else (y + 3)
        lab_y = min(max(lab_y, top + 1), base - 15)
        p.drawText(QRectF(x0, lab_y, w, 15), Qt.AlignmentFlag.AlignCenter,
                   f"{v:.3f}")

        if self._focused:
            p.setPen(QPen(QColor(T.SIGNAL), 1, Qt.PenStyle.DashLine))
            p.drawRect(QRectF(x0 + 1.5, 3.5, w - 3, self.height() - 7))

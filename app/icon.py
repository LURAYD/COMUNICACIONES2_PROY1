"""Icono de la aplicación, dibujado en lugar de heredado.

Una constelación QPSK: cuatro puntos y los ejes I/Q. Es lo que la aplicación
muestra en su primer panel, así que el icono dice lo que hay dentro sin
depender de un logotipo prestado. Se genera a varios tamaños porque Windows
elige uno distinto para la barra de tareas, el escritorio y el conmutador de
ventanas; a 16 px sobreviven los cuatro puntos y poco más, y por eso el
dibujo no tiene nada más.

    python -m app.icon        regenera app/icon.ico
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

from . import theme as T

ICON_PATH = Path(__file__).parent / "icon.ico"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def render(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(QColor(T.BEZEL))

    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    s = size / 64.0          # todo se define sobre una retícula de 64

    # Ejes I/Q
    if size >= 24:
        p.setPen(QPen(QColor(T.RULE_STRONG), max(1.0, 1.0 * s)))
        p.drawLine(QPointF(8 * s, 32 * s), QPointF(56 * s, 32 * s))
        p.drawLine(QPointF(32 * s, 8 * s), QPointF(32 * s, 56 * s))

    # Los cuatro puntos, con su halo de fósforo
    r_core = max(1.6, 5.0 * s)
    r_halo = r_core * 2.1
    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        c = QPointF((32 + dx * 15) * s, (32 + dy * 15) * s)
        if size >= 32:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(T.rgba(T.SIGNAL, 0.22))
            p.drawEllipse(c, r_halo, r_halo)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T.SIGNAL_HI))
        p.drawEllipse(c, r_core, r_core)
    p.end()
    return pm


def build() -> QIcon:
    ic = QIcon()
    for s in SIZES:
        ic.addPixmap(render(s))
    return ic


def load() -> QIcon:
    """El icono del disco si existe; si no, uno dibujado al vuelo."""
    if ICON_PATH.exists():
        ic = QIcon(str(ICON_PATH))
        if not ic.isNull():
            return ic
    return build()


def write() -> Path:
    render(256).save(str(ICON_PATH), "ICO")
    return ICON_PATH


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication([])
    T.load_fonts()
    print("escrito:", write())

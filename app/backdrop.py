"""El fondo ilustrado de la aplicación.

La ilustración cubre la ventana entera y sobre ella se apoyan las superficies:
el rail y la cabecera van en blanco translúcido, de modo que la imagen asoma y
tiñe el chasis, mientras que los paneles de datos son blanco opaco. Esa es toda
la jerarquía — **la ilustración es el suelo, los datos son el papel**.

Sobre el velo. La imagen va a un 62 % de velo blanco, no por timidez: una
constelación de 3 000 puntos sobre una ilustración a plena saturación deja de
ser legible, y este programa existe para leer medidas. El velo la convierte en
una aguada pastel que conserva su composición y su color sin disputarle el
contraste a la señal.

Si el fichero no está, se pinta el color liso y no ocurre nada más.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from . import theme as T


class Backdrop(QWidget):
    """Contenedor raíz que pinta la ilustración bajo todo lo demás."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Backdrop")
        self._src: Optional[QPixmap] = None
        self._scaled: Optional[QPixmap] = None
        self._scaled_for = (0, 0)

        path = T.background_path()
        if path is not None:
            pm = QPixmap(str(path))
            if not pm.isNull():
                self._src = pm

    # -- escalado ------------------------------------------------------------
    def _cover(self, w: int, h: int) -> Optional[QPixmap]:
        """Escala la imagen para CUBRIR la ventana, recortando el sobrante.

        Se guarda la versión escalada porque reescalar medio megapíxel en cada
        `paintEvent` costaría más que dibujar todas las gráficas juntas.
        """
        if self._src is None or w <= 0 or h <= 0:
            return None
        if self._scaled is not None and self._scaled_for == (w, h):
            return self._scaled
        self._scaled = self._src.scaled(
            w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation)
        self._scaled_for = (w, h)
        return self._scaled

    # -- pintado -------------------------------------------------------------
    def paintEvent(self, _e):  # noqa: N802
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(T.GROUND))

        pm = self._cover(w, h)
        if pm is not None:
            # Centrado sobre el eje mayor: al recortar se pierde por los bordes,
            # nunca por un lado solo.
            p.drawPixmap(QPointF((w - pm.width()) / 2.0,
                                 (h - pm.height()) / 2.0), pm)
            veil = QColor("#ffffff" if T.MODE == "light" else T.GROUND)
            veil.setAlphaF(T.SCRIM)
            p.fillRect(self.rect(), veil)
        p.end()

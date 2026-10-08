"""Banco de pruebas: la vista en vivo.

Camino de la senal arriba, cuatro instrumentos en el centro, lectura de medidas
abajo. Todo responde al mismo resultado de simulacion; al cambiar de punto de
derivacion no se recalcula nada, solo se redibuja lo que ya esta medido.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QVBoxLayout, QWidget)

from . import theme as T
from .displays import Constellation, Convergence, Eye, Spectrum
from .engine import STAGE_BY_KEY, SYMBOL, SimResult
from .signalpath import SignalPath
from .widgets import HRule, Panel, Readout, panel_label, text_label


def fmt_ber(ber: float, bits: int) -> tuple[str, str]:
    """BER con su caso de cero errores dicho como lo que es: una cota."""
    if bits and ber <= 0:
        return f"< {1.0 / bits:.1e}".replace("e-0", "e-"), "cota"
    return f"{ber:.2e}".replace("e-0", "e-"), ""


def _sci(x: float) -> str:
    return f"{x:.2e}".replace("e-0", "e-").replace("e+0", "e+")


# Por encima de esta BER el enlace no es utilizable aunque la trama enganche.
BER_ENLACE = 1e-2


def link_state(res: SimResult) -> str:
    """Estado del enlace: el sincronismo de trama solo no basta."""
    if not res.locked:
        return "unlock"
    ber = res.stats.get("ber", 0.0)
    return "locked" if ber < BER_ENLACE else "weak"


class StatusDot(QWidget):
    """Enganche del receptor. Color + texto: nunca solo color."""

    def __init__(self, parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(7)
        self.dot = QWidget()
        self.dot.setFixedSize(7, 7)
        h.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignVCenter)
        self.txt = text_label("", T.f_label(), T.INK_DIM)
        h.addWidget(self.txt)
        self.set_state("idle")

    def set_state(self, state: str, text: str = "") -> None:
        col, label = {
            "idle":    (T.INK_GHOST, "en espera"),
            "busy":    (T.WARNING, "calculando"),
            "locked":  (T.GOOD, "receptor enganchado"),
            "weak":    (T.WARNING, "enganchado · BER alta"),
            "unlock":  (T.CRITICAL, "sin enganche"),
            "error":   (T.CRITICAL, "error"),
        }[state]
        self.dot.setStyleSheet(f"background: {col}; border-radius: 3px;")
        self.txt.setText(text or label)
        self.txt.setStyleSheet(
            f"color: {T.INK_DIM if state in ('idle', 'busy') else col};")


class ReadoutBar(QWidget):
    """Las medidas del enlace completo, en una sola fila tabular."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ReadoutBar")
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 12, 20, 12)
        v.setSpacing(10)

        self.ber = Readout("BER", "", large=True,
                           tip="Tasa de error de bit medida sobre la carga útil.")
        self.theory = Readout("Teórica AWGN", "",
                              tip="BER teórica para esta modulación y Eb/N0 en canal\n"
                                  "AWGN puro. La distancia a la medida es la\n"
                                  "penalización de implementación más la del canal.")
        self.ser = Readout("SER", "")
        self.evm = Readout("EVM", "%",
                           tip="Magnitud del vector de error sobre los símbolos decididos.")
        self.mse = Readout("MSE residual", "dB",
                           tip="Error cuadrático medio residual en régimen permanente.")
        self.conv = Readout("Convergencia", "simb",
                            tip="Primer símbolo a partir del cual la curva de MSE suavizada\n"
                                "se mantiene a menos de 3 dB del MSE de régimen permanente.\n"
                                "Solo aplica a ecualizadores adaptativos (LMS, RLS, CMA).")
        self.cost = Readout("Coste", "mult/simb",
                            tip="Multiplicaciones reales por símbolo del ecualizador.\n"
                                "LMS es O(N); RLS es O(N²).")
        self.eta = Readout("Eficiencia", "b/s/Hz",
                           tip="Rb / B = k / (1 + roll-off).")

        rows = ((self.ber, self.theory, self.ser, self.evm, self.eta),
                (self.mse, self.conv, self.cost))
        for n, items in enumerate(rows):
            h = QHBoxLayout()
            h.setSpacing(0)
            for i, r in enumerate(items):
                if i:
                    sep = QWidget()
                    sep.setFixedWidth(1)
                    sep.setStyleSheet(f"background: {T.RULE_STRONG};")
                    h.addSpacing(16)
                    h.addWidget(sep)
                    h.addSpacing(16)
                r.setMinimumWidth(r.sizeHint().width())
                h.addWidget(r)
            h.addStretch(1)
            if n == 1:
                self.status = StatusDot()
                h.addWidget(self.status, 0, Qt.AlignmentFlag.AlignVCenter)
            v.addLayout(h)

    def clear(self) -> None:
        for r in (self.ber, self.theory, self.ser, self.evm, self.mse,
                  self.conv, self.cost, self.eta):
            r.set("--", T.INK_GHOST)

    def update_from(self, res: SimResult) -> None:
        s = res.stats
        txt, note = fmt_ber(s["ber"], int(s.get("ber_bits", 0)))
        # Umbrales de lectura, no de aprobado: 1e-3 es la referencia que usa el
        # informe para comparar modulaciones.
        col = T.GOOD if s["ber"] < 1e-3 else (T.WARNING if s["ber"] < 5e-2 else T.CRITICAL)
        self.ber.set(txt, col, unit=note)
        self.theory.set(_sci(res.theory_ber) if math.isfinite(res.theory_ber) else "--",
                        T.INK_DIM)
        self.ser.set(_sci(s["ser"]), T.INK)
        self.evm.set(f"{s['evm_pct']:.1f}", T.INK)

        mse_db = s.get("eq_mse_db")
        self.mse.set("--" if mse_db is None or not math.isfinite(mse_db)
                     else f"{mse_db:.1f}", T.INK)
        c = res.eq_conv
        if res.req.eq_kind in ("none", "zf", "mmse"):
            self.conv.set("—", T.INK_GHOST, unit="")
            if res.req.eq_kind == "none":
                self.mse.set("—", T.INK_GHOST)
        elif c is None or c < 0:
            self.conv.set("no converge", T.SERIOUS, unit="")
        else:
            self.conv.set(f"{c}", T.INK, unit="simb")
        self.cost.set(f"{res.eq_flops}", T.INK)
        self.eta.set(f"{s.get('eta_bps_hz', float('nan')):.2f}", T.INK)
        self.status.set_state(link_state(res))


class Bench(QWidget):
    """Vista en vivo completa."""

    request_run = Signal(bool)     # True = corrida asentada (con comparacion)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.res: Optional[SimResult] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        center = QWidget()
        cv = QVBoxLayout(center)
        cv.setContentsMargins(18, 16, 18, 16)
        cv.setSpacing(12)

        self.path = SignalPath()
        cv.addWidget(self.path)

        cap = QWidget()
        ch = QHBoxLayout(cap)
        ch.setContentsMargins(2, 0, 2, 0)
        ch.setSpacing(10)
        self.cap_tag = panel_label("Punto de derivación", T.SIGNAL)
        ch.addWidget(self.cap_tag, 0, Qt.AlignmentFlag.AlignTop)
        self.caption = text_label("", T.f_body(), T.INK_DIM, wrap=True)
        ch.addWidget(self.caption, 1)
        cv.addWidget(cap)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        self.p_const = Panel("Constelación")
        self.const = Constellation()
        self.p_const.set_content(self.const)

        # Dos ojos lado a lado tras el filtro adaptado: antes y después del
        # ecualizador. En las etapas previas solo se usa el primero.
        self.p_eye = Panel("Diagrama de ojo")
        eyes = QWidget()
        eh = QHBoxLayout(eyes)
        eh.setContentsMargins(0, 0, 0, 0)
        eh.setSpacing(0)
        self.eye = Eye()
        self.eye_after = Eye()
        eh.addWidget(self.eye, 1)
        eh.addWidget(self.eye_after, 1)
        self.eye_after.setVisible(False)
        self.p_eye.set_content(eyes)

        self.p_spec = Panel("Densidad espectral")
        self.spec = Spectrum()
        self.p_spec.set_content(self.spec)

        self.p_conv = Panel("Convergencia del ecualizador")
        self.conv = Convergence()
        self.p_conv.set_content(self.conv)

        grid.addWidget(self.p_const, 0, 0)
        grid.addWidget(self.p_eye, 0, 1)
        grid.addWidget(self.p_spec, 1, 0)
        grid.addWidget(self.p_conv, 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 3)
        grid.setRowStretch(1, 2)
        cv.addLayout(grid, 1)

        root.addWidget(center, 1)
        self.readout = ReadoutBar()
        root.addWidget(self.readout)

        self.path.selected.connect(self._on_stage)
        self._show_stage(self.path.current, animate=False)

    # -- ciclo ---------------------------------------------------------------
    def set_busy(self, busy: bool) -> None:
        if busy and self.res is None:
            self.readout.status.set_state("busy")
        elif busy:
            self.readout.status.set_state("busy")
        elif self.res is not None:
            self.readout.status.set_state(link_state(self.res))

    def set_error(self, msg: str) -> None:
        self.readout.status.set_state("error", msg[:70])

    def apply(self, res: SimResult) -> None:
        first = self.res is None
        self.res = res
        self.readout.update_from(res)
        self.path.set_openings({k: t.opening for k, t in res.taps.items()})
        self.const.set_reference(res.ideal)
        self.spec.show(res.psd, res.req.beta)
        self.conv.show(res)
        self._show_stage(self.path.current, animate=not first)

    def _on_stage(self, key: str) -> None:
        self._show_stage(key, animate=True)

    def _show_stage(self, key: str, animate: bool) -> None:
        st = STAGE_BY_KEY[key]
        self.caption.setText(st.story)
        self.cap_tag.setText(st.title)

        if self.res is None:
            return
        tap = self.res.taps[key]

        self.p_const.set_title(f"Constelación  ·  {st.title}")
        if tap.pts is not None:
            self.const.autoscale(tap.pts)
            self.const.show_tap(tap.pts, tap.kind, animate=animate)
        if st.kind == SYMBOL and key != "tx":
            self.p_const.set_note(f"EVM {tap.evm:.1f} %")
        elif key == "tx":
            self.p_const.set_note("referencia ideal")
        else:
            self.p_const.set_note("muestreada en el instante óptimo")

        self._show_eye(key, st)

        bw = (1.0 + self.res.req.beta)
        self.p_spec.set_note(f"B = {bw:.2f} Rs")
        k = self.res.req.eq_kind.upper()
        self.p_conv.set_note("sin ecualizador" if k == "NONE" else f"método {k}")

    def _show_eye(self, key: str, st) -> None:
        """Un ojo hasta el canal; desde el filtro adaptado, antes y después.

        Las etapas desde la temporización van a 1 muestra/símbolo y no tienen
        forma de onda propia: se muestra la salida del filtro adaptado (antes)
        y esa misma señal pasada por los coeficientes del ecualizador (después).
        """
        res = self.res

        def col(op: float) -> str:
            return T.GOOD if op > 0.5 else (T.WARNING if op > 0.2 else T.CRITICAL)

        if key in ("tx", "rrc", "chan"):
            src = "rrc" if key == "tx" else key
            tap = res.taps[src]
            self.eye_after.setVisible(False)
            self.eye.set_caption("")
            self.eye.show_wave(tap.wave, res.sps, tap.opening)
            self.p_eye.set_title(f"Diagrama de ojo  ·  {STAGE_BY_KEY[src].title}")
            self.p_eye.set_note(f"apertura {tap.opening:.3f}", col(tap.opening))
            return

        before = res.taps["mf"]
        self.eye_after.setVisible(True)
        self.eye.set_caption(f"antes del ecualizador  ·  {before.opening:.3f}",
                             col(before.opening))
        self.eye.show_wave(before.wave, res.sps, before.opening)
        eq = res.req.eq_kind.upper()
        self.p_eye.set_title("Diagrama de ojo  ·  antes y después del ecualizador")
        if res.eye_after is None:
            self.eye_after.set_caption("después del ecualizador")
            self.eye_after.show_wave(None, res.sps, float("nan"))
            self.eye_after._unavailable("Sin ecualizador.\nElige uno en el rail.")
            self.p_eye.set_note(f"apertura {before.opening:.3f}", col(before.opening))
            return
        after = res.opening_after
        self.eye_after.set_caption(f"después del {eq}  ·  {after:.3f}", col(after))
        self.eye_after.show_wave(res.eye_after, res.sps, after)
        self.p_eye.set_note(f"apertura {before.opening:.3f} → {after:.3f}", col(after))

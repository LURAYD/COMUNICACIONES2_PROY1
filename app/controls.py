"""Rail de controles: los parametros del enlace, agrupados como en la guia.

Senal / Canal / Receptor - el mismo orden en que la guia enumera los requisitos.
Cada control se desactiva cuando el escenario o el metodo elegido lo dejan sin
efecto (el perfil multitrayecto no existe en el escenario A; lambda solo gobierna
al RLS), porque un control que no hace nada miente sobre lo que se esta midiendo.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QHBoxLayout, QLineEdit, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from . import theme as T
from .engine import Request
from .widgets import (HRule, LabeledCombo, Segmented, SliderRow, checkbox,
                      panel_label, text_label)

SCENARIOS = [
    ("A", "A"), ("B", "B"), ("C", "C"), ("D", "D"),
]
SCENARIO_NOTE = {
    "A": "Solo AWGN. Es el canal de referencia: valida la cadena contra la teoría.",
    "B": "Multitrayectoria + AWGN. Aísla el efecto de la ISI, sin errores de sincronismo.",
    "C": "Canal degradado: multitrayectoria, AWGN, offset de frecuencia, de fase y de reloj.",
    "D": "Como C, más desvanecimiento Rayleigh variable en el tiempo (espectro de Jakes).",
}

MODS = [("qpsk", "QPSK"), ("8psk", "8PSK"), ("16qam", "16-QAM"), ("64qam", "64-QAM")]
PROFILES = [("flat", "Plano"), ("mild", "Leve"), ("moderate", "Moderado"),
            ("severe", "Severo"), ("aleatorio", "Aleatorio (semilla)"),
            ("manual", "h escrita a mano")]
H_DEFAULT = "0, 0.2, 1, 0, 0.8"
EQS = [("none", "Sin ecualizar"), ("lms", "LMS  (método A)"),
       ("rls", "RLS  (método B)"), ("zf", "Zero-Forcing"), ("mmse", "MMSE"),
       ("cma", "CMA (ciego)")]


def _group(title: str) -> tuple[QWidget, QVBoxLayout]:
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(15, 15, 15, 16)
    v.setSpacing(13)
    head = panel_label(title, T.INK_DIM)
    v.addWidget(head)
    return w, v


class Controls(QScrollArea):
    """Emite `changed` continuamente y `settled` cuando el gesto termina."""

    changed = Signal()
    settled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Rail")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setFixedWidth(262)

        host = QWidget()
        host.setObjectName("RailHost")
        root = QVBoxLayout(host)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ------------------------------------------------------------ SENAL
        g, v = _group("Señal")
        self.mod = LabeledCombo(
            "Modulación", MODS, "qpsk",
            tip="QPSK es la modulación obligatoria (requisito 4.3). La segunda\n"
                "modulación del proyecto es 16-QAM (requisito 4.4).")
        v.addWidget(self.mod)
        self.ebn0 = SliderRow(
            "Eb/N0", 0, 24, 12, 0.5, "{:.1f}", "dB",
            tip="Energía por bit entre densidad espectral de ruido.\n"
                "Es el eje de todas las curvas de BER.")
        v.addWidget(self.ebn0)
        self.beta = SliderRow(
            "Roll-off del RRC", 0.10, 0.90, 0.35, 0.05, "{:.2f}", "",
            tip="Exceso de ancho de banda del coseno alzado.\n"
                "B = Rs(1+β): más roll-off, más banda y ojo más robusto.")
        v.addWidget(self.beta)
        root.addWidget(g)
        root.addWidget(HRule(T.RULE_STRONG))

        # ------------------------------------------------------------ CANAL
        g, v = _group("Canal")
        self.scenario = Segmented(SCENARIOS, "C", height=32, min_seg=40)
        v.addWidget(self.scenario)
        self.scen_note = text_label(SCENARIO_NOTE["C"], T.f_small(), T.INK_FAINT,
                                    wrap=True)
        v.addWidget(self.scen_note)

        self.profile = LabeledCombo(
            "Perfil multitrayecto", PROFILES, "moderate",
            tip="Perfiles FIR de retardo y amplitud.\n"
                "Moderado: 4 ecos, τ_rms = 0,62 T.\n"
                "Aleatorio: h sorteado con una semilla (misma semilla, mismo h).\n"
                "A mano: un coeficiente por periodo de símbolo T.")
        v.addWidget(self.profile)

        # -- canal h: aleatorio con semilla o escrito a mano ------------------
        self.seed = SliderRow(
            "Semilla del canal", 0, 999, 7, 1, "{:.0f}", "",
            tip="Cada semilla da un canal h distinto y siempre el mismo:\n"
                "cursor 1 en el centro y 4 ecos uniformes en ±0,6.\n"
                "Los datos y el ruido no cambian con ella.")
        v.addWidget(self.seed)
        self.next_ch = QPushButton("Otro canal  (semilla + 1)")
        self.next_ch.setToolTip("Pasa a la semilla siguiente: un canal nuevo,\n"
                                "reproducible con esa misma semilla.")
        v.addWidget(self.next_ch)

        self.h_name = panel_label("Respuesta al impulso  h")
        v.addWidget(self.h_name)
        self.h_edit = QLineEdit(H_DEFAULT)
        self.h_edit.setFont(T.font(10, 400, mono=True))
        self.h_edit.setToolTip(
            "Coeficientes separados por comas, uno por periodo de símbolo T.\n"
            "El mayor es el cursor; 0 solo ocupa posición; admite complejos\n"
            "(0.3+0.2j). Se aplica al pulsar Intro o al salir del campo.")
        v.addWidget(self.h_edit)
        self.h_note = text_label("", T.f_small(), T.INK_FAINT, wrap=True)
        self.h_note.setFont(T.font(9, 400, mono=True))
        v.addWidget(self.h_note)
        self._h_ok = H_DEFAULT
        self.cfo = SliderRow(
            "Offset de frecuencia", 0.0, 0.010, 0.003, 0.0005, "{:.4f}", "Rs",
            tip="Como fracción de la tasa de símbolo. El límite de adquisición\n"
                "de Schmidl-Cox es Rs/(2L) = 0,78 %.")
        v.addWidget(self.cfo)
        self.phase = SliderRow(
            "Offset de fase", 0, 180, 37, 1, "{:.0f}", "grados")
        v.addWidget(self.phase)
        self.timing = SliderRow(
            "Error de temporización", 0.0, 0.5, 0.37, 0.01, "{:.2f}", "T",
            tip="Retardo fraccional de muestreo, en periodos de símbolo.")
        v.addWidget(self.timing)
        self.fd = SliderRow(
            "Doppler  fD/Rs", 0.0, 0.0010, 0.0002, 0.00002, "{:.5f}", "",
            tip="Solo en el escenario D. Gobierna la velocidad del desvanecimiento:\n"
                "es lo que hace relevante al factor de olvido del RLS.")
        v.addWidget(self.fd)
        root.addWidget(g)
        root.addWidget(HRule(T.RULE_STRONG))

        # --------------------------------------------------------- RECEPTOR
        g, v = _group("Receptor")
        self.eq = LabeledCombo(
            "Ecualizador", EQS, "lms",
            tip="La guía pide comparar dos estrategias.\n"
                "Método A = LMS normalizado, método B = RLS.")
        v.addWidget(self.eq)
        self.taps = SliderRow(
            "Longitud  N", 3, 61, 21, 2, "{:.0f}", "taps",
            tip="Número de coeficientes del filtro ecualizador.\n"
                "El coste del RLS crece como N², el del LMS como N.")
        v.addWidget(self.taps)
        self.mu = SliderRow(
            "Paso de adaptación", 0.01, 1.00, 0.50, 0.01, "{:.2f}", "",
            tip="Paso del LMS normalizado. μ = 0,5 es el óptimo medido:\n"
                "con μ = 0,15 el LMS falla con entrenamiento corto.")
        v.addWidget(self.mu)
        self.lam = SliderRow(
            "Factor de olvido", 0.900, 0.9999, 0.995, 0.0005, "{:.4f}", "",
            tip="Memoria del RLS. En canal estático no afecta;\n"
                "en el escenario D vale 50× en BER.")
        v.addWidget(self.lam)
        self.train = SliderRow(
            "Entrenamiento", 64, 1024, 512, 64, "{:.0f}", "símbolos")
        v.addWidget(self.train)

        v.addSpacing(3)
        v.addWidget(panel_label("Lazos del receptor"))
        self.cb_timing = checkbox(
            "Recuperación de temporización", True,
            "Lazo de Gardner. Al desactivarlo se muestrea a ciegas y el error\n"
            "de temporización del canal se ve directamente en la constelación.")
        self.cb_cfo = checkbox(
            "Corrección de frecuencia", True,
            "Estimación de Schmidl-Cox sobre el preámbulo Zadoff-Chu.")
        self.cb_pll = checkbox(
            "PLL de fase", True,
            "Lazo dirigido por decisión después del ecualizador.")
        self.cb_mf = checkbox(
            "Filtro adaptado", True,
            "Al desactivarlo se pierde la maximización de SNR en el instante\n"
            "de decisión: requisito 4.9 de la guía.")
        for cb in (self.cb_timing, self.cb_cfo, self.cb_pll, self.cb_mf):
            v.addWidget(cb)
        root.addWidget(g)
        root.addStretch(1)

        self.setWidget(host)
        self._wire()
        self._sync_enabled()

    # -- cableado ------------------------------------------------------------
    def _wire(self) -> None:
        sliders = (self.ebn0, self.beta, self.cfo, self.phase, self.timing,
                   self.fd, self.taps, self.mu, self.lam, self.train)
        for s in sliders:
            s.moved.connect(lambda _v: self.changed.emit())
            s.settled.connect(lambda _v: self.settled.emit())

        self.scenario.changed.connect(self._on_scenario)
        for c in (self.mod, self.profile, self.eq):
            c.changed.connect(lambda _k: (self._sync_enabled(), self.settled.emit()))

        self.seed.moved.connect(lambda _v: (self._show_h(), self.changed.emit()))
        self.seed.settled.connect(lambda _v: (self._show_h(), self.settled.emit()))
        self.next_ch.clicked.connect(self._next_channel)
        self.h_edit.editingFinished.connect(self._on_h_edited)
        self.h_edit.textEdited.connect(lambda _t: self._mark_h(None))
        for cb in (self.cb_timing, self.cb_cfo, self.cb_pll, self.cb_mf):
            cb.toggled.connect(lambda _b: self.settled.emit())

    def _next_channel(self) -> None:
        self.seed.set_value((int(self.seed.value()) + 1) % 1000)
        self._show_h()
        self.settled.emit()

    def _on_h_edited(self) -> None:
        """Valida h con el mismo analizador que usa la simulación.

        Un h que no se entiende no se aplica: se marca el campo y se sigue
        simulando con el último h válido, que es el que muestra la nota.
        """
        from comm2.channel import get_profile
        txt = self.h_edit.text().strip()
        try:
            get_profile(txt)
        except ValueError as e:
            self._mark_h(str(e).split(":")[0])
            return
        self._mark_h(None)
        if txt != self._h_ok:
            self._h_ok = txt
            self._show_h()
            self.settled.emit()

    def _mark_h(self, err: Optional[str]) -> None:
        self.h_edit.setProperty("invalid", bool(err))
        self.h_edit.style().unpolish(self.h_edit)
        self.h_edit.style().polish(self.h_edit)
        if err:
            self.h_note.setText(f"no se entiende: {err}.\nSigue h = [{self._h_fmt()}]")
            self.h_note.setStyleSheet(f"color: {T.CRITICAL}")

    def _h_fmt(self) -> str:
        from comm2.channel import format_taps, parse_taps, random_taps
        if self.profile.value() == "aleatorio":
            return format_taps(random_taps(seed=int(self.seed.value())))
        return format_taps(parse_taps(self._h_ok))

    def _show_h(self) -> None:
        """El h en uso, siempre a la vista: es lo que hace reproducible el canal."""
        k = self.profile.value()
        if k in ("aleatorio", "manual"):
            self.h_note.setText(f"h = [{self._h_fmt()}]")
            self.h_note.setStyleSheet(
                f"color: {T.INK_DIM if self.profile.isEnabled() else T.INK_GHOST}")
        else:
            self.h_note.setText("")

    def set_view(self, key: str) -> None:
        """La vista activa decide qué controles tienen efecto."""
        self._view = key
        self._sync_enabled()

    def _on_scenario(self, key: str) -> None:
        self.scen_note.setText(SCENARIO_NOTE[key])
        self._sync_enabled()
        self.settled.emit()

    def _sync_enabled(self) -> None:
        s = self.scenario.current
        eq = self.eq.value()
        # La vista «ISI y ecualizador» fija el escenario B sin sincronismo de
        # portadora: escenario, offsets y esos dos lazos no tienen efecto allí.
        isi = getattr(self, "_view", "bench") == "isi"
        self.scenario.setEnabled(not isi)
        self.scen_note.setText(
            "La vista «ISI y ecualizador» usa siempre el escenario B, sin "
            "offsets de portadora: solo canal h y ruido." if isi else SCENARIO_NOTE[s])
        self.profile.setEnabled(isi or s != "A")
        for w in (self.cfo, self.phase, self.timing):
            w.setEnabled(not isi and s in ("C", "D"))
        self.fd.setEnabled(not isi and s == "D")
        self.cb_cfo.setEnabled(not isi)
        self.cb_pll.setEnabled(not isi)
        k = self.profile.value()
        on = self.profile.isEnabled()
        self.seed.setVisible(k == "aleatorio")
        self.next_ch.setVisible(k == "aleatorio")
        self.seed.setEnabled(on)
        self.next_ch.setEnabled(on)
        for w in (self.h_name, self.h_edit):
            w.setVisible(k == "manual")
            w.setEnabled(on)
        self.h_note.setVisible(k in ("aleatorio", "manual"))
        self._show_h()
        adaptive = eq in ("lms", "rls", "cma")
        self.taps.setEnabled(eq != "none")
        self.mu.setEnabled(eq in ("lms", "cma"))
        self.lam.setEnabled(eq == "rls")
        self.train.setEnabled(eq != "none")

    # -- lectura -------------------------------------------------------------
    def _profile_spec(self) -> str:
        """Lo que entiende `comm2.channel.get_profile`: nombre, semilla o h."""
        k = self.profile.value()
        if k == "aleatorio":
            return f"aleatorio:{int(self.seed.value())}"
        if k == "manual":
            return self._h_ok
        return k

    def request(self, compare: bool = True) -> Request:
        return Request(
            scenario=self.scenario.current,
            mod=self.mod.value(),
            ebn0_db=self.ebn0.value(),
            profile=self._profile_spec(),
            beta=self.beta.value(),
            cfo_frac_rs=self.cfo.value(),
            phase_deg=self.phase.value(),
            timing_frac=self.timing.value(),
            fd_frac_rs=self.fd.value(),
            eq_kind=self.eq.value(),
            n_taps=int(self.taps.value()),
            mu=self.mu.value(),
            lam=self.lam.value(),
            n_train=int(self.train.value()),
            timing_recovery=self.cb_timing.isChecked(),
            cfo_correction=self.cb_cfo.isChecked(),
            phase_pll=self.cb_pll.isChecked(),
            matched_filter=self.cb_mf.isChecked(),
            compare=compare,
        )

"""Validacion cruzada con GNU Radio (Seccion 11 de la guia).

La guia pide reproducir un experimento representativo en la segunda herramienta
y analizar si ambos resultados son consistentes. Aqui eso ocurre **en vivo**:
la aplicacion compila el flowgraph con `grcc`, lo ejecuta con el interprete de
radioconda, lee el fichero `complex64` resultante y superpone su espectro sobre
el del simulador de Python.

Los coeficientes del canal se inyectan desde Python en el flowgraph, en lugar de
teclearse a mano en GNU Radio Companion. Es la unica forma de que la comparacion
signifique algo: si el canal no fuera identico bit a bit, cualquier diferencia
entre las dos herramientas seria inatribuible.

Reparto entre los dos flowgraphs:

- `tx_qpsk_canal.grc` no tiene sumideros graficos, asi que se ejecuta sin
  interfaz y da la comparacion cuantitativa.
- `rx_qpsk_desde_python.grc` lleva los sumideros Qt de GNU Radio (constelacion,
  PSD, ojo en vivo); ese se abre en GNU Radio Companion, que es donde tiene
  sentido verlo.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QPushButton,
                               QVBoxLayout, QWidget)

from comm2 import SystemParams, metrics

from . import theme as T
from .displays import _label, _plot
from .widgets import (HRule, Panel, Readout, SliderRow, panel_label,
                      text_label)


def _fmt_db(x: float) -> str:
    if x is None or not np.isfinite(x):
        return "sin ruido" if x == float("inf") else "--"
    return f"{x:.1f} dB"


PROJECT = Path(__file__).resolve().parent.parent
GRC_DIR = PROJECT / "grc"
IO_DIR = GRC_DIR / "io"
DRIVER = Path(__file__).parent / "grc_driver.py"


# ---------------------------------------------------------------------------
# Deteccion de la instalacion
# ---------------------------------------------------------------------------

@dataclass
class GrcInstall:
    python: Optional[Path] = None
    grcc: Optional[Path] = None
    companion: Optional[Path] = None
    version: str = ""
    problem: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.python and self.grcc)


def _candidates() -> list[Path]:
    home = Path.home()
    out = [home / "radioconda", Path("C:/radioconda"),
           Path("C:/Program Files/GNURadio-3.10"),
           home / "miniconda3" / "envs" / "gnuradio"]
    env = os.environ.get("GNURADIO_HOME")
    if env:
        out.insert(0, Path(env))
    return out


def detect() -> GrcInstall:
    """Localiza radioconda sin importar nada: solo rutas y una consulta."""
    for root in _candidates():
        py = root / "python.exe"
        grcc = root / "Scripts" / "grcc.exe"
        if not py.exists():
            py = root / "bin" / "python"
        if not grcc.exists():
            grcc = root / "bin" / "grcc"
        if py.exists() and grcc.exists():
            inst = GrcInstall(python=py, grcc=grcc)
            comp = root / "Scripts" / "gnuradio-companion.exe"
            if not comp.exists():
                comp = root / "bin" / "gnuradio-companion"
            inst.companion = comp if comp.exists() else None
            try:
                r = subprocess.run(
                    [str(py), "-c",
                     "from gnuradio import gr; print(gr.version())"],
                    capture_output=True, text=True, timeout=60,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                inst.version = (r.stdout or "").strip() or "?"
                if r.returncode != 0:
                    inst.problem = (r.stderr or "").strip()[:200]
            except Exception as exc:  # noqa: BLE001
                inst.problem = f"{type(exc).__name__}: {exc}"
            return inst
    return GrcInstall(problem="No se encontró ninguna instalación de GNU Radio.")


def companion_command(inst: GrcInstall, grc_file: Path) -> list[str]:
    """Orden para abrir GNU Radio Companion como lo hace el menú Inicio.

    `Scripts/gnuradio-companion.exe` lanzado a pelo MUERE al arrancar: sin el
    entorno de conda activado, GTK no encuentra Pango y `gi/overrides` lanza un
    AssertionError (medido). El acceso directo oficial de radioconda no lanza el
    .exe: ejecuta `python cwp.py <prefijo> gnuradio-companion.exe`, y `cwp.py`
    es quien activa el entorno. Aquí se hace lo mismo, con `pythonw` para que
    no aparezca una consola y `--no-console` para la del propio lanzador.
    """
    root = inst.python.parent
    cwp = root / "cwp.py"
    if cwp.exists():
        pyw = root / "pythonw.exe"
        launcher = pyw if pyw.exists() else inst.python
        return [str(launcher), str(cwp), "--no-console", str(root),
                str(inst.companion), str(grc_file)]
    return [str(inst.companion), str(grc_file)]


def _clean_env() -> dict:
    """Entorno sin rastro del .venv del simulador.

    La aplicación corre dentro de .venv; si Companion heredara VIRTUAL_ENV,
    PYTHONHOME o el Scripts del .venv en el PATH, mezclaría intérpretes, que es
    justo lo que la separación de entornos del proyecto prohíbe.
    """
    env = dict(os.environ)
    for k in ("VIRTUAL_ENV", "PYTHONHOME", "PYTHONPATH", "PYTHONEXECUTABLE",
              "__PYVENV_LAUNCHER__"):
        env.pop(k, None)
    venv = str(Path(sys.prefix).resolve()).lower()
    env["PATH"] = os.pathsep.join(
        d for d in env.get("PATH", "").split(os.pathsep)
        if d and not str(Path(d)).lower().startswith(venv))
    return env


# ---------------------------------------------------------------------------
# Trabajador
# ---------------------------------------------------------------------------

class _GrcWorker(QObject):
    log = Signal(str)
    done = Signal(object)
    failed = Signal(str)

    @Slot(object)
    def run(self, job: tuple) -> None:
        inst, noise, ebn0 = job
        tmp = Path(tempfile.mkdtemp(prefix="comm2-grc-"))
        try:
            self.log.emit("Compilando tx_qpsk_canal.grc con grcc…")
            r = subprocess.run(
                [str(inst.grcc), "-o", str(tmp), str(GRC_DIR / "tx_qpsk_canal.grc")],
                capture_output=True, text=True, timeout=300,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if r.returncode != 0 or not (tmp / "tx_qpsk_canal.py").exists():
                self.failed.emit("grcc falló:\n" + (r.stderr or r.stdout)[:500])
                return
            self.log.emit("Compilado. Ejecutando el flowgraph…")

            taps = IO_DIR / "ch_taps_para_grc.txt"
            cmd = [str(inst.python), str(DRIVER), str(tmp), "tx_qpsk_canal",
                   str(GRC_DIR), "--noise", f"{noise:.6f}",
                   "--outputs", "io/grc_tx_signal.cf32;io/grc_rx_signal.cf32"]
            if taps.exists():
                cmd += ["--taps", str(taps)]
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

            payload = None
            for line in (r.stdout or "").splitlines():
                if line.startswith("GRCJSON "):
                    payload = json.loads(line[8:])
            if payload is None:
                self.failed.emit("El flowgraph no devolvió resultado:\n"
                                 + ((r.stderr or r.stdout) or "sin salida")[:500])
                return
            if not payload.get("ok"):
                self.failed.emit(payload.get("error", "error desconocido"))
                return

            self.log.emit("Ejecutado. Midiendo y comparando…")
            self.done.emit(self._compare(payload, noise))
        except subprocess.TimeoutExpired:
            self.failed.emit("El flowgraph excedió el tiempo máximo.")
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # -- medida -------------------------------------------------------------
    @staticmethod
    def _snr_simbolo(rx, p) -> float:
        """SNR estimada a TASA DE SÍMBOLO, no sobre la señal sobremuestreada.

        El estimador M2M4 supone módulo constante. La forma de onda
        sobremuestreada y conformada con RRC no lo es en absoluto, y aplicarlo
        ahí da un número sistemáticamente bajo que no significa nada: medido
        sobre la misma captura, 2,98 dB sobremuestreada frente a 5,07 dB a tasa
        de símbolo. Tras el filtro adaptado y el diezmado, QPSK sí es de módulo
        constante y el estimador recupera su validez.

        Lo que queda dentro del «ruido» estimado incluye la ISI del canal
        multitrayecto, que para este estimador es indistinguible del ruido: es
        una cota inferior de la SNR real, y se rotula como tal.
        """
        if rx is None or rx.size < 8192:
            return float("nan")
        try:
            from comm2.pulse import matched_filter, rrc_filter
            h = rrc_filter(p.beta, p.span, p.sps)
            mf = matched_filter(rx.astype(complex), h)
            off = metrics.best_sampling_phase(mf, p.sps)
            sym = mf[off::p.sps]
            # Recorta los transitorios de entrada y salida del filtro.
            lo, hi = int(0.10 * sym.size), int(0.90 * sym.size)
            sym = sym[lo:hi]
            if sym.size < 512:
                return float("nan")
            sym = sym / (np.sqrt(np.mean(np.abs(sym) ** 2)) + 1e-15)
            return float(metrics.estimate_snr_m2m4(sym))
        except Exception:
            return float("nan")

    def _compare(self, payload: dict, noise_v: float) -> dict:
        p = SystemParams()
        out: dict = {"elapsed": payload["elapsed"],
                     "gr_version": payload.get("gr_version", "?"), "rows": [],
                     "psd": {}}

        def measure(x: np.ndarray, label: str) -> dict:
            n = min(x.size, 120000)
            x = x[:n].astype(complex)
            f, pdb = metrics.psd(x, p.fs, nperseg=1024)
            out["psd"][label] = (f / p.rs, pdb - float(np.max(pdb)))
            pk = float(np.max(np.abs(x) ** 2))
            mean = float(np.mean(np.abs(x) ** 2)) + 1e-18
            return {
                "n": int(x.size),
                "bw": metrics.occupied_bandwidth(x, p.fs) / 1e3,
                "papr": 10 * np.log10(pk / mean),
            }

        # --- GNU Radio ------------------------------------------------------
        gt = payload["files"].get("io/grc_tx_signal.cf32", {})
        gr_tx = np.fromfile(gt["path"], dtype=np.complex64) if gt.get("samples") else np.array([])
        gt_rx = payload["files"].get("io/grc_rx_signal.cf32", {})
        gr_rx = np.fromfile(gt_rx["path"], dtype=np.complex64) if gt_rx.get("samples") else np.array([])

        # --- Python ---------------------------------------------------------
        from comm2.link import transmit
        py_tx, _frm, _h = transmit(p)

        m_py = measure(py_tx, "py")
        m_gr = measure(gr_tx, "grc") if gr_tx.size else None

        snr_gr = self._snr_simbolo(gr_rx, p)

        nominal = p.bw / 1e3
        out["rows"] = [
            ("Ancho de banda ocupado (99 %)", "kHz",
             m_py["bw"], m_gr["bw"] if m_gr else float("nan"), nominal),
            ("PAPR", "dB", m_py["papr"], m_gr["papr"] if m_gr else float("nan"),
             float("nan")),
        ]
        out["snr_grc"] = snr_gr
        # SNR que produciria el ruido SOLO, a partir de la potencia de senal
        # medida y de la tension pedida. Comprobado empiricamente: el bloque
        # Channel Model usa `noise_voltage` como desviacion tipica del ruido
        # complejo, de modo que su potencia es v^2 (medido: la potencia
        # recibida sube 0,352 al pasar v de 0 a 0,60).
        p_sig = float(np.mean(np.abs(gr_tx) ** 2)) if gr_tx.size else float("nan")
        pn = noise_v ** 2
        out["snr_awgn"] = (10 * np.log10(p_sig / pn)
                           if (pn > 1e-12 and np.isfinite(p_sig)) else float("inf"))
        out["noise_v"] = noise_v
        out["n_grc"] = int(gr_tx.size)
        out["n_py"] = int(py_tx.size)
        out["nominal_bw"] = nominal
        return out


# ---------------------------------------------------------------------------
# Vista
# ---------------------------------------------------------------------------

class GrcView(QWidget):
    _launch = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.inst = detect()
        self._busy = False
        self._proc: Optional[subprocess.Popen] = None
        self._proc_log: Optional[Path] = None
        self._proc_checks = 0
        self._watch = QTimer(self)
        self._watch.setInterval(1000)
        self._watch.timeout.connect(self._check_companion)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        # -- estado de la instalacion -----------------------------------------
        head = Panel("Herramienta secundaria")
        hw = QWidget()
        hv = QVBoxLayout(hw)
        hv.setContentsMargins(15, 13, 15, 14)
        hv.setSpacing(11)

        row = QHBoxLayout()
        row.setSpacing(28)
        self.r_ver = Readout("GNU Radio", "")
        self.r_py = Readout("Intérprete", "")
        self.r_state = Readout("Flowgraphs", "")
        for r in (self.r_ver, self.r_py, self.r_state):
            row.addWidget(r)
        row.addStretch(1)

        self.noise = SliderRow(
            "Ruido del canal", 0.0, 0.60, 0.10, 0.01, "{:.2f}", "V",
            tip="El bloque Channel Model de GNU Radio especifica el ruido como\n"
                "TENSIÓN, no como Eb/N0, y la correspondencia depende de la\n"
                "normalización del Constellation Modulator. En vez de calibrarla\n"
                "a ciegas se fija la tensión y se MIDE la SNR resultante.")
        self.noise.setFixedWidth(196)
        row.addWidget(self.noise, 0, Qt.AlignmentFlag.AlignVCenter)

        self.btn_run = QPushButton("Compilar y ejecutar")
        self.btn_run.setObjectName("Primary")
        self.btn_run.setMinimumWidth(168)
        self.btn_open = QPushButton("Abrir en GNU Radio Companion")
        row.addWidget(self.btn_run, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.btn_open, 0, Qt.AlignmentFlag.AlignVCenter)
        hv.addLayout(row)

        self.status = text_label("", T.f_small(), T.INK_FAINT, wrap=True)
        hv.addWidget(self.status)
        head.set_content(hw)
        root.addWidget(head)

        # -- comparacion -------------------------------------------------------
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        self.p_psd = Panel("Espectro  ·  Python frente a GNU Radio")
        holder = QWidget()
        hh = QVBoxLayout(holder)
        hh.setContentsMargins(6, 4, 6, 6)
        self.plot = _plot()
        self.pi = self.plot.getPlotItem()
        _label(self.pi, "PSD [dB]", "frecuencia [Rs]")
        self.pi.setXRange(-1.6, 1.6, padding=0)
        self.pi.setYRange(-75, 6, padding=0)
        self.c_py = self.pi.plot([], [], pen=pg.mkPen(T.S1, width=1.8))
        self.c_gr = self.pi.plot([], [], pen=pg.mkPen(T.S2, width=1.8))
        leg = self.pi.addLegend(offset=(-10, 10), labelTextColor=T.INK_DIM,
                                labelTextSize="8pt",
                                brush=pg.mkBrush(T.rgba(T.PANEL, 0.88)),
                                pen=pg.mkPen(T.RULE))
        leg.addItem(self.c_py, "Python  ·  comm2")
        leg.addItem(self.c_gr, "GNU Radio  ·  flowgraph")
        hh.addWidget(self.plot)
        self.p_psd.set_content(holder)
        grid.addWidget(self.p_psd, 0, 0)

        self.p_tab = Panel("Consistencia entre herramientas")
        tw = QWidget()
        self.tab = QVBoxLayout(tw)
        self.tab.setContentsMargins(15, 14, 15, 15)
        self.tab.setSpacing(0)
        self.p_tab.set_content(tw)
        grid.addWidget(self.p_tab, 0, 1)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        root.addLayout(grid, 1)

        note = text_label(
            "El flowgraph de transmisor y canal se ejecuta sin interfaz y da la "
            "comparación cuantitativa. El de receptor lleva los sumideros gráficos "
            "de GNU Radio (constelación, PSD y ojo en vivo) y se abre en Companion, "
            "que es donde tiene sentido verlo. Los coeficientes del canal se "
            "inyectan desde Python para que ambas herramientas vean exactamente el "
            "mismo canal.",
            T.f_body(), T.INK_FAINT, wrap=True)
        root.addWidget(note)

        # -- hilo ---------------------------------------------------------------
        self._thread = QThread()
        self._thread.setObjectName("comm2-grc")
        self._worker = _GrcWorker()
        self._worker.moveToThread(self._thread)
        self._launch.connect(self._worker.run)
        self._worker.log.connect(lambda m: self._say(m, T.INK_DIM))
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

        self.btn_run.clicked.connect(self._run)
        self.btn_open.clicked.connect(self._open_companion)
        self._refresh_install()
        self._empty_table()

    # -- estado --------------------------------------------------------------
    def _refresh_install(self) -> None:
        i = self.inst
        if i.ok:
            self.r_ver.set(i.version or "?", T.GOOD)
            self.r_py.set(str(i.python.parent.name), T.INK)
            self.r_py.setToolTip(str(i.python))
            n = sum(1 for f in GRC_DIR.glob("*.grc"))
            self.r_state.set(f"{n} encontrados", T.INK)
            self._say("Instalación detectada. El flowgraph se compilará con grcc "
                      "y se ejecutará con este intérprete, aislado del entorno "
                      "virtual del simulador.", T.INK_FAINT)
        else:
            self.r_ver.set("no detectado", T.CRITICAL)
            self.r_py.set("--", T.INK_GHOST)
            self.r_state.set("--", T.INK_GHOST)
            self.btn_run.setEnabled(False)
            self.btn_open.setEnabled(False)
            self._say(i.problem or "GNU Radio no está disponible en este equipo.",
                      T.SERIOUS)
        self.btn_open.setEnabled(bool(i.companion))

    def _say(self, msg: str, color: str = T.INK_FAINT) -> None:
        self.status.setText(msg)
        self.status.setStyleSheet(f"color: {color}")

    # -- acciones ------------------------------------------------------------
    def _run(self) -> None:
        if self._busy or not self.inst.ok:
            return
        self._busy = True
        self.btn_run.setEnabled(False)
        self.btn_run.setText("Ejecutando...")
        self._say("Compilando...", T.INK_DIM)
        self._launch.emit((self.inst, float(self.noise.value()), 0.0))

    def _open_companion(self) -> None:
        """Abre Companion desacoplado y vigila los primeros segundos.

        Desacoplado: cerrar el banco de pruebas no debe cerrar Companion ni
        perder lo que se esté editando allí. Vigilado: si muere al arrancar, se
        dice por qué, en vez de que el botón parezca no hacer nada.
        """
        if not self.inst.companion:
            return
        if self._proc is not None and self._proc.poll() is None:
            self._say("GNU Radio Companion ya está abierto: búscalo en la barra "
                      "de tareas.", T.INK_DIM)
            return
        grc = GRC_DIR / "rx_qpsk_desde_python.grc"
        self._proc_log = Path(tempfile.gettempdir()) / "comm2_companion.log"
        flags = 0
        for name in ("DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP"):
            flags |= getattr(subprocess, name, 0)
        try:
            with open(self._proc_log, "w", encoding="utf-8") as log:
                self._proc = subprocess.Popen(
                    companion_command(self.inst, grc), cwd=str(GRC_DIR),
                    env=_clean_env(), stdout=log, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL, creationflags=flags)
        except OSError as exc:
            self._say(f"No se pudo lanzar GNU Radio Companion: {exc}", T.SERIOUS)
            return
        falta = not (IO_DIR / "py_tx_signal.cf32").exists()
        self._say("Abriendo GNU Radio Companion con el flowgraph del receptor "
                  "(activando el entorno de radioconda: tarda unos segundos)."
                  + ("  Ojo: falta grc/io/py_tx_signal.cf32; genéralo con "
                     "«Compilar y ejecutar» o con exp6_validacion_grc.py --export "
                     "antes de ejecutar el flowgraph." if falta else ""),
                  T.SERIOUS if falta else T.INK_DIM)
        self.btn_open.setEnabled(False)
        self._proc_checks = 0
        self._watch.start()

    def _check_companion(self) -> None:
        self._proc_checks += 1
        code = self._proc.poll() if self._proc is not None else 0
        if code is None and self._proc_checks < 15:
            return                       # sigue arrancando o ya está abierto
        self._watch.stop()
        self.btn_open.setEnabled(True)
        if code is None:
            self._say("GNU Radio Companion está abierto con "
                      "rx_qpsk_desde_python.grc. Sus sumideros gráficos se "
                      "muestran en ventanas propias de GNU Radio.", T.GOOD)
        elif code != 0:
            tail = ""
            try:
                lines = [ln.strip() for ln in self._proc_log.read_text(
                    encoding="utf-8", errors="replace").splitlines() if ln.strip()]
                tail = lines[-1][:160] if lines else ""
            except OSError:
                pass
            self._say(f"GNU Radio Companion se cerró al arrancar (código {code})"
                      f"{': ' + tail if tail else ''}. Registro completo en "
                      f"{self._proc_log}.", T.SERIOUS)

    @Slot(object)
    def _on_done(self, res: dict) -> None:
        self._busy = False
        self.btn_run.setEnabled(True)
        self.btn_run.setText("Compilar y ejecutar")

        if "py" in res["psd"]:
            f, y = res["psd"]["py"]
            self.c_py.setData(f, y)
        if "grc" in res["psd"]:
            f, y = res["psd"]["grc"]
            self.c_gr.setData(f, y)

        self._fill_table(res)
        self._say(f"Flowgraph ejecutado en {res['elapsed']:.2f} s con GNU Radio "
                  f"{res['gr_version']}.  {res['n_grc']:,} muestras leídas del "
                  f"fichero complex64.".replace(",", " "), T.GOOD)

    @Slot(str)
    def _on_failed(self, msg: str) -> None:
        self._busy = False
        self.btn_run.setEnabled(True)
        self.btn_run.setText("Compilar y ejecutar")
        self._say(msg, T.CRITICAL)

    # -- tabla ---------------------------------------------------------------
    def _clear_table(self) -> None:
        while self.tab.count():
            it = self.tab.takeAt(0)
            w = it.widget()
            if w is not None:
                # `deleteLater` es asincrono: el widget sigue pintandose hasta
                # que el bucle de eventos procese el borrado, y el texto de
                # «sin ejecutar» se veia superpuesto sobre la tabla ya llena.
                # Desvincularlo del padre lo retira de la pantalla al instante.
                w.setParent(None)
                w.deleteLater()

    def _empty_table(self) -> None:
        self._clear_table()
        self.tab.addWidget(text_label(
            "Sin ejecutar. Pulsa «Compilar y ejecutar» para generar la forma de "
            "onda en GNU Radio y contrastarla con la del simulador.",
            T.f_body(), T.INK_FAINT, wrap=True))
        self.tab.addStretch(1)

    def _fill_table(self, res: dict) -> None:
        self._clear_table()
        hdr = QHBoxLayout()
        for txt, w, al in (("Magnitud", 3, Qt.AlignmentFlag.AlignLeft),
                           ("Python", 2, Qt.AlignmentFlag.AlignRight),
                           ("GNU Radio", 2, Qt.AlignmentFlag.AlignRight),
                           ("Dif.", 2, Qt.AlignmentFlag.AlignRight)):
            lb = panel_label(txt)
            lb.setAlignment(al | Qt.AlignmentFlag.AlignVCenter)
            hdr.addWidget(lb, w)
        box = QWidget()
        box.setLayout(hdr)
        self.tab.addWidget(box)
        self.tab.addSpacing(6)
        self.tab.addWidget(HRule(T.RULE_STRONG))

        for name, unit, py, gr, nominal in res["rows"]:
            self.tab.addSpacing(9)
            row = QHBoxLayout()
            row.setSpacing(0)
            lb = text_label(f"{name}  [{unit}]", T.f_body(), T.INK_DIM)
            row.addWidget(lb, 3)
            for v in (py, gr):
                t = text_label("--" if not np.isfinite(v) else f"{v:.2f}",
                               T.font(11, 500, mono=True), T.INK)
                t.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                row.addWidget(t, 2)
            if np.isfinite(py) and np.isfinite(gr) and abs(py) > 1e-9:
                d = 100 * (gr - py) / abs(py)
                col = T.GOOD if abs(d) < 5 else (T.WARNING if abs(d) < 15 else T.SERIOUS)
                txt = f"{d:+.1f} %"
            else:
                col, txt = T.INK_GHOST, "--"
            t = text_label(txt, T.font(11, 500, mono=True), col)
            t.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(t, 2)
            w = QWidget()
            w.setLayout(row)
            self.tab.addWidget(w)
            self.tab.addSpacing(6)
            self.tab.addWidget(HRule())

        self.tab.addSpacing(12)
        snr = res.get("snr_grc", float("nan"))
        self.tab.addWidget(text_label(
            f"Con {res.get('noise_v', 0):.2f} V de ruido, la SNR que "
            f"produciría el AWGN solo es "
            f"{_fmt_db(res.get('snr_awgn', float('nan')))}, y la medida sobre "
            f"la señal recibida es {_fmt_db(snr)}.\n\n"
            "La diferencia entre ambas NO es un error: el estimador M2M4 no "
            "distingue la ISI del multitrayecto del ruido, y en este canal la "
            "ISI domina. Por eso la medida apenas se mueve al bajar el ruido: "
            "lo que limita el enlace aquí es la distorsión, no la potencia.",
            T.f_small(), T.INK_FAINT, wrap=True))
        self.tab.addSpacing(10)
        self.tab.addWidget(text_label(
            f"Ancho de banda nominal del RRC: B = Rs(1+β) = "
            f"{res['nominal_bw']:.1f} kHz. Si ambas herramientas lo reproducen, "
            "la conformación de pulso está implementada igual en las dos.",
            T.f_small(), T.INK_FAINT, wrap=True))
        self.tab.addStretch(1)

    def stop(self) -> None:
        self._thread.quit()
        self._thread.wait(3000)

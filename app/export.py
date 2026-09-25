"""Modo sin interfaz: guarda las imágenes sin abrir ninguna ventana.

Responde a la pregunta «¿puede funcionar sin necesidad de mostrar, que se
guarden las imágenes, como si no quisiera usar la interfaz?». Sí: es el mismo
simulador y los mismos instrumentos, renderizados fuera de pantalla con la
plataforma `offscreen` de Qt y escritos a disco.

    python -m app --export
    python -m app --export salida/ --escenario B --ebn0 14 --eq rls
    python -m app --export --tema oscuro

Genera, para la configuración pedida:

    cadena.png                 el camino de la señal con su perfil de apertura
    constelacion_<etapa>.png   los ocho puntos de derivación
    ojo_<etapa>.png            los tres puntos donde el ojo es medible
    espectro.png               PSD del transmisor y tras el canal
    convergencia.png           curvas de aprendizaje LMS y RLS
    medidas.csv                BER, SER, EVM, MSE, convergencia y coste

No es un sustituto de `experiments/run_all.py`, que produce las figuras del
informe en matplotlib: esto produce las del instrumento, que son las que sirven
para la presentación.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QEventLoop, QSize, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from . import theme as T
from .engine import STAGES, SYMBOL, Request, SimResult, simulate

PANEL_SIZE = QSize(760, 620)
WIDE_SIZE = QSize(1180, 300)


def _grab(w: QWidget, size: QSize, path: Path, scale: float = 2.0) -> None:
    """Renderiza un widget a fichero sin mostrarlo.

    El factor de escala da una imagen al doble de resolución, que es lo que hace
    falta para proyectar o para pegarla en un informe sin que se vea pixelada.
    """
    w.resize(size)
    w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    w.show()
    app = QApplication.instance()
    for _ in range(4):                       # deja asentar maquetado y ejes
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 40)

    pm = QPixmap(int(size.width() * scale), int(size.height() * scale))
    pm.setDevicePixelRatio(scale)
    pm.fill(Qt.GlobalColor.transparent)
    w.render(pm)
    pm.save(str(path))
    w.hide()


def _panel(title: str, inner: QWidget) -> QWidget:
    from .widgets import Panel
    p = Panel(title)
    p.set_content(inner)
    return p


def run(req: Request, out_dir: Path, verbose: bool = True) -> SimResult:
    from .displays import Constellation, Convergence, Eye, Spectrum
    from .signalpath import SignalPath

    out_dir.mkdir(parents=True, exist_ok=True)
    res = simulate(req)

    def say(msg: str) -> None:
        if verbose:
            print(msg)

    say(f"Escenario {req.scenario} · {req.mod.upper()} · Eb/N0 {req.ebn0_db:.1f} dB "
        f"· ecualizador {req.eq_kind.upper()}")
    say(f"  BER {res.stats['ber']:.3e}   EVM {res.stats['evm_pct']:.2f} %   "
        f"enganche: {'sí' if res.locked else 'no'}   ({res.elapsed:.2f} s)")

    # --- el camino de la señal ---------------------------------------------
    path_w = SignalPath()
    path_w.set_openings({k: t.opening for k, t in res.taps.items()})
    path_w.set_current("pll")
    _grab(path_w, QSize(WIDE_SIZE.width(), path_w.height()), out_dir / "cadena.png")
    say("  cadena.png")

    # --- constelación en los ocho puntos ------------------------------------
    for st in STAGES:
        tap = res.taps[st.key]
        if tap.pts is None:
            continue
        c = Constellation()
        c.set_reference(res.ideal)
        c.autoscale(tap.pts)
        c.show_tap(tap.pts, tap.kind, animate=False)
        nota = (f"EVM {tap.evm:.1f} %" if st.kind == SYMBOL and st.key != "tx"
                else ("referencia ideal" if st.key == "tx"
                      else "muestreada en el instante óptimo"))
        p = _panel(f"Constelación  ·  {st.title}", c)
        p.set_note(nota)
        _grab(p, PANEL_SIZE, out_dir / f"constelacion_{st.key}.png")
    say(f"  constelacion_*.png  ({sum(1 for s in STAGES)} etapas)")

    # --- ojo, solo donde es medible -----------------------------------------
    n_eye = 0
    for st in STAGES:
        if st.kind == SYMBOL:
            continue                          # ya está a tasa de símbolo
        tap = res.taps[st.key]
        e = Eye()
        e.show_wave(tap.wave, res.sps, tap.opening)
        p = _panel(f"Diagrama de ojo  ·  {st.title}", e)
        p.set_note(f"apertura {tap.opening:.3f}")
        _grab(p, PANEL_SIZE, out_dir / f"ojo_{st.key}.png")
        n_eye += 1
    say(f"  ojo_*.png  ({n_eye} puntos medibles)")

    # --- espectro y convergencia --------------------------------------------
    sp = Spectrum()
    sp.show(res.psd, req.beta)
    p = _panel("Densidad espectral", sp)
    p.set_note(f"B = {1.0 + req.beta:.2f} Rs")
    _grab(p, PANEL_SIZE, out_dir / "espectro.png")
    say("  espectro.png")

    cv = Convergence()
    cv.show(res)
    p = _panel("Convergencia del ecualizador", cv)
    p.set_note(f"método {req.eq_kind.upper()}")
    _grab(p, PANEL_SIZE, out_dir / "convergencia.png")
    say("  convergencia.png")

    # --- las medidas, para que las figuras no queden sin su tabla -----------
    csv_path = out_dir / "medidas.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["magnitud", "valor", "unidad"])
        s = res.stats
        filas = [
            ("escenario", req.scenario, ""),
            ("modulacion", req.mod.upper(), ""),
            ("ebn0", f"{req.ebn0_db:.2f}", "dB"),
            ("perfil_multitrayecto", req.profile, ""),
            ("ecualizador", req.eq_kind.upper(), ""),
            ("taps", req.n_taps, ""),
            ("ber", f"{s['ber']:.6e}", ""),
            ("ber_teorica_awgn", f"{res.theory_ber:.6e}", ""),
            ("ber_bits", s.get("ber_bits", 0), "bits"),
            ("ser", f"{s['ser']:.6e}", ""),
            ("evm", f"{s['evm_pct']:.3f}", "%"),
            ("mse_residual", f"{s.get('eq_mse_db', float('nan')):.3f}", "dB"),
            ("convergencia", res.eq_conv, "simbolos"),
            ("coste", res.eq_flops, "mult reales/simbolo"),
            ("eficiencia_espectral", f"{s.get('eta_bps_hz', 0):.4f}", "b/s/Hz"),
            ("enganche", "si" if res.locked else "no", ""),
        ]
        filas += [(f"apertura_ojo_{st.key}", f"{res.taps[st.key].opening:.4f}", "")
                  for st in STAGES]
        wr.writerows(filas)
    say("  medidas.csv")
    say(f"\nEscrito en {out_dir.resolve()}")
    return res

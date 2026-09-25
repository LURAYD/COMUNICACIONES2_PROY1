"""Punto de entrada del banco de pruebas.

    Banco de pruebas.bat        doble clic
    python -m app               abre la ventana
    python -m app --tema oscuro instrumento de fósforo, para portátil
    python -m app --export      NO abre nada: guarda las imágenes y sale
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))
SRC = PROJECT / "src"
if SRC.exists() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _perfil(texto: str) -> str:
    """Valida el perfil al leer la línea de órdenes: un nombre o un vector h."""
    from comm2.channel import get_profile
    try:
        get_profile(texto)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None
    return texto


def parse(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="python -m app",
        description="Banco de pruebas del receptor digital adaptativo "
                    "(Proyecto 1, Comunicaciones II 2026).")
    ap.add_argument("--export", nargs="?", const="resultados_app", default=None,
                    metavar="CARPETA",
                    help="no abre la interfaz: corre la simulación, guarda las "
                         "imágenes y las medidas en CARPETA, y sale.")
    ap.add_argument("--tema", choices=["claro", "oscuro"], default="claro",
                    help="claro (de serie) u oscuro.")
    ap.add_argument("--escenario", choices=["A", "B", "C", "D"], default="C")
    ap.add_argument("--mod", default="qpsk",
                    choices=["qpsk", "8psk", "16qam", "64qam"])
    ap.add_argument("--ebn0", type=float, default=12.0, metavar="dB")
    ap.add_argument("--perfil", default="moderate", type=_perfil,
                    help="flat, mild, moderate, severe o una respuesta al "
                         "impulso espaciada a T, p. ej. \"0,0.2,1,0,0.8\".")
    ap.add_argument("--eq", default="lms",
                    choices=["none", "lms", "rls", "zf", "mmse", "cma"])
    ap.add_argument("--taps", type=int, default=21)
    ap.add_argument("--simbolos", type=int, default=4000,
                    help="símbolos de carga útil por corrida.")
    return ap.parse_args(argv)


def _install_error_dialog() -> None:
    """Un fallo no puede terminar en silencio.

    La aplicación arranca con `pythonw`, que no tiene consola: sin esto, un
    error dejaría la ventana cerrada y ningún mensaje en ninguna parte, que es
    la peor forma posible de fallar delante de un tribunal.
    """
    import traceback

    from PySide6.QtWidgets import QMessageBox

    def hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            return
        detail = "".join(traceback.format_exception(exc_type, exc, tb))
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle("Error en el banco de pruebas")
        box.setText(f"{exc_type.__name__}: {exc}")
        box.setInformativeText("El detalle completo está abajo.")
        box.setDetailedText(detail)
        box.exec()

    sys.excepthook = hook


def _style(app, T) -> None:
    from PySide6.QtGui import QColor, QPalette

    T.load_fonts()
    app.setFont(T.f_body())
    app.setStyleSheet(T.stylesheet())

    # La paleta base también se tiñe: si no, lo que Qt pinta por su cuenta
    # (desplegables, marcos nativos) aparece en gris del sistema.
    pal = app.palette()
    pal.setColor(QPalette.ColorRole.Window, QColor(T.GROUND))
    pal.setColor(QPalette.ColorRole.Base, QColor(T.PANEL))
    pal.setColor(QPalette.ColorRole.Text, QColor(T.INK))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(T.INK))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(T.SIGNAL))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(pal)


def main(argv: list[str] | None = None) -> int:
    args = parse(sys.argv[1:] if argv is None else argv)

    # La consola de Windows viene en cp1252 y se come los acentos y el punto
    # medio de los mensajes de progreso.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    # Sin interfaz: Qt necesita saberlo ANTES de crear la aplicación, para no
    # pedirle una pantalla al sistema que aquí no hace falta.
    if args.export is not None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from app import theme as T
    T.set_mode(args.tema)

    app = QApplication(sys.argv[:1])
    app.setApplicationName("Receptor digital adaptativo")
    app.setOrganizationName("Comunicaciones II 2026")
    _style(app, T)

    from app.engine import Request
    req = Request(scenario=args.escenario, mod=args.mod, ebn0_db=args.ebn0,
                  profile=args.perfil, eq_kind=args.eq, n_taps=args.taps,
                  n_payload=args.simbolos, compare=True)

    if args.export is not None:
        from app.export import run as export_run
        export_run(req, Path(args.export))
        return 0

    _install_error_dialog()
    from app.icon import load as load_icon
    app.setWindowIcon(load_icon())

    from app.window import MainWindow
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

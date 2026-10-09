"""Ejecuta el flowgraph de validación sin ventanas. Lo lanza validar_gnuradio.py.

Se ejecuta con el Python de radioconda, NO con el del proyecto: los bindings de
GNU Radio están compilados contra ese intérprete y `import gnuradio` desde
.venv no puede funcionar. Solo depende de gnuradio, numpy y PyQt5.

El flowgraph es de tipo qt_gui (para verlo en Companion), así que sus
sumideros Qt necesitan una QApplication; con QT_QPA_PLATFORM=offscreen existe
pero no pinta nada. A diferencia del main() que genera GRC, aquí se espera a
que se acaben los ficheros (`tb.wait()`) en vez de a que se cierre la ventana.

Uso:
    <radioconda>/python.exe ejecutar_flowgraph.py <dir_generado> <modulo> <parametros.txt> [ritmo]

Escribe en la salida estándar una línea «GRCJSON {…}» con el resultado.
"""

import json
import os
import sys
import time


def main() -> int:
    gen_dir, modulo, parametros = sys.argv[1], sys.argv[2], sys.argv[3]
    ritmo = float(sys.argv[4]) if len(sys.argv) > 4 else 1e6
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, gen_dir)

    from PyQt5 import Qt
    from gnuradio import gr

    app = Qt.QApplication(sys.argv[:1])  # noqa: F841 - la necesitan los sumideros Qt
    cls = getattr(__import__(modulo), modulo)
    tb = cls(parametros=parametros, ritmo=ritmo)
    t0 = time.time()
    tb.start()
    tb.wait()
    tb.stop()
    print("GRCJSON " + json.dumps({"ok": True, "segundos": time.time() - t0,
                                   "version": gr.version()}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - el error viaja al guion que lo lanzó
        print("GRCJSON " + json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        sys.exit(1)

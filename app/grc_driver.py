"""Guion ejecutado por el interprete de radioconda, NO por el entorno de la app.

Los bindings de Python de GNU Radio estan compilados contra el interprete del
sistema, no contra un entorno virtual: `import gnuradio` desde `.venv` no puede
funcionar. Por eso este fichero se ejecuta como subproceso con el Python de
radioconda y solo depende de `gnuradio` y `numpy`. El resultado vuelve por la
salida estandar como una linea JSON.

Uso:
    <radioconda>/python.exe grc_driver.py <dir_generado> <modulo> <cwd> [opciones]
"""

import argparse
import json
import os
import sys
import time


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("gen_dir")        # donde grcc dejo el .py
    ap.add_argument("module")         # nombre del modulo sin .py
    ap.add_argument("work_dir")       # cwd: los File Sink usan rutas relativas
    ap.add_argument("--taps", default="")
    ap.add_argument("--noise", type=float, default=None)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--outputs", default="")   # rutas a medir, separadas por ;
    a = ap.parse_args()

    sys.path.insert(0, a.gen_dir)
    os.makedirs(os.path.join(a.work_dir, "io"), exist_ok=True)
    os.chdir(a.work_dir)

    import numpy as np

    mod = __import__(a.module)
    cls = getattr(mod, a.module)
    tb = cls()

    # Los coeficientes del canal se inyectan desde Python para que ambas
    # herramientas vean EXACTAMENTE el mismo canal: si se tecleara a mano en el
    # flowgraph, cualquier diferencia de BER seria inatribuible.
    if a.taps and hasattr(tb, "set_ch_taps"):
        txt = open(a.taps, "r", encoding="utf-8").read()
        lit = txt[txt.index("["): txt.rindex("]") + 1]
        tb.set_ch_taps([complex(v) for v in eval(lit)])
    if a.noise is not None and hasattr(tb, "set_noise_volt"):
        tb.set_noise_volt(float(a.noise))

    t0 = time.time()
    tb.start()
    tb.wait()
    try:
        tb.stop()
        tb.wait()
    except Exception:
        pass
    elapsed = time.time() - t0

    files = {}
    for path in filter(None, a.outputs.split(";")):
        full = os.path.join(a.work_dir, path)
        if os.path.exists(full):
            x = np.fromfile(full, dtype=np.complex64)
            files[path] = {"samples": int(x.size), "path": full}
        else:
            files[path] = {"samples": 0, "path": full}

    print("GRCJSON " + json.dumps({
        "ok": True, "elapsed": elapsed, "files": files,
        "gr_version": _version(),
    }))
    return 0


def _version() -> str:
    try:
        from gnuradio import gr
        return gr.version()
    except Exception:
        return "?"


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - el error viaja a la interfaz
        print("GRCJSON " + json.dumps({"ok": False,
                                       "error": f"{type(exc).__name__}: {exc}"}))
        sys.exit(1)

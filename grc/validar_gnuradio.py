"""Validación cruzada Python <-> GNU Radio de una corrida, con un solo comando.

    1. Toma la corrida: una carpeta, su parametros.txt o el JSON que exporta
       la aplicación (en ese caso la genera primero con generar_corrida.py).
    2. Compila validacion_gnuradio.grc con grcc y lo ejecuta sin ventanas con
       el Python de radioconda (ejecutar_flowgraph.py).
    3. Compara lo que escribió GNU Radio con lo de Python y deja en
       <corrida>/comparacion/ la tabla (txt y csv) y la figura.

Uso (desde la raíz del proyecto, con .venv):
    .venv\\Scripts\\python grc\\validar_gnuradio.py                       # la corrida más reciente
    .venv\\Scripts\\python grc\\validar_gnuradio.py grc\\corridas\\ejemplo
    .venv\\Scripts\\python grc\\validar_gnuradio.py comm2_config.json      # el JSON de la aplicación
    .venv\\Scripts\\python grc\\validar_gnuradio.py grc\\corridas\\ejemplo --sin-ejecutar
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(AQUI))

import numpy as np  # noqa: E402

from corrida import cf32, comprobar, leer_txt  # noqa: E402

FLOWGRAPH = AQUI / "validacion_gnuradio.grc"
GENERADO = AQUI / "generado"


# ---------------------------------------------------------------------------
# GNU Radio
# ---------------------------------------------------------------------------


def radioconda() -> tuple[Path, Path]:
    """(python, grcc) de la instalación de GNU Radio."""
    candidatos = [Path(os.environ["GNURADIO_HOME"])] if "GNURADIO_HOME" in os.environ else []
    candidatos += [Path.home() / "radioconda", Path("C:/radioconda")]
    for raiz in candidatos:
        py, grcc = raiz / "python.exe", raiz / "Scripts" / "grcc.exe"
        if py.is_file() and grcc.is_file():
            return py, grcc
    raise SystemExit("No encuentro GNU Radio (radioconda). Define GNURADIO_HOME con su carpeta.")


def ejecutar(parametros: Path) -> dict:
    py, grcc = radioconda()
    gen = GENERADO / "validacion_gnuradio.py"
    if not gen.is_file() or gen.stat().st_mtime < FLOWGRAPH.stat().st_mtime:
        print("  Compilando validacion_gnuradio.grc con grcc...")
        GENERADO.mkdir(exist_ok=True)
        r = subprocess.run([str(grcc), "-o", str(GENERADO), str(FLOWGRAPH)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0 or not gen.is_file():
            raise SystemExit("grcc falló:\n" + (r.stdout + r.stderr)[-2000:])
    print("  Ejecutando el flowgraph con GNU Radio (sin ventanas)...")
    r = subprocess.run([str(py), str(AQUI / "ejecutar_flowgraph.py"), str(GENERADO),
                        "validacion_gnuradio", str(parametros)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=600)
    linea = next((l for l in r.stdout.splitlines() if l.startswith("GRCJSON ")), None)
    if linea is None:
        raise SystemExit("El flowgraph no respondió:\n" + (r.stdout + r.stderr)[-2000:])
    res = json.loads(linea[len("GRCJSON "):])
    if not res["ok"]:
        raise SystemExit("El flowgraph falló: " + res["error"])
    return res


# ---------------------------------------------------------------------------
# Comparación
# ---------------------------------------------------------------------------


def _papr_db(x):
    p = np.abs(x[np.abs(x) > 0]) ** 2
    return float(10 * np.log10(p.max() / p.mean()))


def _wilson(e, n):
    """Intervalo de confianza 95 % de una proporción (válido con 0 errores)."""
    z, p = 1.96, e / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(c - h, 0.0), c + h


def _ber_txt(e, n):
    # Nunca BER = 0: sin errores solo hay una cota.
    return f"{e / n:.2e} ({e}/{n})" if e else f"< {1 / n:.1e} (0/{n})"


def receptor_grc(P, d: Path):
    """BER y EVM de los símbolos que escribió el receptor de GNU Radio."""
    from comm2 import metrics, sync
    from comm2.modulation import Modulation

    s = cf32(d / "simbolos_tx.cf32")
    g, z, nt, npl = (int(P[k]) for k in ("guard", "zc_len", "n_train", "n_payload"))
    tr = s[g + 2 * z: g + 2 * z + nt]
    pay = s[g + 2 * z + nt: g + 2 * z + nt + npl]
    y = cf32(d / "gnuradio" / "grc_simbolos_rx.cf32")
    # El receptor de GNU Radio no sabe dónde empieza la trama: se localiza el
    # entrenamiento por correlación, igual que hace el de Python.
    i0, corr, _ = sync.fine_frame_sync(y, tr, search=max(min(y.size - nt - npl, 4000), 1))
    rx = y[i0 + nt: i0 + nt + npl]
    if corr < 0.3 or rx.size < npl:
        return None
    # Ganancia compleja residual por mínimos cuadrados sobre la carga útil
    # (resuelve también la ambigüedad de fase de k·90° del lazo de Costas).
    rx = rx * np.vdot(rx, pay) / np.vdot(rx, rx)
    mod = Modulation(P["modulacion"])
    ber = metrics.bit_error_rate(mod.demodulate(pay), mod.demodulate(rx))
    return {"errores": ber.errors, "bits": ber.total, "evm": metrics.evm_percent(rx, pay),
            "corr": corr, "simbolos": rx}


def comparar(d: Path) -> list[dict]:
    from comm2 import metrics

    P = leer_txt(d / "parametros.txt")
    R = leer_txt(d / "resultados_python.txt")
    fs = float(P["fs"])
    py_tx, py_rx = cf32(d / "senal_tx.cf32"), cf32(d / "senal_rx.cf32")
    gr_tx, gr_rx = cf32(d / "gnuradio" / "grc_tx.cf32"), cf32(d / "gnuradio" / "grc_rx.cf32")

    n = min(py_tx.size, gr_tx.size)
    nmse = 10 * np.log10(np.sum(np.abs(py_tx[:n] - gr_tx[:n]) ** 2) / np.sum(np.abs(py_tx[:n]) ** 2))
    filas = [
        {"etapa": "Transmisor", "magnitud": "Diferencia muestra a muestra (NMSE)",
         "python": "referencia", "gnuradio": f"{nmse:.1f} dB", "diferencia": f"{n} muestras"},
    ]

    def fila(etapa, mag, a, b, fmt, unidad="", rel=True):
        dif = (f"{100 * (b - a) / a:+.1f} %" if rel else f"{b - a:+.2f}{unidad}")
        filas.append({"etapa": etapa, "magnitud": mag, "python": fmt.format(a) + unidad,
                      "gnuradio": fmt.format(b) + unidad, "diferencia": dif})

    fila("Transmisor", "Ancho de banda 99 %", metrics.occupied_bandwidth(py_tx, fs) / 1e3,
         metrics.occupied_bandwidth(gr_tx, fs) / 1e3, "{:.2f}", " kHz")
    fila("Transmisor", "PAPR", _papr_db(py_tx), _papr_db(gr_tx), "{:.2f}", " dB", rel=False)
    fila("Transmisor", "Potencia media", np.mean(np.abs(py_tx) ** 2),
         np.mean(np.abs(gr_tx) ** 2), "{:.5f}")
    m = min(py_rx.size, gr_rx.size)
    fila("Canal", "Potencia recibida (señal + ruido)", np.mean(np.abs(py_rx[:m]) ** 2),
         np.mean(np.abs(gr_rx[:m]) ** 2), "{:.5f}")

    rx = receptor_grc(P, d)
    e_py, n_py = int(R["ber_errores"]), int(R["ber_bits"])
    if rx is None:
        filas.append({"etapa": "Receptor", "magnitud": "BER", "python": _ber_txt(e_py, n_py),
                      "gnuradio": "no enganchó", "diferencia": "—"})
    else:
        lo_p, hi_p = _wilson(e_py, n_py)
        lo_g, hi_g = _wilson(rx["errores"], rx["bits"])
        solapan = lo_p <= hi_g and lo_g <= hi_p
        filas.append({"etapa": "Receptor", "magnitud": "BER", "python": _ber_txt(e_py, n_py),
                      "gnuradio": _ber_txt(rx["errores"], rx["bits"]),
                      "diferencia": "compatibles (IC 95 % se solapan)" if solapan
                      else "distintas (IC 95 % no se solapan)"})
        fila("Receptor", "EVM [%]", float(R["evm_pct"]), rx["evm"], "{:.1f}", "", rel=False)
    return filas, P, rx


def figura(d: Path, P: dict, rx) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from comm2 import plots

    plots.setup()
    fs, sps = float(P["fs"]), int(P["sps"])
    C_PY, C_GR = "#1f77b4", "#d62728"     # azul Python, rojo GNU Radio
    py_tx, gr_tx = cf32(d / "senal_tx.cf32"), cf32(d / "gnuradio" / "grc_tx.cf32")
    py_rx, gr_rx = cf32(d / "senal_rx.cf32"), cf32(d / "gnuradio" / "grc_rx.cf32")

    fig, ax = plt.subplots(2, 2, figsize=(11, 7.5), constrained_layout=True)
    plots.psd(ax[0, 0], py_tx, fs, "Python", rs=fs / sps, beta=float(P["rolloff"]), color=C_PY, lw=2.5)
    plots.psd(ax[0, 0], gr_tx, fs, "GNU Radio", color=C_GR, lw=1)
    ax[0, 0].set_title("Espectro transmitido")
    ax[0, 0].legend(fontsize=7)

    i0 = (int(P["guard"]) + 2 * int(P["zc_len"])) * sps     # inicio del entrenamiento
    t = np.arange(i0, i0 + 12 * sps)
    ax[0, 1].plot(t / sps, py_tx[t].real, color=C_PY, lw=3, alpha=0.5, label="Python")
    ax[0, 1].plot(t / sps, gr_tx[t].real, color=C_GR, lw=1, label="GNU Radio")
    ax[0, 1].set_title("Señal transmitida, parte real (12 símbolos)")
    ax[0, 1].set_xlabel("tiempo [T]")
    ax[0, 1].legend(fontsize=7)

    plots.psd(ax[1, 0], py_rx, fs, "Python", color=C_PY, lw=2.5)
    plots.psd(ax[1, 0], gr_rx, fs, "GNU Radio", color=C_GR, lw=1)
    ax[1, 0].set_title("Espectro tras el canal")
    ax[1, 0].legend(fontsize=7)

    from comm2.modulation import Modulation
    mod = Modulation(P["modulacion"])
    py_sym = cf32(d / "simbolos_rx_python.cf32")
    plots.constellation(ax[1, 1], py_sym, mod=mod, color=C_PY, n_max=2000)
    if rx is not None:
        ax[1, 1].plot(rx["simbolos"][:2000].real, rx["simbolos"][:2000].imag, ".", ms=2,
                      alpha=0.25, color=C_GR, rasterized=True)
    ax[1, 1].set_title("Carga útil a la salida del receptor\n(azul Python, rojo GNU Radio)")

    fig.suptitle(f"Validación cruzada · escenario {P['escenario']}, canal {P['perfil']}, "
                 f"{str(P['modulacion']).upper()}, Eb/N0 = {P['ebn0_db']} dB")
    out = d / "comparacion" / "validacion.png"
    fig.savefig(out)
    plt.close(fig)
    return out


def escribir_tabla(d: Path, filas: list[dict]) -> str:
    import csv

    (d / "comparacion").mkdir(exist_ok=True)
    with open(d / "comparacion" / "tabla.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    anchos = {k: max(len(k), *(len(str(f[k])) for f in filas)) for k in filas[0]}
    cab = "  ".join(k.upper().ljust(anchos[k]) for k in filas[0])
    lineas = [cab, "-" * len(cab)]
    lineas += ["  ".join(str(f[k]).ljust(anchos[k]) for k in f) for f in filas]
    texto = "\n".join(lineas)
    (d / "comparacion" / "tabla.txt").write_text(texto + "\n", encoding="utf-8")
    return texto


# ---------------------------------------------------------------------------


def resolver(arg: str) -> Path:
    """Carpeta de la corrida a partir de lo que se pase en la línea de órdenes."""
    if not arg:
        corridas = [p.parent for p in (AQUI / "corridas").glob("*/parametros.txt")]
        if not corridas:
            raise SystemExit("No hay corridas: genera una con grc/generar_corrida.py")
        return max(corridas, key=lambda c: (c / "parametros.txt").stat().st_mtime)
    p = Path(arg)
    if p.suffix.lower() == ".json":
        from generar_corrida import generar
        print("JSON de la aplicación: se simula para obtener las señales.")
        return generar(argparse.Namespace(json=str(p), salida=""))
    return p.parent if p.is_file() else p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corrida", nargs="?", default="",
                    help="carpeta, parametros.txt o JSON de la aplicación")
    ap.add_argument("--sin-ejecutar", action="store_true",
                    help="no ejecutar GNU Radio; comparar lo que ya haya en gnuradio/")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    d = resolver(a.corrida).resolve()
    print(f"Corrida: {d}")
    problemas = comprobar(d)
    if problemas:
        raise SystemExit("La corrida no sirve:\n  " + "\n  ".join(problemas))
    if not a.sin_ejecutar:
        res = ejecutar(d / "parametros.txt")
        print(f"  GNU Radio {res['version']}: {res['segundos']:.2f} s")
    elif not (d / "gnuradio" / "grc_tx.cf32").is_file():
        raise SystemExit("No hay salidas de GNU Radio en gnuradio/: ejecuta sin --sin-ejecutar.")

    filas, P, rx = comparar(d)
    texto = escribir_tabla(d, filas)
    png = figura(d, P, rx)
    print()
    print(texto)
    print()
    print(f"Tabla y figura en {d / 'comparacion'}")
    print(f"  {png.name}, tabla.txt, tabla.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())

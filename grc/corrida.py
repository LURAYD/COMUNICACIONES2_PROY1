"""Formato de intercambio Python <-> GNU Radio: la «corrida».

Una corrida es una carpeta con los datos de UN enlace simulado y los
parámetros con que se simuló, en un formato que GNU Radio lee sin depender de
este proyecto:

    corrida/
    ├── parametros.txt            los valores usados (clave = valor)
    ├── resultados_python.txt     BER, EVM… del receptor de Python
    ├── simbolos_tx.cf32          símbolos que entran al filtro RRC (con guarda)
    ├── senal_tx.cf32             señal transmitida (tras el RRC, antes del canal)
    ├── senal_rx.cf32             señal recibida (tras el canal de Python)
    ├── simbolos_rx_python.cf32   carga útil a la salida del receptor de Python
    ├── gnuradio/                 lo escriben los flowgraphs de GNU Radio
    └── comparacion/              lo escribe validar_gnuradio.py

`.cf32` es complex64 con I y Q intercalados: el formato interno de GNU Radio,
que el bloque File Source lee tal cual y NumPy con `np.fromfile(f, np.complex64)`.

Quien genere la corrida (el botón de la aplicación o `generar_corrida.py`)
solo tiene que llamar a `escribir_corrida(r, carpeta)` con el `LinkResult` de
`run_link`. El formato está descrito para personas en FORMATO.md.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import numpy as np

VERSION_FORMATO = 1

# Claves obligatorias de parametros.txt: si falta alguna, los flowgraphs
# usarían su valor por defecto sin avisar y la comparación no valdría nada.
OBLIGATORIAS = ("modulacion", "fs", "sps", "rolloff", "span", "zc_len",
                "n_train", "n_payload", "guard", "ebn0_db", "noise_voltage",
                "cfo_hz", "fase_grados", "reloj_ppm", "retardo_frac",
                "taps_canal", "eq_taps", "eq_mu")

FICHEROS = ("parametros.txt", "simbolos_tx.cf32", "senal_tx.cf32", "senal_rx.cf32")


def _c(z: complex) -> str:
    """Complejo sin espacios: `complex()` lo lee tal cual en ambos lados."""
    return f"{z.real:+.8f}{z.imag:+.8f}j"


def escribir_corrida(r, carpeta, origen: str = "") -> Path:
    """Escribe la corrida de un `LinkResult` en `carpeta` y devuelve la ruta."""
    from comm2.frame import add_guard

    d = Path(carpeta)
    d.mkdir(parents=True, exist_ok=True)
    p, ch, frm = r.params, r.chan, r.frame
    k = frm.mod.bits_per_symbol

    taps = np.asarray(r.sync_info["channel_taps"], dtype=complex)
    sigma2 = float(r.sync_info["sigma2"])
    eq = r.rxcfg.eq

    lineas = [
        "# Corrida para la validación cruzada Python <-> GNU Radio",
        f"# Generada por: {origen or 'comm2'}",
        f"# Fecha: {_dt.datetime.now():%Y-%m-%d %H:%M:%S}",
        "# Formato: clave = valor  (lo que va tras '#' es comentario)",
        "",
        f"formato        = {VERSION_FORMATO}",
        f"escenario      = {ch.name}",
        f"perfil         = {ch.profile.name.replace(',', ' ')}",
        f"modulacion     = {frm.mod.name}",
        "",
        "# --- Transmisor",
        f"fs             = {p.fs:g}          # Hz, frecuencia de muestreo",
        f"sps            = {p.sps}           # muestras por símbolo",
        f"rolloff        = {p.beta:g}        # roll-off del RRC",
        f"span           = {p.span}          # duración del RRC en símbolos (span*sps+1 coeficientes, energía 1)",
        f"zc_len         = {p.zc_len}        # cada mitad del preámbulo Zadoff-Chu",
        f"n_train        = {frm.n_train}     # símbolos de entrenamiento",
        f"n_payload      = {frm.n_payload}   # símbolos de datos",
        f"guard          = {p.guard}         # ceros antes y después de la ráfaga",
        "",
        "# --- Canal (en el orden en que se aplica)",
        f"ebn0_db        = {ch.ebn0_db:g}",
        f"noise_voltage  = {np.sqrt(sigma2):.8f}   # desviación típica del ruido complejo = sqrt(1/(k*Eb/N0)); en GNU Radio va tal cual",
        f"cfo_hz         = {ch.cfo_hz:g}     # desplazamiento de frecuencia",
        f"fase_grados    = {np.degrees(ch.phase_off_rad):g}",
        f"reloj_ppm      = {ch.clock_ppm:g}  # deriva del reloj de muestreo",
        f"retardo_frac   = {ch.timing_frac:g}  # muestras; GNU Radio no lo reproduce",
        f"rayleigh       = {int(bool(ch.rayleigh))}  # 1 = desvanecimiento variable; GNU Radio no lo reproduce",
        f"n_taps_canal   = {taps.size}",
        "taps_canal     = " + ",".join(_c(t) for t in taps)
        + "   # canal a tasa de MUESTREO, ya interpolado",
        "",
        "# --- Receptor de Python (el de GNU Radio usa los mismos valores)",
        f"ecualizador    = {eq.kind}",
        f"eq_taps        = {eq.n_taps}",
        f"eq_mu          = {eq.mu:g}",
        f"semilla        = {p.seed}",
        f"bits_por_simbolo = {k}",
    ]
    (d / "parametros.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")

    st = r.stats
    res = [
        "# Resultados del receptor de Python sobre esta misma corrida",
        f"ber            = {st['ber']:.6e}",
        f"ber_errores    = {st['ber_errors']}",
        f"ber_bits       = {st['ber_bits']}",
        f"evm_pct        = {st['evm_pct']:.4f}",
        f"enganchado     = {int(bool(r.locked))}",
    ]
    (d / "resultados_python.txt").write_text("\n".join(res) + "\n", encoding="utf-8")

    def _cf32(nombre, x):
        np.asarray(x, dtype=np.complex64).tofile(d / nombre)

    _cf32("simbolos_tx.cf32", add_guard(frm.symbols, p.guard))
    _cf32("senal_tx.cf32", r.tx_signal)
    _cf32("senal_rx.cf32", r.rx_signal)
    _cf32("simbolos_rx_python.cf32", r.payload_rx)
    return d


# ---------------------------------------------------------------------------
# Lectura (lado Python: la usa validar_gnuradio.py)
# ---------------------------------------------------------------------------


def _valor(v: str):
    if "," in v:
        try:
            return [complex(x) for x in v.split(",") if x.strip()]
        except ValueError:
            return v
    for conv in (int, float, complex):
        try:
            return conv(v)
        except ValueError:
            pass
    return v


def leer_txt(ruta) -> dict:
    """Lee un fichero `clave = valor` como el que escribe `escribir_corrida`."""
    out = {}
    for linea in Path(ruta).read_text(encoding="utf-8").splitlines():
        linea = linea.split("#", 1)[0].strip()
        if "=" in linea:
            k, v = linea.split("=", 1)
            out[k.strip()] = _valor(v.strip())
    return out


def comprobar(carpeta) -> list[str]:
    """Problemas que impiden usar la carpeta. Lista vacía si está bien."""
    d = Path(carpeta)
    falta = [f for f in FICHEROS if not (d / f).is_file()]
    if falta:
        return [f"falta el fichero {f}" for f in falta]
    P = leer_txt(d / "parametros.txt")
    return [f"parametros.txt no tiene la clave '{k}'" for k in OBLIGATORIAS if k not in P]


def cf32(ruta) -> np.ndarray:
    return np.fromfile(ruta, dtype=np.complex64).astype(complex)

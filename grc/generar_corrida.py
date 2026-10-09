"""Genera una corrida de prueba para GNU Radio sin pasar por la aplicación.

Hace lo mismo que hará el botón «Calcular» del banco de pruebas: simula un
enlace con `run_link` y lo vuelca con `corrida.escribir_corrida`. Sirve para
trabajar en los flowgraphs sin esperar a la aplicación.

Uso (desde la raíz del proyecto, con el entorno .venv):
    .venv\\Scripts\\python grc\\generar_corrida.py
    .venv\\Scripts\\python grc\\generar_corrida.py --escenario B --ebn0 12 --perfil moderate
    .venv\\Scripts\\python grc\\generar_corrida.py --perfil "0,0.2,1,0,0.8" --salida grc\\corridas\\mi_canal
    .venv\\Scripts\\python grc\\generar_corrida.py --json comm2_config.json   # el JSON de la aplicación
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(AQUI))

from comm2 import EqualizerConfig, ReceiverConfig, SystemParams, run_link, scenarios  # noqa: E402

from corrida import escribir_corrida  # noqa: E402


def simular(escenario: str, ebn0: float, perfil: str, mod: str, eq: str,
            n_payload: int):
    # Mismos valores por defecto que app/engine.py::Request
    p = SystemParams(mod=mod, beta=0.35, n_payload=n_payload, n_train=512)
    rx = ReceiverConfig(eq=EqualizerConfig(kind=eq, n_taps=21, mu=0.50, lam=0.995))
    e = escenario.upper()
    if e == "A":
        chan = scenarios.scenario_a(p, ebn0_db=ebn0)
    elif e == "B":
        chan = scenarios.scenario_b(p, ebn0_db=ebn0, profile=perfil)
    else:
        chan = scenarios.scenario_c(p, ebn0_db=ebn0, profile=perfil)
    return run_link(p, chan, rx)


def desde_json(ruta):
    """Simula el enlace descrito por el JSON que exporta la aplicación.

    Es el fichero de «Exportar → Guardar JSON» (app/gnuradio_json.py). Trae
    los parámetros pero no las señales, así que aquí se vuelve a simular con
    esos mismos valores para tener las formas de onda.
    """
    import json

    import numpy as np
    from comm2.channel import ChannelConfig, get_profile

    c = json.loads(Path(ruta).read_text(encoding="utf-8"))
    p = SystemParams(fs=c["samp_rate"], sps=c["sps"], beta=c["rrc_beta"],
                     span=c["rrc_span"], mod=c["modulation"], zc_len=c["zc_len"],
                     n_train=c["n_train"], n_payload=c["n_payload"], guard=c["guard"])
    perfil = get_profile(c["channel_profile"])
    taps = np.array(c["channel_taps_re"]) + 1j * np.array(c["channel_taps_im"])
    propios = perfil.taps(p.sps)
    if propios.size != taps.size or not np.allclose(propios, taps, atol=1e-6):
        raise SystemExit(f"El canal '{c['channel_profile']}' no reproduce los taps del JSON.")
    chan = ChannelConfig(name=c["scenario"], profile=perfil, ebn0_db=c["ebn0_db"],
                         cfo_hz=c["freq_offset_hz"], phase_off_rad=c["phase_offset_rad"],
                         timing_frac=c["timing_offset_samples"], clock_ppm=c["clock_ppm"],
                         rayleigh=c["rayleigh"], fd_hz=c["doppler_hz"])
    rx = ReceiverConfig(matched_filter=c["matched_filter"],
                        timing_recovery=c["timing_recovery"],
                        cfo_correction=c["cfo_correction"], phase_pll=c["phase_pll"],
                        eq=EqualizerConfig(kind=c["equalizer"], n_taps=c["eq_ntaps"],
                                           mu=c["eq_mu"], lam=c["eq_lambda"]))
    return run_link(p, chan, rx)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", default="",
                    help="JSON exportado por la aplicación (sección Exportar)")
    ap.add_argument("--escenario", default="B", choices=list("ABCabc"))
    ap.add_argument("--ebn0", type=float, default=12.0, help="Eb/N0 en dB")
    ap.add_argument("--perfil", default="moderate",
                    help="flat, mild, moderate, severe, 'aleatorio:SEMILLA' o h a mano '0,0.2,1,0,0.8'")
    ap.add_argument("--mod", default="qpsk")
    ap.add_argument("--eq", default="lms", help="none, lms, rls, zf, mmse, cma")
    ap.add_argument("--n-payload", type=int, default=4000)
    ap.add_argument("--salida", default="", help="carpeta (por defecto grc/corridas/...)")
    a = ap.parse_args()

    carpeta = generar(a)
    print(f"Corrida escrita en {carpeta}")
    return 0


def generar(a) -> Path:
    """Simula y escribe la corrida; devuelve la carpeta."""
    if a.json:
        r = desde_json(a.json)
        nombre = Path(a.json).stem
        origen = f"JSON de la aplicación ({Path(a.json).name})"
    else:
        r = simular(a.escenario, a.ebn0, a.perfil, a.mod, a.eq, a.n_payload)
        nombre = f"{a.escenario.upper()}_{r.chan.profile.name}_{a.ebn0:g}dB_{a.mod}"
        origen = "grc/generar_corrida.py"
    nombre = "".join(c if c.isalnum() or c in "_.-" else "_" for c in nombre)[:60]
    carpeta = Path(a.salida) if a.salida else AQUI / "corridas" / nombre
    escribir_corrida(r, carpeta, origen=origen)

    st = r.stats
    k_n = st["ber_bits"]
    ber = (f"{st['ber']:.2e}" if st["ber_errors"] else f"< {1 / k_n:.1e} (0 errores)")
    print(f"  {r.chan.describe(r.params.sps, r.params.fs)}")
    print(f"  Receptor de Python: BER {ber}, EVM {st['evm_pct']:.1f} %")
    return carpeta


if __name__ == "__main__":
    sys.exit(main())

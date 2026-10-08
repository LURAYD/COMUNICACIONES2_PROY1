"""Prueba de reproducibilidad de la campana completa.

Ejecuta los siete experimentos de principio a fin con una carga util minima y
escribiendo en un directorio temporal. No busca resultados con sentido
estadistico: busca que TODAS las rutas de codigo se ejecuten sin error,
incluidas las de generacion de figuras, que son las que mas facilmente quedan
sin probar cuando se retoca una grafica.

Es la garantia de que `experiments/run_all.py` reproduce la campana entera a
partir del repositorio limpio, que es el entregable (e) de la guia: "archivos
de resultados necesarios para reproducir las graficas".

    python tests/test_campana.py          # ~5 min
    pytest tests/test_campana.py

Para la validacion numerica de cada bloque por separado, ver test_comm2.py.
"""

from __future__ import annotations

import sys
import tempfile
import time
import traceback
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

# Carga util minima: suficiente para que la sincronizacion enganche y el
# ecualizador converja, pero ~30x mas rapida que la campana real.
N_PAYLOAD = 600
N_TRAIN = 128
N_PUNTOS_BARRIDO = 2


def _preparar(tmp: Path):
    """Redirige las salidas al directorio temporal y recorta los barridos."""
    import _common
    from comm2 import plots

    (tmp / "data").mkdir(parents=True, exist_ok=True)
    (tmp / "figures").mkdir(parents=True, exist_ok=True)
    _common.DATA = tmp / "data"
    _common.FIGS = tmp / "figures"
    plots.FIG_DIR = tmp / "figures"
    plots.DATA_DIR = tmp / "data"
    _common.BASE = _common.BASE.replace(n_payload=N_PAYLOAD, n_train=N_TRAIN)

    import exp0_diagrama_bloques, exp1_ber_awgn, exp2_isi, exp3_ecualizacion
    import exp4_robustez, exp5_modulacion

    modulos = (exp1_ber_awgn, exp2_isi, exp3_ecualizacion, exp4_robustez,
               exp5_modulacion)
    for m in modulos:
        m.BASE = _common.BASE
        ebn0 = getattr(m, "EBN0", None)
        if isinstance(ebn0, np.ndarray):
            m.EBN0 = ebn0[:N_PUNTOS_BARRIDO]

    return [("0 diagrama de bloques", exp0_diagrama_bloques.main),
            ("1 BER en AWGN", exp1_ber_awgn.main),
            ("2 efecto de la ISI", exp2_isi.main),
            ("3 ecualizacion", exp3_ecualizacion.main),
            ("4 robustez", exp4_robustez.main),
            ("5 modulaciones", exp5_modulacion.main)]


def test_campana_completa_se_ejecuta_sin_errores():
    with tempfile.TemporaryDirectory(prefix="comm2_campana_") as d:
        tmp = Path(d)
        pasos = _preparar(tmp)
        fallos = []
        for nombre, fn in pasos:
            t0 = time.time()
            try:
                fn()
                print(f"  OK     {nombre:24s} {time.time()-t0:6.1f} s", flush=True)
            except Exception as e:
                fallos.append((nombre, e))
                print(f"  FALLO  {nombre}", flush=True)
                traceback.print_exc()

        figs = sorted(p.name for p in (tmp / "figures").glob("*.png"))
        tabs = sorted(p.name for p in (tmp / "data").glob("*.csv"))
        print(f"\n  {len(figs)} figuras, {len(tabs)} tablas, {len(fallos)} fallos")

        assert not fallos, f"experimentos con error: {[n for n, _ in fallos]}"
        # La campana debe producir al menos una figura por experimento y las
        # tablas de los cinco experimentos que las generan.
        assert len(figs) >= 7, figs
        assert len(tabs) >= 12, tabs


def main() -> int:
    try:
        test_campana_completa_se_ejecuta_sin_errores()
    except AssertionError as e:
        print(f"\n  FALLA: {e}")
        return 1
    print("\n  Campana reproducible: todos los experimentos completan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Ejecuta toda la campana de simulacion y regenera tablas y figuras.

    python run_all.py            # todo
    python run_all.py 1 3 5      # solo los experimentos indicados
    python run_all.py --lista    # ver que hay disponible

Los resultados se escriben en results/data/*.csv y results/figures/*.png.
Todo es determinista: la semilla base esta en _common.BASE.seed.
"""

from __future__ import annotations

import argparse
import time
import traceback

import exp0_diagrama_bloques
import exp1_ber_awgn
import exp2_isi
import exp3_ecualizacion
import exp4_robustez
import exp5_modulacion
import exp6_validacion_grc
from _common import ROOT, banner

PASOS = {
    "0": ("Diagrama de bloques del sistema", exp0_diagrama_bloques.main),
    "1": ("BER teorica vs simulada en AWGN", exp1_ber_awgn.main),
    "2": ("Efecto de la ISI", exp2_isi.main),
    "3": ("Comparacion de ecualizadores", exp3_ecualizacion.main),
    "4": ("Robustez", exp4_robustez.main),
    "5": ("Comparacion de modulaciones", exp5_modulacion.main),
    "6": ("Validacion cruzada con GNU Radio", exp6_validacion_grc.main),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pasos", nargs="*", help="numeros de experimento a ejecutar")
    ap.add_argument("--lista", action="store_true")
    args = ap.parse_args()

    if args.lista:
        for k, (nombre, _) in PASOS.items():
            print(f"  {k}  {nombre}")
        return

    pedidos = args.pasos or list(PASOS)
    t_total = time.time()
    resumen = []
    for k in pedidos:
        if k not in PASOS:
            print(f"  paso desconocido: {k}")
            continue
        nombre, fn = PASOS[k]
        t0 = time.time()
        try:
            fn()
            estado = "OK"
        except Exception:
            estado = "FALLO"
            traceback.print_exc()
        resumen.append((k, nombre, estado, time.time() - t0))

    banner("RESUMEN")
    for k, nombre, estado, dt in resumen:
        print(f"  [{estado:5s}] {k}  {nombre:45s} {dt:7.1f} s")
    print(f"\n  Tiempo total: {time.time() - t_total:.1f} s")
    print(f"  Tablas : {(ROOT / 'results' / 'data')}")
    print(f"  Figuras: {(ROOT / 'results' / 'figures')}")


if __name__ == "__main__":
    main()

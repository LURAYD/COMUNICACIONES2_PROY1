"""Resumen ejecutivo de la campana: lee results/data/*.csv y produce las tablas
que van al informe.

    python resumen.py            # imprime por pantalla
    python resumen.py --md       # ademas escribe results/RESUMEN.md

No recalcula nada: solo consolida lo que hayan generado los experimentos, de
modo que las cifras del informe y las de los CSV no puedan divergir.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd

from _common import DATA, ROOT, banner
from comm2 import SystemParams
from comm2.modulation import Modulation

BASE = SystemParams()


def _leer(nombre: str) -> pd.DataFrame | None:
    f = DATA / f"{nombre}.csv"
    return pd.read_csv(f) if f.exists() else None


def _fmt(v, fmt="{:.2e}"):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "—"
    if isinstance(v, float) and v == 0.0:
        return "< 1e-6"
    return fmt.format(v)


def _tabla_md(df: pd.DataFrame) -> str:
    # Las columnas pueden no ser cadenas (p. ej. tras un pivot sobre lambda).
    cols = list(df.columns)
    cab = [str(c) for c in cols]
    out = ["| " + " | ".join(cab) + " |",
           "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(out)


def resumen() -> list[tuple[str, pd.DataFrame]]:
    secciones: list[tuple[str, pd.DataFrame]] = []

    # ---------------------------------------------------- Exp 1: validacion
    d = _leer("exp1_perdida_implementacion")
    if d is not None:
        filas = []
        for m, g in d.groupby("mod"):
            filas.append({"Modulacion": m.upper(),
                          "Razon BER sim/teo (mediana)": f"{g['razon'].median():.2f}",
                          "Razon maxima": f"{g['razon'].max():.2f}",
                          "Puntos comparados": len(g)})
        secciones.append(("Experimento 1 — validacion en AWGN", pd.DataFrame(filas)))

    # ---------------------------------------------------------- Exp 2: ISI
    d = _leer("exp2_isi")
    if d is not None:
        t = d[["perfil", "tau_rms_T", "apertura_ojo", "evm_pct", "ber"]].copy()
        t.columns = ["Perfil", "tau_rms [T]", "Apertura del ojo", "EVM [%]", "BER"]
        t["tau_rms [T]"] = t["tau_rms [T]"].map("{:.3f}".format)
        t["Apertura del ojo"] = t["Apertura del ojo"].map("{:.3f}".format)
        t["EVM [%]"] = t["EVM [%]"].map("{:.1f}".format)
        t["BER"] = t["BER"].map(_fmt)
        secciones.append(("Experimento 2 — efecto de la ISI", t))

    # ------------------------------------------------ Exp 3: ecualizadores
    d = _leer("exp3_comparacion_detallada")
    if d is not None:
        t = d[["etiqueta", "ber", "mse_residual_db", "conv_a_-9dB",
               "mult_reales_por_simbolo", "orden"]].copy()
        t.columns = ["Metodo", "BER", "MSE residual [dB]",
                     "Convergencia a -9 dB [simb]", "Mult. reales/simbolo", "Orden"]
        t["BER"] = t["BER"].map(_fmt)
        t["MSE residual [dB]"] = t["MSE residual [dB]"].map("{:.2f}".format)
        secciones.append(("Experimento 3 — comparacion de ecualizadores", t))

    d = _leer("exp3_sensibilidad_parametros")
    if d is not None:
        t = d.copy()
        t["ber"] = t["ber"].map(_fmt)
        t["mse_residual_db"] = t["mse_residual_db"].map("{:.2f}".format)
        t.columns = ["Metodo", "Parametro", "Valor", "BER", "MSE residual [dB]",
                     "Convergencia a -6 dB"]
        secciones.append(("Experimento 3 — sensibilidad a mu y lambda", t))

    # ------------------------------------------------------ Exp 4: robustez
    d = _leer("exp4_3_cfo")
    if d is not None:
        sub = d[d["eq"] == "rls"]
        limite = None
        for _, r in sub.sort_values("cfo_frac_rs").iterrows():
            if r["ber"] > 1e-2:
                limite = r["cfo_frac_rs"]
                break
        teorico = 1.0 / (2 * BASE.zc_len)
        filas = [{"Magnitud": "Limite medido de adquisicion de CFO",
                  "Valor": f"{limite*100:.2f} % de Rs" if limite else "no alcanzado"},
                 {"Magnitud": "Limite teorico Rs/(2L)",
                  "Valor": f"{teorico*100:.2f} % de Rs"}]
        secciones.append(("Experimento 4.3 — rango de adquisicion de frecuencia",
                          pd.DataFrame(filas)))

    d = _leer("exp4_5_taps_entrenamiento")
    if d is not None:
        sub = d[d["variable"] == "n_train"].pivot(index="valor", columns="eq",
                                                  values="ber")
        sub = sub.reset_index().rename(columns={"valor": "Simbolos de entrenamiento"})
        for c in sub.columns[1:]:
            sub[c] = sub[c].map(_fmt)
        secciones.append(("Experimento 4.5 — BER frente a longitud del entrenamiento",
                          sub))

    d = _leer("exp4_7_rayleigh")
    if d is not None:
        sub = d.pivot(index="fd_frac_rs", columns="lam", values="ber").reset_index()
        sub = sub.rename(columns={"fd_frac_rs": "fD/Rs"})
        for c in sub.columns[1:]:
            sub[c] = sub[c].map(_fmt)
        secciones.append(("Experimento 4.7 — Rayleigh: factor de olvido del RLS", sub))

    # -------------------------------------------------- Exp 5: modulaciones
    d = _leer("exp5_potencia_vs_eficiencia")
    if d is not None:
        t = d.copy()
        t["eta_bps_hz"] = t["eta_bps_hz"].map("{:.2f}".format)
        for c in ("ebn0_req_db", "ebn0_teo_db", "penalizacion_db"):
            t[c] = t[c].map(lambda v: "—" if not np.isfinite(v) else f"{v:.1f}")
        t.columns = ["Escenario", "Modulacion", "k", "eta [b/s/Hz]",
                     "Eb/N0 medido [dB]", "Eb/N0 teorico [dB]", "Penalizacion [dB]"]
        secciones.append(("Experimento 5 — potencia frente a eficiencia espectral "
                          "(BER = 1e-3)", t))

    # ------------------------------------------------ Exp 6: GNU Radio
    d = _leer("exp6_validacion_cruzada")
    if d is not None:
        secciones.append(("Validacion cruzada con GNU Radio", d))

    return secciones


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", action="store_true", help="escribir results/RESUMEN.md")
    args = ap.parse_args()

    banner("RESUMEN DE RESULTADOS")
    secciones = resumen()
    if not secciones:
        print("  No hay resultados todavia. Ejecuta run_all.py primero.")
        return

    partes = ["# Resumen de resultados\n",
              f"Configuracion base: `{BASE.summary()}`\n"]
    for titulo, tabla in secciones:
        print(f"\n## {titulo}\n")
        print(tabla.to_string(index=False))
        partes.append(f"\n## {titulo}\n\n{_tabla_md(tabla)}\n")

    if args.md:
        path = ROOT / "results" / "RESUMEN.md"
        path.write_text("\n".join(partes), encoding="utf-8")
        print(f"\n  -> {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

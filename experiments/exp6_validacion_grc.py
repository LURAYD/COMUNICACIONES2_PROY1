"""Validacion cruzada Python <-> GNU Radio (seccion 11 de la guia).

El experimento representativo elegido es el **Experimento 2** (efecto de la ISI
sobre QPSK con conformacion RRC), porque involucra a la vez el transmisor, el
canal y el receptor, y sus metricas (PSD, constelacion, EVM, BER) son
comparables entre herramientas sin ambiguedad.

Se realizan dos comparaciones complementarias:

  A) GNU Radio como TRANSMISOR + CANAL  (grc/tx_qpsk_canal.grc)
     GRC genera QPSK+RRC y la pasa por su propio modelo de canal. Python mide
     la PSD, el ancho de banda ocupado y la SNR sobre el fichero resultante y
     los contrasta con su propia cadena. Valida el TRANSMISOR y el CANAL.

  B) GNU Radio como RECEPTOR  (grc/rx_qpsk_desde_python.grc)
     GRC procesa exactamente la MISMA forma de onda que genera este simulador
     (io/py_tx_signal.cf32). Como transmisor y canal son identicos, cualquier
     diferencia en la BER es atribuible al receptor. Valida el RECEPTOR.

Formato de intercambio: complex64 intercalado (I,Q), que es exactamente el
formato interno de GNU Radio, de modo que `np.fromfile(f, dtype=np.complex64)`
y el bloque File Source/Sink son directamente compatibles.

Uso:
    python exp6_validacion_grc.py            # exporta ficheros y compara lo que haya
    python exp6_validacion_grc.py --export   # solo exporta
"""

from __future__ import annotations

import argparse
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from _common import BASE, ROOT, banner, eq_config, plots, save_table
from comm2 import ReceiverConfig, metrics, run_link, scenarios, sync
from comm2.channel import PROFILES
from comm2.modulation import Modulation

IO = ROOT / "grc" / "io"
IO.mkdir(parents=True, exist_ok=True)

PY_TX = IO / "py_tx_signal.cf32"
PY_REF = IO / "py_reference.npz"
GRC_TX = IO / "grc_tx_signal.cf32"
GRC_RX = IO / "grc_rx_signal.cf32"
GRC_SYM = IO / "grc_rx_symbols.cf32"
GRC_BYTES = IO / "grc_tx_bytes.bin"

EBN0 = 14.0
PERFIL = "moderate"


# ---------------------------------------------------------------------------
# Exportacion hacia GNU Radio
# ---------------------------------------------------------------------------


def exportar(p) -> dict:
    """Genera la forma de onda de referencia y los datos que necesita GRC."""
    rx = ReceiverConfig(eq=eq_config("rls"))
    r = run_link(p, scenarios.scenario_b(p, EBN0, profile=PERFIL), rx)

    r.tx_signal.astype(np.complex64).tofile(PY_TX)
    np.savez(PY_REF, training=r.frame.training, payload=r.frame.payload,
             bits=r.frame.bits, preamble=r.frame.preamble,
             sps=p.sps, beta=p.beta, n_train=p.n_train, n_payload=p.n_payload,
             ber_python=r.stats["ber"], evm_python=r.stats["evm_pct"])

    taps = PROFILES[PERFIL].taps(p.sps)
    taps_str = "[" + ", ".join(f"{t.real:+.6f}{t.imag:+.6f}j" for t in taps) + "]"
    (IO / "ch_taps_para_grc.txt").write_text(
        "# Pegar como valor de la variable ch_taps en el flowgraph de GRC\n"
        f"# Perfil '{PERFIL}' a {p.sps} muestras/simbolo, {taps.size} taps\n"
        + taps_str + "\n", encoding="utf-8")

    print(f"  Exportado {PY_TX.name}: {r.tx_signal.size} muestras complex64 "
          f"({PY_TX.stat().st_size/1e6:.2f} MB)")
    print(f"  Exportado {PY_REF.name}: trama de referencia para calcular la BER")
    print(f"  Exportado ch_taps_para_grc.txt: {taps.size} taps del canal '{PERFIL}'")
    print(f"  Referencia Python: BER={r.stats['ber']:.3e}  EVM={r.stats['evm_pct']:.2f} %")
    return {"link": r, "taps": taps}


# ---------------------------------------------------------------------------
# Comparacion A: GRC como transmisor + canal
# ---------------------------------------------------------------------------


def comparar_transmisor(p, ref) -> pd.DataFrame | None:
    if not GRC_TX.exists():
        print(f"  [A] {GRC_TX.name} no encontrado: ejecuta grc/tx_qpsk_canal.grc")
        return None
    grc_tx = np.fromfile(GRC_TX, dtype=np.complex64).astype(complex)
    py_tx = ref["link"].tx_signal
    rx_pairs = [("Python", py_tx, ref["link"].rx_signal)]
    if GRC_RX.exists():
        rx_pairs.append(("GNU Radio", grc_tx,
                         np.fromfile(GRC_RX, dtype=np.complex64).astype(complex)))
    else:
        rx_pairs.append(("GNU Radio", grc_tx, None))

    rows = []
    for nombre, tx, rx_sig in rx_pairs:
        # SNR estimada de forma ciega sobre la senal recibida: evita tener que
        # calibrar la correspondencia entre `noise_voltage` de GNU Radio y Eb/N0.
        snr = np.nan
        if rx_sig is not None:
            n = min(rx_sig.size, 200000)
            snr = metrics.estimate_snr_m2m4(rx_sig[:n])
        rows.append({
            "herramienta": nombre, "muestras": int(tx.size),
            "potencia_media": float(np.mean(np.abs(tx) ** 2)),
            "papr_db": float(10 * np.log10(np.max(np.abs(tx) ** 2) /
                                           np.mean(np.abs(tx) ** 2))),
            "bw_99_khz": metrics.occupied_bandwidth(tx, p.fs) / 1e3,
            "snr_estimada_db": snr,
        })
    df = pd.DataFrame(rows)
    print("\n  [A] Transmisor: Python vs GNU Radio")
    for _, r in df.iterrows():
        print(f"      {r['herramienta']:10s} B99={r['bw_99_khz']:7.2f} kHz  "
              f"PAPR={r['papr_db']:5.2f} dB  SNR(M2M4)={r['snr_estimada_db']:6.2f} dB")
    print(f"      Referencia teorica B = Rs(1+beta) = {p.bw/1e3:.2f} kHz")
    return df


# ---------------------------------------------------------------------------
# Comparacion B: GRC como receptor
# ---------------------------------------------------------------------------


def comparar_receptor(p, ref) -> dict | None:
    if not GRC_SYM.exists():
        print(f"  [B] {GRC_SYM.name} no encontrado: ejecuta grc/rx_qpsk_desde_python.grc")
        return None
    sym = np.fromfile(GRC_SYM, dtype=np.complex64).astype(complex)
    frm = ref["link"].frame
    mod = Modulation(p.mod)

    # El receptor de GNU Radio no conoce la estructura de trama: se sincroniza
    # aqui por correlacion con la secuencia de entrenamiento conocida.
    d, corr, _ = sync.fine_frame_sync(sym, frm.training,
                                      search=min(sym.size - frm.n_train, 4000))
    if corr < 0.3:
        print(f"  [B] No se logro sincronizar con la trama (corr={corr:.3f}). "
              "Revisa que el flowgraph haya procesado la senal completa.")
        return None
    cuerpo = sym[d: d + frm.n_train + frm.n_payload]

    # ganancia/fase: el lazo de Costas deja una ambiguedad de fase de k*90 grados
    a = np.vdot(frm.training, cuerpo[: frm.n_train]) / frm.n_train
    cuerpo = cuerpo / (a + 1e-12)
    payload = cuerpo[frm.n_train:][: frm.n_payload]
    bits = mod.demodulate(payload)
    ber = metrics.bit_error_rate(frm.bits, bits)
    evm = metrics.evm_percent(payload, frm.payload)

    ber_py = float(np.load(PY_REF)["ber_python"])
    evm_py = float(np.load(PY_REF)["evm_python"])
    print("\n  [B] Receptor: Python vs GNU Radio (misma forma de onda y canal)")
    print(f"      Python    : BER={ber_py:.3e}  EVM={evm_py:.2f} %")
    print(f"      GNU Radio : BER={ber.rate:.3e}  EVM={evm:.2f} %  (corr sync={corr:.3f})")
    return {"payload": payload, "ber": ber.rate, "evm": evm,
            "ber_py": ber_py, "evm_py": evm_py, "corr": corr}


# ---------------------------------------------------------------------------


def main(solo_export: bool = False):
    banner("VALIDACION CRUZADA - Python vs GNU Radio Companion")
    plots.setup()
    p = BASE
    print(f"  {p.summary()}")
    print(f"  Experimento reproducido: Experimento 2 (ISI), perfil '{PERFIL}', "
          f"Eb/N0 = {EBN0:.0f} dB\n")

    ref = exportar(p)
    if solo_export:
        return

    df_tx = comparar_transmisor(p, ref)
    res_rx = comparar_receptor(p, ref)

    filas = []
    if df_tx is not None:
        save_table(df_tx, "exp6_transmisor_python_vs_grc")
        filas += df_tx.to_dict("records")
    if res_rx is not None:
        filas.append({"herramienta": "Python (receptor)", "ber": res_rx["ber_py"],
                      "evm_pct": res_rx["evm_py"]})
        filas.append({"herramienta": "GNU Radio (receptor)", "ber": res_rx["ber"],
                      "evm_pct": res_rx["evm"]})
    if filas:
        save_table(pd.DataFrame(filas), "exp6_validacion_cruzada")

    # ------------------------------------------------------------- figura
    n_paneles = 1 + (df_tx is not None) + (res_rx is not None)
    fig, axes = plt.subplots(1, max(n_paneles, 2), figsize=(5 * max(n_paneles, 2), 3.9),
                             constrained_layout=True)
    axes = np.atleast_1d(axes)
    i = 0

    plots.psd(axes[i], ref["link"].tx_signal, p.fs, "Python", rs=p.rs, beta=p.beta,
              color="#1f77b4")
    if GRC_TX.exists():
        plots.psd(axes[i], np.fromfile(GRC_TX, dtype=np.complex64).astype(complex),
                  p.fs, "GNU Radio", color="#d62728")
    axes[i].set_title("PSD transmitida"); axes[i].legend(fontsize=7)
    i += 1

    plots.constellation(axes[i], ref["link"].payload_rx,
                        f"Receptor Python (RLS)\nBER={ref['link'].stats['ber']:.2e}",
                        mod=ref["link"].frame.mod)
    i += 1

    if res_rx is not None and i < axes.size:
        plots.constellation(axes[i], res_rx["payload"],
                            f"Receptor GNU Radio (LMS-DD)\nBER={res_rx['ber']:.2e}",
                            mod=ref["link"].frame.mod, color="#d62728")
        i += 1

    fig.suptitle("Validacion cruzada - Experimento 2 reproducido en GNU Radio")
    plots.save_fig(fig, "exp6_validacion_grc")

    if df_tx is None and res_rx is None:
        print("\n  No hay salidas de GNU Radio todavia. Pasos a seguir:")
        print("    1. Abre grc/tx_qpsk_canal.grc en GNU Radio Companion.")
        print("    2. Pega los taps de grc/io/ch_taps_para_grc.txt en la variable ch_taps.")
        print("    3. Ejecuta el flowgraph (genera grc/io/grc_*.cf32).")
        print("    4. Abre grc/rx_qpsk_desde_python.grc y ejecutalo.")
        print("    5. Vuelve a lanzar este script.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", action="store_true",
                    help="solo exportar los ficheros de intercambio")
    main(ap.parse_args().export)

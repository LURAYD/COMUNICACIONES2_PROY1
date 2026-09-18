"""Experimento 2 - Efecto de la interferencia intersimbolica.

Se compara el enlace antes y despues de introducir el canal multitrayectoria
(Escenario A vs Escenario B) mediante:
  * constelacion recibida,
  * diagrama de ojo (a la salida del filtro adaptado, sobremuestreado),
  * densidad espectral de potencia,
  * respuesta en frecuencia del canal,
  * BER.

La lectura fisica que se busca: el canal multitrayectoria no atenua potencia
(los perfiles estan normalizados a energia unitaria) sino que introduce nulos
selectivos en frecuencia. Esos nulos cierran el ojo y dispersan la constelacion
aunque la relacion senal-ruido media no cambie, de modo que la degradacion de
BER es atribuible exclusivamente a la ISI.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from _common import BASE, banner, plots, save_table
from comm2 import ReceiverConfig, EqualizerConfig, run_link, scenarios, metrics
from comm2.channel import PROFILES

EBN0 = 14.0
PERFILES = ["flat", "mild", "moderate", "severe"]


def eye_window(r, p, n_sym: int = 400):
    """Tramo del filtro adaptado ya corregido en frecuencia y alineado.

    Se toma una ventana corta a partir del inicio de la rafaga: sobre la trama
    completa el residuo de frecuencia (unos pocos Hz) acumula varios radianes y
    cerraria el ojo artificialmente.
    """
    mf = r.sync_info["mf_sync"]
    off = 16 * p.sps                       # retroceso aplicado en run_link
    return mf[off: off + n_sym * p.sps]


def main() -> pd.DataFrame:
    banner("EXPERIMENTO 2 - Efecto de la ISI (Escenario A vs Escenario B)")
    plots.setup()
    p = BASE
    rx = ReceiverConfig(eq=EqualizerConfig(kind="none"))

    # ------------------------------------------------- barrido de severidad
    rows, results = [], {}
    for name in PERFILES:
        prof = PROFILES[name]
        ch = (scenarios.scenario_a(p, EBN0) if name == "flat"
              else scenarios.scenario_b(p, EBN0, profile=name))
        r = run_link(p, ch, rx)
        results[name] = r
        eye = metrics.eye_opening(r.sym_post_eq, sps=1)
        rows.append({
            "perfil": name, "descripcion": prof.name,
            "retardos_T": str(prof.delays_sym), "ganancias_dB": str(prof.gains_db),
            "tau_rms_T": prof.delay_spread_sym,
            "ebn0_db": EBN0, "ber": r.stats["ber"], "ser": r.stats["ser"],
            "evm_pct": r.stats["evm_pct"],
            "mse_db": 10 * np.log10(r.stats["mse"] + 1e-15),
            "apertura_ojo": eye["opening"], "jitter_rel": eye["jitter_std"],
            "bw_ocupado_khz": metrics.occupied_bandwidth(r.tx_signal, p.fs) / 1e3,
        })
        print(f"  {name:9s} tau_rms={prof.delay_spread_sym:5.3f} T  "
              f"BER={r.stats['ber']:.3e}  EVM={r.stats['evm_pct']:5.1f}%  "
              f"ojo={eye['opening']:.3f}")
    df = pd.DataFrame(rows)
    save_table(df, "exp2_isi")

    # ------------------------------------------------------ figura principal
    a, b = results["flat"], results["moderate"]
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.6), constrained_layout=True)

    plots.constellation(axes[0, 0], a.payload_rx, "A: AWGN - constelacion",
                        mod=a.frame.mod)
    plots.constellation(axes[1, 0], b.payload_rx, "B: multipath - constelacion",
                        mod=b.frame.mod, color="#d62728")

    ea, eb_ = eye_window(a, p), eye_window(b, p)
    plots.eye(axes[0, 1], ea, p.sps, title="A: AWGN - diagrama de ojo")
    plots.eye(axes[1, 1], eb_, p.sps, title="B: multipath - diagrama de ojo")
    lim = max(np.max(np.abs(ea.real)), np.max(np.abs(eb_.real))) * 1.1
    axes[0, 1].set_ylim(-lim, lim); axes[1, 1].set_ylim(-lim, lim)

    ax = axes[0, 2]
    plots.psd(ax, a.tx_signal, p.fs, "TX (RRC)", rs=p.rs, beta=p.beta, color="k")
    plots.psd(ax, b.rx_signal, p.fs, "RX tras multipath", color="#d62728")
    ax.set_title("Densidad espectral de potencia"); ax.legend(fontsize=7)

    ax = axes[1, 2]
    for name, color in zip(PERFILES[1:], ["#2ca02c", "#d62728", "#9467bd"]):
        taps = PROFILES[name].taps(p.sps)
        nfft = 2048
        H = np.fft.fftshift(np.fft.fft(taps, nfft))
        f = np.fft.fftshift(np.fft.fftfreq(nfft, d=1 / p.fs))
        mag = 20 * np.log10(np.abs(H) + 1e-12)
        ax.plot(f / 1e3, mag, color=color, label=PROFILES[name].name)
    ax.set_xlim(-p.rs * 0.75 / 1e3, p.rs * 0.75 / 1e3); ax.set_ylim(-30, 10)
    ax.set_xlabel("Frecuencia [kHz]"); ax.set_ylabel("$|H(f)|$ [dB]")
    ax.set_title("Respuesta del canal: nulos selectivos"); ax.legend(fontsize=7)

    fig.suptitle(f"Experimento 2 - Efecto de la ISI (QPSK, $E_b/N_0$ = {EBN0:.0f} dB)")
    plots.save_fig(fig, "exp2_isi_panorama")

    # -------------------------------------------- ojo por severidad de canal
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.4), sharey=True,
                             constrained_layout=True)
    for ax, name in zip(axes, PERFILES):
        plots.eye(ax, eye_window(results[name], p), p.sps, n_traces=250,
                  title=f"{PROFILES[name].name}\nBER={results[name].stats['ber']:.2e}")
    fig.suptitle("Experimento 2 - Cierre del ojo con la dispersion del canal")
    plots.save_fig(fig, "exp2_ojo_por_perfil")
    return df


if __name__ == "__main__":
    main()

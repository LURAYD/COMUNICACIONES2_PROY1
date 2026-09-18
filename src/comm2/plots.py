"""Graficas normalizadas para el informe.

Todas las funciones reciben un `ax` de Matplotlib para poder componer figuras
de varios paneles, y `save_fig` escribe en results/figures con el mismo
formato (300 dpi, fondo blanco) para todo el informe.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt              # noqa: E402

from . import metrics                         # noqa: E402

FIG_DIR = Path(__file__).resolve().parents[2] / "results" / "figures"
DATA_DIR = Path(__file__).resolve().parents[2] / "results" / "data"

COLORS = {
    "none": "#b00020", "lms": "#1f77b4", "rls": "#2ca02c",
    "zf": "#ff7f0e", "mmse": "#9467bd", "cma": "#8c564b",
    "teoria": "#333333",
}


def setup(style: str = "report") -> None:
    plt.rcParams.update({
        "figure.dpi": 110, "savefig.dpi": 300, "savefig.bbox": "tight",
        "font.size": 9, "axes.grid": True, "grid.alpha": 0.3,
        "axes.titlesize": 10, "legend.fontsize": 8,
        "figure.facecolor": "white", "axes.facecolor": "white",
        "lines.linewidth": 1.4, "lines.markersize": 4,
    })


def save_fig(fig, name: str, subdir: str = "") -> Path:
    d = FIG_DIR / subdir if subdir else FIG_DIR
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}.png"
    fig.savefig(path)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Constelacion
# ---------------------------------------------------------------------------


def constellation(ax, sym: np.ndarray, title: str = "", mod=None,
                  n_max: int = 4000, color: str = "#1f77b4", alpha: float = 0.25):
    s = sym[:n_max]
    ax.plot(s.real, s.imag, ".", ms=2, alpha=alpha, color=color, rasterized=True)
    if mod is not None:
        c = mod.constellation
        ax.plot(c.real, c.imag, "x", color="k", ms=7, mew=1.4, label="ideal")
    lim = max(1.8, 1.15 * np.max(np.abs(s)) if s.size else 1.8)
    lim = min(lim, 4.0)
    ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim)
    ax.set_aspect("equal")
    ax.set_xlabel("En fase (I)"); ax.set_ylabel("Cuadratura (Q)")
    ax.axhline(0, color="0.8", lw=0.6); ax.axvline(0, color="0.8", lw=0.6)
    if title:
        ax.set_title(title)
    return ax


# ---------------------------------------------------------------------------
# Diagrama de ojo
# ---------------------------------------------------------------------------


def eye(ax, x: np.ndarray, sps: int, n_traces: int = 250, span: int = 2,
        offset: int | None = None, component: str = "I", title: str = ""):
    """Diagrama de ojo. Con `offset=None` se centra automaticamente el instante
    optimo de muestreo en t/T = 0 (si no, el ojo aparece desplazado y cuesta
    leer la apertura)."""
    if offset is None:
        best = metrics.best_sampling_phase(x, sps)
        offset = int((best - span * sps // 2) % sps)
    t, seg = metrics.eye_data(x, sps, n_traces, span, offset)
    if seg.size == 0:
        return ax
    d = seg.real if component.upper() == "I" else seg.imag
    for row in d:
        ax.plot(t, row, color="#1f77b4", alpha=0.08, lw=0.8)
    ax.set_xlabel("t / T"); ax.set_ylabel(f"Amplitud ({component})")
    ax.axvline(0, color="r", ls="--", lw=0.8, alpha=0.7)
    if title:
        ax.set_title(title)
    return ax


# ---------------------------------------------------------------------------
# Espectro
# ---------------------------------------------------------------------------


def psd(ax, x: np.ndarray, fs: float, label: str = "", rs: float | None = None,
        beta: float | None = None, **kw):
    f, p = metrics.psd(x, fs)
    ax.plot(f / 1e3, p - np.max(p), label=label, **kw)
    if rs is not None and beta is not None:
        b = rs * (1 + beta) / 2
        ax.axvline(b / 1e3, color="r", ls=":", lw=1)
        ax.axvline(-b / 1e3, color="r", ls=":", lw=1,
                   label=f"$\\pm R_s(1+\\beta)/2$ = {b/1e3:.0f} kHz")
    ax.set_xlabel("Frecuencia [kHz]"); ax.set_ylabel("PSD normalizada [dB/Hz]")
    ax.set_ylim(-80, 5)
    return ax


# ---------------------------------------------------------------------------
# Curvas BER
# ---------------------------------------------------------------------------


def ber_with_floor(ax, x, ber, n_bits: float, label: str = "", color=None,
                   marker="o", ls="-", floor_marker="o"):
    """Dibuja una curva de BER señalando el suelo de resolucion del Monte Carlo.

    Descartar sin mas los puntos con cero errores (lo natural en escala
    logaritmica) borra de la grafica justamente al metodo que mejor funciona: el
    RLS desaparece de los paneles donde no comete ningun error. Aqui esos puntos
    se dibujan en el suelo 0.5/n_bits con marcador hueco, que es la lectura
    honesta: "por debajo de lo que esta simulacion puede medir".
    """
    x = np.asarray(x, dtype=float)
    ber = np.asarray(ber, dtype=float)
    floor = 0.5 / max(n_bits, 1.0)
    y = np.where((ber <= 0) | ~np.isfinite(ber), floor, ber)
    cero = (ber <= 0) | ~np.isfinite(ber)
    ax.plot(x, y, ls, color=color, label=label, zorder=3)
    if (~cero).any():
        ax.plot(x[~cero], y[~cero], marker, color=color, ms=4.5, zorder=4)
    if cero.any():
        ax.plot(x[cero], y[cero], floor_marker, color=color, ms=5.5, mfc="white",
                mew=1.3, zorder=4)
    ax.axhline(floor, color="0.75", ls=":", lw=0.9, zorder=1)
    return floor


def ber_curve(ax, ebn0_db, ber, label: str = "", theory=None, color=None,
              marker="o", ls="-", ci=None):
    ber = np.asarray(ber, dtype=float)
    b = np.where(ber <= 0, np.nan, ber)
    ax.semilogy(ebn0_db, b, marker=marker, ls=ls, label=label, color=color)
    if ci is not None:
        lo, hi = np.asarray(ci[0]), np.asarray(ci[1])
        ax.fill_between(ebn0_db, np.where(lo <= 0, 1e-12, lo), hi, alpha=0.15,
                        color=color, lw=0)
    if theory is not None:
        ax.semilogy(ebn0_db, theory, "k--", lw=1.1, label="teorica (AWGN)")
    ax.set_xlabel("$E_b/N_0$ [dB]"); ax.set_ylabel("BER")
    ax.set_ylim(1e-6, 1)
    ax.grid(True, which="both", alpha=0.3)
    return ax


# ---------------------------------------------------------------------------
# Ecualizador
# ---------------------------------------------------------------------------


def learning_curve(ax, eq_result, label: str = "", color=None, n_train: int | None = None):
    lc = eq_result.learning_curve
    ax.plot(np.arange(lc.size), lc, label=label or eq_result.kind.upper(),
            color=color or COLORS.get(eq_result.kind))
    if n_train:
        ax.axvline(n_train, color="0.5", ls="--", lw=0.9)
    ax.set_xlabel("Simbolo"); ax.set_ylabel("MSE instantaneo [dB]")
    return ax


def tap_stem(ax, w: np.ndarray, title: str = ""):
    n = np.arange(w.size)
    ax.stem(n, np.abs(w), basefmt=" ")
    ax.set_xlabel("Tap"); ax.set_ylabel("|w|")
    if title:
        ax.set_title(title)
    return ax


def channel_response(ax, taps: np.ndarray, sps: int, fs: float, title: str = ""):
    """Respuesta en frecuencia del canal (|H(f)| normalizada)."""
    nfft = 2048
    H = np.fft.fftshift(np.fft.fft(taps, nfft))
    f = np.fft.fftshift(np.fft.fftfreq(nfft, d=1 / fs))
    mag = 20 * np.log10(np.abs(H) + 1e-12)
    ax.plot(f / 1e3, mag - np.max(mag))
    ax.set_xlabel("Frecuencia [kHz]"); ax.set_ylabel("|H(f)| [dB]")
    ax.set_xlim(-fs / sps * 0.75 / 1e3, fs / sps * 0.75 / 1e3)
    if title:
        ax.set_title(title)
    return ax

"""Modelos de canal (Seccion 7 de la guia).

Convenio de ruido
-----------------
La constelacion tiene energia media unitaria (Es = 1) y el RRC energia
unitaria, de modo que tras el filtro adaptado y el muestreo en el instante
optimo la muestra util vale a_k y el ruido tiene varianza sigma^2. Por tanto

    Es/N0 = 1 / sigma^2,      sigma^2 = 1 / (k * Eb/N0)

independientemente del sobremuestreo. Los canales multitrayectoria se
normalizan a energia unitaria (sum |g|^2 = 1) para que el multipath
introduzca ISI y desvanecimiento selectivo *sin* cambiar la relacion
senal-ruido media: asi la degradacion observada es atribuible unicamente a
la distorsion, no a una perdida de potencia.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
from scipy.interpolate import CubicSpline

from .pulse import frac_delay_taps


# ---------------------------------------------------------------------------
# AWGN
# ---------------------------------------------------------------------------


def noise_sigma2(ebn0_db: float, bits_per_symbol: int, es: float = 1.0) -> float:
    """Varianza de ruido complejo (potencia total) para un Eb/N0 dado."""
    ebn0 = 10 ** (ebn0_db / 10.0)
    return es / (bits_per_symbol * ebn0)


def add_awgn(x: np.ndarray, ebn0_db: float, bits_per_symbol: int,
             rng: np.random.Generator, es: float = 1.0) -> np.ndarray:
    """Suma ruido blanco gaussiano complejo circularmente simetrico."""
    sigma2 = noise_sigma2(ebn0_db, bits_per_symbol, es)
    n = np.sqrt(sigma2 / 2) * (rng.standard_normal(x.size) + 1j * rng.standard_normal(x.size))
    return x + n


def snr_db_from_ebn0(ebn0_db: float, bits_per_symbol: int, beta: float) -> float:
    """SNR en el ancho de banda ocupado B = Rs(1+beta): SNR = Es/N0 / (1+beta)."""
    return ebn0_db + 10 * np.log10(bits_per_symbol) - 10 * np.log10(1 + beta)


# ---------------------------------------------------------------------------
# Multitrayectoria determinista (canal FIR)
# ---------------------------------------------------------------------------


@dataclass
class MultipathProfile:
    """Perfil retardo-potencia. Los retardos se dan en periodos de simbolo."""

    name: str
    delays_sym: tuple                # retardos [T]
    gains_db: tuple                  # ganancias relativas [dB]
    phases_rad: tuple = ()           # fases de cada trayecto [rad]
    normalize: bool = True

    def __post_init__(self):
        if not self.phases_rad:
            self.phases_rad = tuple(0.0 for _ in self.delays_sym)
        n = len(self.delays_sym)
        assert len(self.gains_db) == n and len(self.phases_rad) == n

    @property
    def delay_spread_sym(self) -> float:
        """Dispersion de retardo RMS en periodos de simbolo."""
        p = 10 ** (np.asarray(self.gains_db) / 10.0)
        p = p / p.sum()
        d = np.asarray(self.delays_sym, dtype=float)
        mean = np.sum(p * d)
        return float(np.sqrt(np.sum(p * (d - mean) ** 2)))

    def taps(self, sps: int, n_taps_interp: int = 41) -> np.ndarray:
        """Respuesta al impulso del canal a la tasa de muestreo."""
        amps = 10 ** (np.asarray(self.gains_db) / 20.0) * np.exp(1j * np.asarray(self.phases_rad))
        delays_smp = np.asarray(self.delays_sym, dtype=float) * sps
        half = (n_taps_interp - 1) // 2
        # Se desplaza todo el perfil `half` muestras para que ningun interpolador
        # quede truncado; ese retardo comun lo absorbe el sincronizador.
        max_d = int(np.ceil(delays_smp.max())) + n_taps_interp
        g = np.zeros(max_d + 1, dtype=complex)
        for a, d in zip(amps, delays_smp):
            i0 = int(np.floor(d))
            h = frac_delay_taps(d - i0, n_taps_interp)
            idx = np.arange(n_taps_interp) + i0
            g[idx] += a * h
        if self.normalize:
            g = g / np.sqrt(np.sum(np.abs(g) ** 2))
        return g

    def describe(self, sps: int) -> str:
        g = self.taps(sps)
        return (f"{self.name}: retardos={self.delays_sym} T, ganancias={self.gains_db} dB, "
                f"tau_rms={self.delay_spread_sym:.3f} T, L={g.size} taps")


# Perfiles predefinidos (justificados en docs/parametros.md)
PROFILES = {
    "flat": MultipathProfile("Plano (sin eco)", (0.0,), (0.0,)),
    "mild": MultipathProfile("Leve", (0.0, 0.5, 1.2), (0.0, -8.0, -14.0),
                             (0.0, 1.1, -2.3)),
    "moderate": MultipathProfile("Moderado", (0.0, 0.7, 1.5, 2.4),
                                 (0.0, -4.0, -8.5, -12.0), (0.0, 2.1, -1.4, 0.6)),
    "severe": MultipathProfile("Severo (eco casi coherente)", (0.0, 1.0, 2.3, 3.6),
                               (0.0, -1.5, -4.0, -7.0), (0.0, 2.6, 1.2, -0.9)),
}


def apply_fir_channel(x: np.ndarray, taps: np.ndarray) -> np.ndarray:
    """Convolucion con el canal FIR (mode='full': conserva la cola del eco)."""
    return np.convolve(x, taps, mode="full")


# ---------------------------------------------------------------------------
# Desvanecimiento Rayleigh variable en el tiempo
# ---------------------------------------------------------------------------


def jakes_taps(n_samples: int, n_paths: int, fd_norm: float,
               rng: np.random.Generator) -> np.ndarray:
    """Coeficientes Rayleigh correlacionados con espectro Doppler de Jakes.

    fd_norm = fD / fs (Doppler maximo normalizado). Se genera ruido blanco
    complejo y se conforma en frecuencia con sqrt(S_Jakes(f)).
    """
    if fd_norm <= 0:
        return (rng.standard_normal((n_paths, 1)) + 1j * rng.standard_normal((n_paths, 1))) \
            / np.sqrt(2) * np.ones((1, n_samples))
    nfft = int(2 ** np.ceil(np.log2(max(n_samples, 1024))))
    f = np.fft.fftfreq(nfft)
    mask = np.abs(f) < fd_norm
    s = np.zeros(nfft)
    s[mask] = 1.0 / (np.pi * fd_norm * np.sqrt(1 - (f[mask] / fd_norm) ** 2))
    s[np.isinf(s)] = 0.0
    s = np.sqrt(s)
    out = np.zeros((n_paths, n_samples), dtype=complex)
    for i in range(n_paths):
        w = (rng.standard_normal(nfft) + 1j * rng.standard_normal(nfft)) / np.sqrt(2)
        h = np.fft.ifft(np.fft.fft(w) * s)
        h = h / np.sqrt(np.mean(np.abs(h) ** 2))       # potencia unitaria por trayecto
        out[i] = h[:n_samples]
    return out


def apply_rayleigh(x: np.ndarray, profile: MultipathProfile, sps: int,
                   fd_norm: float, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Canal multitrayectoria con desvanecimiento Rayleigh por trayecto.

    Devuelve (y, ganancias) donde ganancias[i, n] es el coeficiente complejo
    del trayecto i en la muestra n (util para graficar el fading).
    """
    amps = 10 ** (np.asarray(profile.gains_db) / 20.0)
    amps = amps / np.sqrt(np.sum(amps ** 2))
    delays_smp = np.asarray(profile.delays_sym) * sps
    n = x.size
    fading = jakes_taps(n, len(amps), fd_norm, rng)
    y = np.zeros(n + int(np.ceil(delays_smp.max())) + 41, dtype=complex)
    for i, (a, d) in enumerate(zip(amps, delays_smp)):
        xi = x * (a * fading[i])
        i0 = int(np.floor(d))
        h = frac_delay_taps(d - i0, 41)
        yi = np.convolve(xi, h, mode="full")
        start = i0
        y[start:start + yi.size] += yi
    return y, fading


# ---------------------------------------------------------------------------
# Perturbaciones adicionales
# ---------------------------------------------------------------------------


def apply_cfo(x: np.ndarray, f_off_hz: float, fs: float, phase0: float = 0.0) -> np.ndarray:
    """Offset de frecuencia y fase de portadora: multiplicacion por e^{j(2 pi f n/fs + phi)}."""
    n = np.arange(x.size)
    return x * np.exp(1j * (2 * np.pi * f_off_hz * n / fs + phase0))


def apply_phase_noise(x: np.ndarray, linewidth_hz: float, fs: float,
                      rng: np.random.Generator) -> np.ndarray:
    """Ruido de fase de Wiener (paseo aleatorio) con ancho de linea dado."""
    var = 2 * np.pi * linewidth_hz / fs
    phi = np.cumsum(np.sqrt(var) * rng.standard_normal(x.size))
    return x * np.exp(1j * phi)


def apply_clock_offset(x: np.ndarray, ppm: float, frac_delay: float = 0.0) -> np.ndarray:
    """Error de temporizacion: retardo fraccional fijo + deriva de reloj (ppm).

    Se remuestrea sobre una base temporal t' = (1 + ppm*1e-6) * n + frac_delay
    mediante interpolacion spline cubica.
    """
    n = np.arange(x.size)
    if np.isclose(ppm, 0.0) and np.isclose(frac_delay, 0.0):
        return x.copy()
    t = (1.0 + ppm * 1e-6) * n + frac_delay
    t = t[t <= n[-1]]
    csr = CubicSpline(n, x.real)
    csi = CubicSpline(n, x.imag)
    return csr(t) + 1j * csi(t)


# ---------------------------------------------------------------------------
# Escenarios
# ---------------------------------------------------------------------------


@dataclass
class ChannelConfig:
    """Configuracion completa de un escenario de canal."""

    name: str = "A"
    profile: MultipathProfile = field(default_factory=lambda: PROFILES["flat"])
    ebn0_db: float = 10.0
    cfo_hz: float = 0.0
    phase_off_rad: float = 0.0
    timing_frac: float = 0.0        # retardo fraccional [muestras]
    clock_ppm: float = 0.0          # deriva de reloj de muestreo
    rayleigh: bool = False
    fd_hz: float = 0.0              # Doppler maximo si rayleigh=True
    phase_noise_hz: float = 0.0

    def describe(self, sps: int, fs: float) -> str:
        parts = [f"Escenario {self.name}", f"Eb/N0={self.ebn0_db} dB",
                 f"canal={self.profile.name}"]
        if self.cfo_hz:
            parts.append(f"CFO={self.cfo_hz} Hz ({self.cfo_hz/(fs/sps)*100:.2f} % de Rs)")
        if self.phase_off_rad:
            parts.append(f"fase={np.degrees(self.phase_off_rad):.1f} deg")
        if self.timing_frac or self.clock_ppm:
            parts.append(f"temporizacion={self.timing_frac:.2f} muestras, {self.clock_ppm} ppm")
        if self.rayleigh:
            parts.append(f"Rayleigh fD={self.fd_hz} Hz")
        return " | ".join(parts)


def apply_channel(x: np.ndarray, cfg: ChannelConfig, sps: int, fs: float,
                  bits_per_symbol: int, rng: np.random.Generator) -> dict:
    """Aplica el canal completo. Devuelve dict con la senal y metadatos."""
    info: dict = {}

    # 1) Multitrayectoria (determinista o con fading)
    if cfg.rayleigh:
        y, fading = apply_rayleigh(x, cfg.profile, sps, cfg.fd_hz / fs, rng)
        info["fading"] = fading
        info["taps"] = cfg.profile.taps(sps)
    else:
        taps = cfg.profile.taps(sps)
        y = apply_fir_channel(x, taps)
        info["taps"] = taps

    # 2) Error de temporizacion
    if cfg.timing_frac or cfg.clock_ppm:
        y = apply_clock_offset(y, cfg.clock_ppm, cfg.timing_frac)

    # 3) Offset de frecuencia / fase
    if cfg.cfo_hz or cfg.phase_off_rad:
        y = apply_cfo(y, cfg.cfo_hz, fs, cfg.phase_off_rad)

    # 4) Ruido de fase
    if cfg.phase_noise_hz:
        y = apply_phase_noise(y, cfg.phase_noise_hz, fs, rng)

    # 5) AWGN (ultimo: el ruido se agrega en el frontal del receptor)
    y = add_awgn(y, cfg.ebn0_db, bits_per_symbol, rng, es=1.0)

    info["signal"] = y
    info["sigma2"] = noise_sigma2(cfg.ebn0_db, bits_per_symbol)
    return info

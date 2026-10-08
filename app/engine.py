"""Motor de simulacion: hilo trabajador y extraccion de puntos de derivacion.

Dos responsabilidades.

1. **No congelar la interfaz.** Una corrida de `run_link` tarda ~0,18 s. Si se
   ejecutara en el hilo de la GUI, arrastrar un deslizador seria inutilizable.
   El trabajador vive en su propio hilo y el controlador **descarta las
   peticiones obsoletas**: mientras una corrida esta en curso solo se retiene la
   ultima peticion pedida, de modo que al soltar el control siempre se ve el
   estado final y nunca se acumula una cola de corridas que ya no interesan.

2. **Alinear los puntos de derivacion.** Los cinco puntos a tasa de simbolo
   corresponden a los MISMOS simbolos de carga util, indice a indice: el simbolo
   k antes del ecualizador y el simbolo k despues son el mismo simbolo. Eso es
   lo que permite interpolar entre etapas y ver cada simbolo desplazarse hasta
   su posicion corregida, en vez de comparar dos nubes sin relacion.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from typing import Any, Optional

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal, Slot

from comm2 import (EqualizerConfig, ReceiverConfig, SystemParams, metrics,
                   scenarios)
from comm2.channel import PROFILES
from comm2.link import run_link
from comm2.modulation import Modulation


# ---------------------------------------------------------------------------
# Etapas de la cadena
# ---------------------------------------------------------------------------

SYMBOL, WAVE = "symbol", "wave"


@dataclass(frozen=True)
class Stage:
    key: str
    title: str        # nombre de la etapa en la cadena
    sub: str          # que hace, en dos o tres palabras
    kind: str         # SYMBOL (tasa de simbolo) o WAVE (sobremuestreado)
    story: str        # que hay que mirar aqui, para el lector


STAGES: tuple[Stage, ...] = (
    Stage("tx", "Símbolos", "mapeo Gray", SYMBOL,
          "Los símbolos tal como salen del mapeador: la constelación ideal, sin "
          "ruido ni distorsión. Es la referencia contra la que se mide todo lo demás."),
    Stage("rrc", "RRC", "conformación", WAVE,
          "Tras el filtro de raíz de coseno alzado. El espectro ya está limitado a "
          "B = Rs(1+β) y el ojo está abierto, aunque no del todo: la condición de "
          "Nyquist la cumple el coseno alzado completo, y aquí solo va media raíz."),
    Stage("chan", "Canal", "multitrayecto + AWGN", WAVE,
          "Después del canal. Aquí entran los ecos, el ruido, el offset de "
          "frecuencia y el error de temporización. El ojo se cierra y el espectro "
          "muestra los nulos que dejan las multitrayectorias."),
    Stage("mf", "Filtro adaptado", "maximiza SNR", WAVE,
          "Salida del filtro adaptado, ya corregida en frecuencia y recortada al "
          "inicio de la ráfaga. Maximiza la relación señal-ruido en el instante de "
          "decisión, pero no deshace la ISI del canal."),
    Stage("timing", "Temporización", "Gardner", SYMBOL,
          "Un símbolo por cada periodo T, con el instante de muestreo recuperado "
          "por el lazo de Gardner. La nube sigue emborronada: la ISI sigue ahí."),
    Stage("preeq", "Trama", "sincronismo fino", SYMBOL,
          "Trama localizada y ganancia compleja normalizada sobre el entrenamiento. "
          "Este es el borrón de ISI que el ecualizador tiene que deshacer."),
    Stage("posteq", "Ecualizador", "LMS / RLS", SYMBOL,
          "Salida del ecualizador. La ISI está compensada y la nube colapsa hacia "
          "los puntos de la constelación, pero puede quedar girando por el residuo "
          "de frecuencia."),
    Stage("pll", "PLL + decisión", "portadora", SYMBOL,
          "Tras el lazo de fase dirigido por decisión. La constelación queda fija y "
          "alineada: sobre estos símbolos se deciden los bits y se cuenta la BER."),
)

STAGE_BY_KEY = {s.key: s for s in STAGES}


# ---------------------------------------------------------------------------
# Peticion
# ---------------------------------------------------------------------------

@dataclass
class Request:
    """Todo lo que define una corrida. Un diccionario de parametros, nada mas."""

    scenario: str = "C"
    mod: str = "qpsk"
    ebn0_db: float = 12.0
    profile: str = "moderate"
    beta: float = 0.35
    n_payload: int = 4000

    # perturbaciones (escenario C/D)
    cfo_frac_rs: float = 0.003
    phase_deg: float = 37.0
    timing_frac: float = 0.37
    clock_ppm: float = 20.0
    fd_frac_rs: float = 2e-4

    # receptor
    eq_kind: str = "lms"
    n_taps: int = 21
    mu: float = 0.50
    lam: float = 0.995
    n_train: int = 512
    timing_recovery: bool = True
    cfo_correction: bool = True
    phase_pll: bool = True
    matched_filter: bool = True

    # Curva de aprendizaje del metodo contrario (LMS <-> RLS). Cuesta una
    # segunda corrida completa, asi que se desactiva mientras se arrastra un
    # control y se recupera al soltarlo.
    compare: bool = True

    seq: int = 0        # numero de secuencia, para descartar resultados tardios


def build(req: Request):
    """Traduce la peticion a los objetos de configuracion de `comm2`."""
    p = SystemParams(mod=req.mod, beta=req.beta, n_payload=req.n_payload,
                     n_train=req.n_train)
    eq = EqualizerConfig(kind=req.eq_kind, n_taps=req.n_taps, mu=req.mu,
                         lam=req.lam)
    rx = ReceiverConfig(matched_filter=req.matched_filter,
                        timing_recovery=req.timing_recovery,
                        cfo_correction=req.cfo_correction,
                        phase_pll=req.phase_pll, eq=eq)

    s = req.scenario.upper()
    if s == "A":
        chan = scenarios.scenario_a(p, ebn0_db=req.ebn0_db)
    elif s == "B":
        chan = scenarios.scenario_b(p, ebn0_db=req.ebn0_db, profile=req.profile)
    elif s == "D":
        chan = scenarios.scenario_d_fading(p, ebn0_db=req.ebn0_db,
                                           profile=req.profile,
                                           fd_frac_rs=req.fd_frac_rs)
    else:
        chan = scenarios.scenario_c(p, ebn0_db=req.ebn0_db, profile=req.profile,
                                    cfo_frac_rs=req.cfo_frac_rs,
                                    phase_deg=req.phase_deg,
                                    timing_frac=req.timing_frac,
                                    clock_ppm=req.clock_ppm)
    return p, chan, rx


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------

MAX_POINTS = 3000     # simbolos dibujados; mas no anade informacion visible
EYE_TRACES = 320      # trazas del ojo: suficientes para que el fosforo acumule


@dataclass
class Tap:
    """La senal en un punto de derivacion, lista para dibujar."""
    key: str
    kind: str
    pts: Optional[np.ndarray] = None        # constelacion (complejo)
    wave: Optional[np.ndarray] = None       # forma de onda sobremuestreada
    evm: float = float("nan")
    opening: float = float("nan")
    note: str = ""


@dataclass
class SimResult:
    seq: int
    req: Request
    taps: dict[str, Tap]
    stats: dict[str, Any]
    ideal: np.ndarray                  # constelacion de referencia del mapeador
    ref_pts: np.ndarray                # puntos ideales, alineados con las nubes
    learning: np.ndarray               # curva de aprendizaje del ecualizador [dB]
    learning_ref: Optional[np.ndarray] # la del otro metodo, para comparar
    learning_ref_name: str
    n_train: int
    psd: dict[str, tuple[np.ndarray, np.ndarray]]
    locked: bool
    elapsed: float
    theory_ber: float
    eq_flops: int
    eq_conv: int
    mu_track: np.ndarray
    pll_phase: np.ndarray
    channel_taps: np.ndarray
    sps: int
    fs: float
    # Ojo DESPUES del ecualizador: sus coeficientes aplicados a la salida
    # sobremuestreada del filtro adaptado (ver `_equalize_wave`).
    eye_after: Optional[np.ndarray] = None
    opening_after: float = float("nan")


def _sub(n: int) -> np.ndarray:
    """Indices de submuestreo comunes a todas las etapas a tasa de simbolo."""
    if n <= MAX_POINTS:
        return np.arange(n)
    return np.linspace(0, n - 1, MAX_POINTS).astype(int)


PHASE_WIN = 128       # simbolos de la media movil del estimador de fase del ojo


def _align_phase(seg: np.ndarray, sps: int, mod: Modulation) -> np.ndarray:
    """Alinea la fase de portadora de la salida del filtro adaptado, solo para el ojo.

    El ojo traza la componente I. En el filtro adaptado la portadora aun no
    esta corregida en fase (el PLL actua despues, a tasa de simbolo) y el
    residuo de la estimacion gruesa de frecuencia la hace girar unos grados a lo
    largo de la trama: I y Q se mezclan y el ojo aparece cerrado aunque el pulso
    cumpla Nyquist. Se estima la fase a ciegas con la potencia M-esima en el
    instante optimo, suavizada con una media movil para seguir esa deriva, y se
    deshace. No altera la senal que usa el receptor.
    """
    c = mod.constellation
    m = 8 if mod.name == "8psk" else 4
    ref = np.mean(c ** m)
    if abs(ref) < 1e-6 or seg.size < sps * PHASE_WIN:
        return seg
    off = metrics.best_sampling_phase(seg, sps)
    s = seg[off::sps]
    z = np.convolve(s ** m, np.ones(PHASE_WIN) / PHASE_WIN, mode="same")
    ph = np.unwrap(np.angle(z / ref)) / m
    # Si algun punto cae sobre el eje Q (8PSK), su I es 0 y el ojo en I queda
    # cerrado por geometria: se gira media separacion angular para evitarlo.
    if np.min(np.abs(c.real)) < 0.05:
        ph = ph - np.pi / c.size
    t_sym = off + sps * np.arange(s.size)
    phase = np.interp(np.arange(seg.size), t_sym, ph)
    return seg * np.exp(-1j * phase)


def _equalize_wave(x: np.ndarray, w: np.ndarray, ref_tap: int, sps: int) -> np.ndarray:
    """Aplica el ecualizador espaciado a T a la senal sobremuestreada.

    El ecualizador calcula y[n] = sum_j conj(w_j) r[n + d - j] sobre un simbolo
    por periodo. Ese mismo FIR, con un coeficiente cada `sps` muestras, filtra
    la forma de onda continua: en los instantes de muestreo reproduce los
    simbolos ecualizados y entre ellos da la forma de onda real, que es lo que
    permite trazar el ojo despues del ecualizador.
    """
    g = np.zeros((w.size - 1) * sps + 1, dtype=complex)
    g[::sps] = np.conj(w)
    full = np.convolve(x, g)
    lead = ref_tap * sps
    return full[lead: lead + x.size]


def simulate(req: Request) -> SimResult:
    t0 = time.perf_counter()
    p, chan, rx = build(req)
    r = run_link(p, chan, rx)

    mod = Modulation(req.mod)
    frm = r.frame
    n_tr, n_pl = frm.n_train, frm.n_payload

    # --- alineacion de los puntos a tasa de simbolo -------------------------
    # Todos se recortan a la misma region de carga util, de modo que el indice k
    # designa el mismo simbolo en las cinco etapas.
    d_tr = max(int(r.sync_info["fine_start"]) + frm.preamble_len, 0)

    def payload_of(arr: np.ndarray, start: int) -> np.ndarray:
        seg = arr[start: start + n_pl]
        if seg.size < n_pl:
            seg = np.concatenate([seg, np.zeros(n_pl - seg.size, complex)])
        return seg

    ideal = frm.payload[:n_pl]
    sym_taps = {
        "tx":     ideal,
        "timing": payload_of(r.sym_stream, d_tr + n_tr),
        "preeq":  payload_of(r.sym_pre_eq, n_tr),
        "posteq": payload_of(r.eq.y, n_tr),
        "pll":    payload_of(r.sym_post_eq, n_tr),
    }

    idx = _sub(n_pl)
    ref_pts = ideal[idx]

    taps: dict[str, Tap] = {}
    for key, arr in sym_taps.items():
        evm = metrics.evm_percent(arr, ideal) if key != "tx" else 0.0
        op = metrics.eye_opening(arr, sps=1)["opening"]
        taps[key] = Tap(key=key, kind=SYMBOL, pts=arr[idx], evm=evm, opening=op)

    # --- puntos sobremuestreados -------------------------------------------
    sps = p.sps
    eye_after, opening_after = None, float("nan")
    wave_src = {
        "rrc": r.tx_signal,
        "chan": r.rx_signal,
        "mf": r.sync_info.get("mf_sync", r.mf_out),
    }
    for key, w in wave_src.items():
        w = np.asarray(w)
        # El tramo util evita las guardas de ceros de los extremos de la rafaga.
        lo = min(int(0.15 * w.size), w.size - 1)
        hi = max(int(0.85 * w.size), lo + sps * 4)
        seg = w[lo:hi]
        if seg.size < sps * 8:
            seg = w
        if key == "mf":
            # El ojo de despues se calcula sobre el MISMO tramo, antes de
            # alinear la fase: el ecualizador aprendio sobre simbolos
            # normalizados por la ganancia compleja estimada, no sobre `seg`.
            if req.eq_kind != "none" and np.size(r.eq.w) and np.all(np.isfinite(r.eq.w)):
                a = complex(r.sync_info.get("gain_est", 1.0)) or 1.0
                after = _equalize_wave(seg / a, np.asarray(r.eq.w),
                                       int(r.eq.ref_tap), sps)
                eye_after = _align_phase(after, sps, mod)
                opening_after = metrics.eye_opening(eye_after, sps=sps)["opening"]
            seg = _align_phase(seg, sps, mod)
        op = metrics.eye_opening(seg, sps=sps)["opening"]
        off = metrics.best_sampling_phase(seg, sps)
        dec = seg[off::sps]
        # Normalizacion a energia unitaria: sin esto la constelacion del punto de
        # canal se sale de escala y no se puede comparar con la del transmisor.
        rms = np.sqrt(np.mean(np.abs(dec) ** 2)) + 1e-12
        dec = dec / rms
        k = _sub(dec.size)
        taps[key] = Tap(key=key, kind=WAVE, pts=dec[k], wave=seg,
                        evm=float("nan"), opening=op)

    # --- densidad espectral -------------------------------------------------
    psd_d = {}
    for key in ("rrc", "chan"):
        w = wave_src[key]
        n = min(w.size, 60000)
        f, pdb = metrics.psd(w[:n], p.fs, nperseg=1024)
        psd_d[key] = (f / p.rs, pdb - np.max(pdb))   # eje en unidades de Rs, 0 dB al pico

    # --- curva de aprendizaje ----------------------------------------------
    def to_db(curve) -> np.ndarray:
        """`EqResult.learning_curve` YA viene en dB (|e|^2 suavizado, ver
        `equalizers._analyze`). Aqui solo se sanea: en un tramo divergente puede
        aparecer un no-finito, y el suelo en -60 dB mantiene la traza dibujable
        sin inventar un dato que no se midio."""
        if curve is None or not len(curve):
            return np.array([])
        v = np.asarray(curve, float)
        return np.clip(np.nan_to_num(v, nan=-60.0, posinf=30.0, neginf=-60.0),
                       -60.0, 30.0)

    lc_db = to_db(r.eq.learning_curve)

    # Contraste con el metodo alternativo: LMS <-> RLS, que es la comparacion
    # que pide la Seccion 8 de la guia.
    other = {"lms": "rls", "rls": "lms"}.get(req.eq_kind)
    lc_ref, lc_ref_name = None, ""
    if other and req.compare:
        try:
            rx2 = build(replace(req, eq_kind=other))[2]
            r2 = run_link(p, chan, rx2)
            lc_ref = to_db(r2.eq.learning_curve)
            lc_ref_name = other.upper()
            if not lc_ref.size:
                lc_ref = None
        except Exception:
            lc_ref = None

    ebn0 = req.ebn0_db
    try:
        th = float(mod.ber_theory(np.array([ebn0]))[0])
    except Exception:
        th = float("nan")

    return SimResult(
        seq=req.seq, req=req, taps=taps, stats=dict(r.stats), ideal=mod.constellation,
        ref_pts=ref_pts, learning=lc_db, learning_ref=lc_ref,
        learning_ref_name=lc_ref_name, n_train=n_tr, psd=psd_d,
        locked=bool(r.locked), elapsed=time.perf_counter() - t0,
        theory_ber=th, eq_flops=int(r.stats.get("eq_flops", 0)),
        eq_conv=int(r.stats.get("eq_conv", -1)),
        mu_track=np.asarray(r.sync_info.get("mu_track", [])),
        pll_phase=np.asarray(r.sync_info.get("pll_phase", [])),
        channel_taps=np.asarray(r.sync_info.get("channel_taps", [])),
        sps=sps, fs=p.fs, eye_after=eye_after, opening_after=float(opening_after),
    )


# ---------------------------------------------------------------------------
# Comparación canal ideal frente a canal h (vista «ISI y ecualizador»)
# ---------------------------------------------------------------------------

@dataclass
class LinkView:
    """Un enlace de la comparación, reducido a lo que se dibuja."""
    pts: np.ndarray            # constelación de la carga útil, submuestreada
    ber: float
    bits: int
    evm: float
    snr_db: float              # SNR efectiva = 1/EVM²
    isi_db: float              # ISI residual relativa a la señal útil
    noise_db: float            # ruido a la salida relativo a la señal útil
    mse_db: float              # error total medido
    locked: bool


@dataclass
class IsiResult:
    seq: int
    req: Request
    h_text: str                        # el canal h tal como se simuló
    sir_db: float                      # ISI del canal sin ecualizar (teórica)
    peak_distortion: float
    esn0_db: float                     # techo: SNR del canal ideal
    bound_db: float                    # límite de cualquier ecualizador lineal
    eq_name: str                       # "" si el rail tiene «sin ecualizar»
    links: dict                        # (canal, receptor) -> LinkView
    c: np.ndarray                      # canal a tasa de símbolo (medido)
    f: np.ndarray                      # ecualizador (vacío si no hay)
    q: np.ndarray                      # canal * ecualizador
    freq: np.ndarray                   # eje f/Rs
    C_db: np.ndarray
    F_db: np.ndarray
    Q_db: np.ndarray
    noise_gain_db: float
    ideal: np.ndarray
    elapsed: float


def _resp_db(v: np.ndarray, f: np.ndarray) -> np.ndarray:
    if v is None or not np.size(v):
        return np.full(f.size, np.nan)
    H = np.exp(-2j * np.pi * np.outer(f, np.arange(v.size))) @ v
    return 20 * np.log10(np.abs(H) + 1e-9)


_IDEAL_CACHE: dict = {}


def compare_isi(req: Request) -> IsiResult:
    """Cuatro enlaces con los MISMOS datos y el MISMO ruido.

    canal ideal / canal h, cada uno sin ecualizar y con el ecualizador del rail.
    Escenario B con la sincronización de portadora apagada: el B no tiene
    offset de frecuencia ni de fase, y con el ojo cerrado el PLL dirigido por
    decisión desliza 90° (medido: BER 0,587 con h = 0,0.2,1,0,0.8 a 6 dB), lo
    que se confundiría con ISI. Todo pasa por `run_link`, como en el banco.
    """
    from comm2.channel import format_taps, get_profile
    from comm2.link import equalizer_breakdown, symbol_rate_channel
    from comm2.pulse import rrc_filter

    t0 = time.perf_counter()
    base = replace(req, scenario="B", cfo_correction=False, phase_pll=False)
    prof = get_profile(req.profile)
    p = build(base)[0]
    mod = Modulation(req.mod)

    c_th = symbol_rate_channel(rrc_filter(p.beta, p.span, p.sps),
                               prof.taps(p.sps), p.sps, phase="cursor")
    th = metrics.isi_metrics(c_th)
    n_win = max(8, c_th.size + 2)
    esn0 = req.ebn0_db + 10 * np.log10(mod.bits_per_symbol)
    eq = req.eq_kind if req.eq_kind != "none" else ""

    combos = [("ideal", "none"), ("h", "none")]
    if eq:
        combos += [("ideal", eq), ("h", eq)]

    links, bd_h = {}, None
    for canal, rxk in combos:
        sub = replace(base, profile="flat" if canal == "ideal" else req.profile,
                      eq_kind=rxk, seq=0, compare=False)
        # Los enlaces del canal ideal no dependen de h: al cambiar de canal
        # (semilla, h a mano) se reutilizan y solo se recalculan los de h.
        key = repr(sub) if canal == "ideal" else None
        if key is not None and key in _IDEAL_CACHE:
            links[(canal, rxk)] = _IDEAL_CACHE[key]
            continue
        pp, chan, rx = build(sub)
        r = run_link(pp, chan, rx)
        bd = equalizer_breakdown(r, n_win)
        pl = r.payload_rx
        s = r.stats
        links[(canal, rxk)] = LinkView(
            pts=pl[_sub(pl.size)], ber=float(s["ber"]), bits=int(s["ber_bits"]),
            evm=float(s["evm_pct"]), snr_db=float(s["snr_evm_db"]),
            isi_db=float(10 * np.log10(bd["isi_rel"] + 1e-12)),
            noise_db=float(10 * np.log10(bd["noise_rel"] + 1e-12)),
            mse_db=float(10 * np.log10(bd["mse"] + 1e-12)), locked=bool(r.locked))
        if key is not None:
            if len(_IDEAL_CACHE) > 16:
                _IDEAL_CACHE.clear()
            _IDEAL_CACHE[key] = links[(canal, rxk)]
        if canal == "h" and (rxk == eq or (not eq and rxk == "none")):
            bd_h = bd

    fr = np.linspace(-0.5, 0.5, 512)
    f_eq = bd_h["f"] if eq else np.array([])
    q = bd_h["q"] if eq else bd_h["c"]
    if prof.name.startswith(("h =", "aleatorio")):
        h_text = prof.name
    else:
        h_text = f"perfil «{prof.name}»"
    return IsiResult(
        seq=req.seq, req=req, h_text=h_text, sir_db=th["sir_db"],
        peak_distortion=th["peak_distortion"], esn0_db=float(esn0),
        bound_db=metrics.mmse_le_snr_db(c_th, esn0), eq_name=eq.upper(),
        links=links, c=bd_h["c"], f=f_eq, q=q, freq=fr,
        C_db=_resp_db(bd_h["c"], fr), F_db=_resp_db(f_eq, fr), Q_db=_resp_db(q, fr),
        noise_gain_db=bd_h["noise_gain_db"] if eq else 0.0,
        ideal=mod.constellation, elapsed=time.perf_counter() - t0)


# ---------------------------------------------------------------------------
# Trabajador y controlador
# ---------------------------------------------------------------------------

class _Worker(QObject):
    done = Signal(object)
    failed = Signal(int, str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    @Slot(object)
    def work(self, req: Request) -> None:
        try:
            self.done.emit(self._fn(req))
        except Exception as exc:          # noqa: BLE001 - se muestra en la interfaz
            self.failed.emit(req.seq, f"{type(exc).__name__}: {exc}")


class SimController(QObject):
    """Ejecuta en segundo plano y descarta peticiones obsoletas.

    Mientras una corrida esta en curso solo se guarda la ULTIMA peticion
    pendiente: al arrastrar un deslizador se descartan las intermedias y se
    dibuja siempre el estado final, sin acumular cola.
    """

    result = Signal(object)
    error = Signal(str)
    busy = Signal(bool)

    _dispatch = Signal(object)

    def __init__(self, parent=None, fn=None, name: str = "comm2-sim"):
        super().__init__(parent)
        self._seq = 0
        self._running = False
        self._pending: Optional[Request] = None

        self._thread = QThread()
        self._thread.setObjectName(name)
        # `fn` es la función que se ejecuta en el hilo: `simulate` para el
        # banco, `compare_isi` para la vista de ISI. Mismo descarte de
        # peticiones obsoletas para las dos.
        self._worker = _Worker(fn or simulate)
        self._worker.moveToThread(self._thread)
        self._dispatch.connect(self._worker.work)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    def submit(self, req: Request) -> None:
        self._seq += 1
        req.seq = self._seq
        if self._running:
            self._pending = req          # reemplaza la anterior: coalescencia
            return
        self._start(req)

    def _start(self, req: Request) -> None:
        self._running = True
        self.busy.emit(True)
        self._dispatch.emit(req)

    @Slot(object)
    def _on_done(self, res: SimResult) -> None:
        self._running = False
        if res.seq == self._seq:
            self.result.emit(res)        # solo el mas reciente llega a la vista
        self._drain()

    @Slot(int, str)
    def _on_failed(self, seq: int, msg: str) -> None:
        self._running = False
        if seq == self._seq:
            self.error.emit(msg)
        self._drain()

    def _drain(self) -> None:
        if self._pending is not None:
            req, self._pending = self._pending, None
            self._start(req)
        else:
            self.busy.emit(False)

    def shutdown(self) -> None:
        self._thread.quit()
        self._thread.wait(3000)

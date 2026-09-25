"""Cadena completa transmisor -> canal -> receptor.

    bits -> trama -> mapeo -> RRC -> [canal] -> RRC adaptado ->
    Schmidl-Cox -> correccion CFO -> Gardner -> sinc. fina ->
    CFO fino -> ecualizador -> PLL de fase -> decision -> BER

Cada bloque puede desactivarse desde `ReceiverConfig` para las ablaciones que
piden los experimentos 2 y 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import numpy as np

from . import metrics, sync
from .channel import ChannelConfig, apply_channel
from .equalizers import EqResult, equalize
from .frame import Frame, add_guard, build_frame
from .modulation import Modulation
from .params import ReceiverConfig, SystemParams
from .pulse import matched_filter, pulse_shape, rrc_filter


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------


@dataclass
class LinkResult:
    params: SystemParams
    chan: ChannelConfig
    rxcfg: ReceiverConfig
    frame: Frame
    tx_signal: np.ndarray
    rx_signal: np.ndarray
    mf_out: np.ndarray
    sym_stream: np.ndarray            # tras recuperacion de temporizacion
    sym_pre_eq: np.ndarray            # entrenamiento+carga, antes del ecualizador
    sym_post_eq: np.ndarray           # despues del ecualizador (y del PLL)
    payload_rx: np.ndarray            # simbolos de carga util decididos
    bits_rx: np.ndarray
    eq: EqResult
    sync_info: dict
    stats: dict = field(default_factory=dict)
    locked: bool = True

    def report(self) -> str:
        s = self.stats
        return (f"[{self.chan.name}] {self.params.mod.upper()} Eb/N0={self.chan.ebn0_db:4.1f} dB "
                f"eq={self.eq.kind:5s} -> BER={s['ber']:.3e} SER={s['ser']:.3e} "
                f"EVM={s['evm_pct']:5.2f}% MSE={10*np.log10(s['mse']+1e-15):6.2f} dB")


# ---------------------------------------------------------------------------
# Transmisor
# ---------------------------------------------------------------------------


def transmit(p: SystemParams, rng: np.random.Generator | None = None,
             mod_name: str | None = None) -> tuple[np.ndarray, Frame, np.ndarray]:
    """Devuelve (senal transmitida, trama, filtro RRC)."""
    frm = build_frame(p, rng, mod_name)
    h = rrc_filter(p.beta, p.span, p.sps)
    syms = add_guard(frm.symbols, p.guard)
    tx = pulse_shape(syms, h, p.sps)
    return tx, frm, h


# ---------------------------------------------------------------------------
# Auxiliares del receptor
# ---------------------------------------------------------------------------


def coarse_gain_phase(r: np.ndarray, ref: np.ndarray) -> complex:
    """Ganancia compleja optima (1 tap) estimada sobre simbolos conocidos."""
    n = min(r.size, ref.size)
    num = np.vdot(ref[:n], r[:n])
    den = np.vdot(ref[:n], ref[:n])
    return num / (den + 1e-12)


def symbol_rate_channel(h: np.ndarray, g: np.ndarray, sps: int,
                        phase: str = "peak") -> np.ndarray:
    """Canal equivalente a tasa de simbolo: (h * g * h) diezmado.

    phase = 'peak'   diezma en la muestra de mayor modulo (lo que usan ZF/MMSE);
    phase = 'cursor' diezma alineado con el trayecto mas fuerte del canal, que
                     es el instante de Nyquist en el que se engancha Gardner.
    Con ecos asimetricos el pico de |h*g*h| se desplaza respecto al instante de
    Nyquist (h = [0.2, 1, 0, 0.8] lo adelanta una muestra con sps = 8) y 'peak'
    describe una ISI distinta de la que ve el receptor. Con 'cursor' un canal
    espaciado a T devuelve exactamente sus coeficientes normalizados.
    """
    tot = np.convolve(np.convolve(h, g), h)
    if phase == "cursor":
        pk = int(np.argmax(np.abs(g))) + (h.size - 1)
    else:
        pk = int(np.argmax(np.abs(tot)))
    c = tot[pk % sps:: sps]
    # recorta colas despreciables (< -40 dB del pico)
    thr = 10 ** (-40 / 20) * np.max(np.abs(c))
    nz = np.where(np.abs(c) > thr)[0]
    return c[nz[0]: nz[-1] + 1] if nz.size else c


def equalizer_breakdown(r: "LinkResult", n_win: int = 8) -> dict:
    """Reparte el error de salida del ecualizador en ISI residual y ruido.

    c = canal a tasa de simbolo que ve el ecualizador, medido por minimos
    cuadrados sobre la carga util con los simbolos conocidos; f = conj(w) es el
    filtro del ecualizador y q = c * f la respuesta conjunta. Con simbolos de
    energia 1:
        ISI   = sum_{k != 0} |q_k|^2 / |q_0|^2
        ruido = sigma_in^2 * sum |f|^2 / |q_0|^2
    sigma_in^2 es el residuo del ajuste: el ruido que realmente entra al
    ecualizador (sigma^2 del canal no sirve, la cadena aplica ganancias
    intermedias). Sin ecualizador, f = [1] y q = c.
    """
    ref = r.frame.payload
    rx = r.sym_pre_eq[r.frame.n_train:]
    c, s2_in = metrics.estimate_symbol_channel(rx, ref, n_win, n_win)
    f = np.conj(r.eq.w)
    q = np.convolve(f, c)
    q0 = float(np.max(np.abs(q)) ** 2)
    return {
        "c": c, "f": f, "q": q, "sigma2_in": s2_in,
        "isi_rel": float((np.sum(np.abs(q) ** 2) - q0) / q0),
        "noise_rel": float(s2_in * np.sum(np.abs(f) ** 2) / q0),
        "noise_gain_db": float(10 * np.log10(np.sum(np.abs(f) ** 2) + 1e-30)),
        "mse": float(r.stats["mse"]),
    }


# ---------------------------------------------------------------------------
# Enlace completo
# ---------------------------------------------------------------------------


def run_link(p: SystemParams, chan: ChannelConfig, rxcfg: ReceiverConfig | None = None,
             rng: np.random.Generator | None = None,
             mod_name: str | None = None) -> LinkResult:
    rxcfg = rxcfg or ReceiverConfig()
    rng = rng if rng is not None else p.rng()
    mod = Modulation(mod_name or p.mod)

    # ------------------------------------------------------------------ TX
    tx, frm, h = transmit(p, rng, mod_name)

    # --------------------------------------------------------------- canal
    ch = apply_channel(tx, chan, p.sps, p.fs, mod.bits_per_symbol, rng)
    rx = ch["signal"]

    # ------------------------------------------------------- filtro adaptado
    mf = matched_filter(rx, h) if rxcfg.matched_filter else rx.copy()

    info: dict = {"channel_taps": ch["taps"], "sigma2": ch["sigma2"]}

    # ------------------------------------ 1) Schmidl-Cox: rafaga + CFO grueso
    half = p.zc_len * p.sps
    sc = sync.schmidl_cox(mf, half, p.fs)
    info["sc_start"] = sc.start
    info["sc_peak"] = sc.peak_value
    info["cfo_coarse_hz"] = sc.cfo_hz
    info["cfo_true_hz"] = chan.cfo_hz
    info["cfo_max_hz"] = sync.max_cfo_acquisition(half, p.fs)

    y = sync.derotate(mf, sc.cfo_hz, p.fs) if rxcfg.cfo_correction else mf

    # ----------------------------------- 2) Recuperacion de temporizacion
    # Se retrocede 16 simbolos respecto a la estimacion de Schmidl-Cox: a Eb/N0
    # bajo esa estimacion tiene una dispersion de varios simbolos y, si se
    # quedara corta, el preambulo caeria en indices negativos del flujo de
    # simbolos y la sincronizacion de trama seria imposible.
    backoff = 16 * p.sps
    start = max(sc.start - backoff, 2)
    # Salida del filtro adaptado ya corregida en frecuencia y recortada al
    # inicio de la rafaga: es la senal sobre la que tiene sentido dibujar el
    # diagrama de ojo (sobre `mf` en crudo, el residuo de frecuencia hace girar
    # la constelacion a lo largo de la trama y el ojo aparece cerrado aunque no
    # lo este).
    info["mf_sync"] = y[start:]
    info["burst_start"] = start
    if rxcfg.timing_recovery:
        tr = sync.gardner_timing_recovery(y[start:], p.sps, rxcfg.timing_loop_bw)
        sym_stream = tr.symbols
        info["mu_track"] = tr.mu_track
        info["ted_err"] = tr.err_track
    else:
        sym_stream = sync.fixed_downsample(y[start:], p.sps)
        info["mu_track"] = np.zeros(sym_stream.size)
        info["ted_err"] = np.zeros(sym_stream.size)

    # -------------------------------------- 3) Sincronizacion fina de trama
    # Se correlaciona contra la SECUENCIA DE ENTRENAMIENTO, no contra el
    # preambulo, por dos motivos:
    #   (a) el preambulo [ZC ZC] tiene dos mitades identicas y su
    #       autocorrelacion aperiodica presenta un lobulo lateral de altura 0.5
    #       en el desplazamiento +-zc_len; con multitrayectoria ese lobulo puede
    #       superar al pico principal y el receptor engancha 64 simbolos tarde;
    #   (b) la secuencia PN de entrenamiento es aperiodica y cuatro veces mas
    #       larga, con lo que el pico es inequivoco.
    # Ademas, el maximo de correlacion se situa donde mejor casa la respuesta
    # dispersiva del canal, que es justamente la referencia temporal que debe
    # usar el receptor sin ecualizar (si no, su BER seria artificialmente mala).
    search = frm.preamble_len + 4 * backoff // p.sps + 64
    d_tr, corr, corr_curve = sync.fine_frame_sync(sym_stream, frm.training,
                                                  search=search)
    d = d_tr - frm.preamble_len
    info["fine_start"] = d
    info["fine_corr"] = corr
    info["fine_corr_curve"] = corr_curve

    n_body = frm.n_train + frm.n_payload
    d_tr = max(d_tr, 0)
    if sym_stream.size - d_tr < n_body:
        pad = n_body - (sym_stream.size - d_tr)
        sym_stream = np.concatenate([sym_stream, np.zeros(pad, dtype=complex)])
        info["tail_padding"] = int(pad)
    body = sym_stream[d_tr: d_tr + n_body].copy()

    # ------------------------------------------- 4) CFO fino asistido por datos
    if rxcfg.cfo_correction and rxcfg.fine_cfo:
        f_fine = sync.fine_cfo_ml(body[: frm.n_train], frm.training, p.rs)
        # limita la correccion fina a +-1 % de Rs (evita divergencia con SNR bajo)
        f_fine = float(np.clip(f_fine, -0.01 * p.rs, 0.01 * p.rs))
        body = sync.derotate(body, f_fine, p.rs)
        info["cfo_fine_hz"] = f_fine
        info["cfo_residual_hz"] = chan.cfo_hz - (sc.cfo_hz + f_fine)
    else:
        info["cfo_fine_hz"] = 0.0
        info["cfo_residual_hz"] = (chan.cfo_hz - sc.cfo_hz if rxcfg.cfo_correction
                                   else chan.cfo_hz)

    # ----------------------------- 5) Normalizacion de ganancia/fase (1 tap)
    a = coarse_gain_phase(body[: frm.n_train], frm.training)
    body = body / (a + 1e-12)
    info["gain_est"] = a

    # ----------------------------------------------- 6) Ecualizacion
    cfg = rxcfg.eq
    csym = None
    if cfg.kind in ("zf", "mmse"):
        csym = symbol_rate_channel(h, ch["taps"], p.sps)
        info["channel_sym"] = csym
    eq = equalize(body, frm.training, mod, cfg, channel_sym=csym,
                  sigma2=ch["sigma2"])

    # ------------------------------------------- 7) PLL de fase (dirigido por decision)
    if rxcfg.phase_pll:
        # Estimacion del residuo de frecuencia SOBRE LA SALIDA DEL ECUALIZADOR:
        # ahi la ISI ya esta compensada, de modo que el estimador ML asistido por
        # datos alcanza su precision teorica en lugar de quedar sesgado por los
        # terminos cruzados del canal (que es lo que arruinaba la etapa fina
        # aplicada antes de ecualizar, ver ReceiverConfig.fine_cfo).
        f_res = sync.fine_cfo_ml(eq.y[: frm.n_train], frm.training, p.rs)
        f_res = float(np.clip(f_res, -0.01 * p.rs, 0.01 * p.rs))
        info["cfo_post_eq_hz"] = f_res
        pll = sync.dd_phase_pll(eq.y, mod, rxcfg.phase_loop_bw,
                                ref=frm.training,
                                init_freq=2 * np.pi * f_res / p.rs)
        y_sym = pll.symbols
        info["pll_phase"] = pll.phase
    else:
        y_sym = eq.y
        info["cfo_post_eq_hz"] = 0.0
        info["pll_phase"] = np.zeros(eq.y.size)

    # ------------------------------------------------ 8) Decision y BER
    payload_rx = y_sym[frm.n_train:][: frm.n_payload]
    bits_rx = mod.demodulate(payload_rx)
    stats = metrics.summarize(mod, payload_rx, frm.payload, frm.bits, bits_rx, p.beta)
    stats["eq_kind"] = eq.kind
    stats["eq_mse_db"] = eq.steady_mse_db
    stats["eq_conv"] = eq.convergence_symbols
    stats["eq_flops"] = eq.flops_per_symbol["real_mults"]
    stats["ebn0_db"] = chan.ebn0_db
    stats["scenario"] = chan.name
    stats["mod"] = mod.name
    stats["cfo_residual_hz"] = info["cfo_residual_hz"]
    stats["fine_corr"] = corr

    # La multitrayectoria reduce el pico de correlacion; el umbral se fija muy
    # por encima del valor esperado para ruido puro (~1/sqrt(L) = 0.07).
    locked = corr > 0.30 and sc.peak_value > 0.30
    return LinkResult(params=p, chan=chan, rxcfg=rxcfg, frame=frm, tx_signal=tx,
                      rx_signal=rx, mf_out=mf, sym_stream=sym_stream,
                      sym_pre_eq=body, sym_post_eq=y_sym, payload_rx=payload_rx,
                      bits_rx=bits_rx, eq=eq, sync_info=info, stats=stats,
                      locked=locked)


# ---------------------------------------------------------------------------
# Monte Carlo
# ---------------------------------------------------------------------------


def monte_carlo(p: SystemParams, chan_factory, rxcfg: ReceiverConfig,
                n_frames: int = 1, mod_name: str | None = None,
                seed_offset: int = 0, collect: bool = False) -> dict:
    """Promedia varias realizaciones independientes del canal/datos.

    `chan_factory(i)` devuelve el ChannelConfig de la realizacion i (permite
    variar el fading o el ruido entre tramas).
    """
    errs = bits = serr = nsym = 0
    mses, evms, convs, mse_db, corrs = [], [], [], [], []
    last: Optional[LinkResult] = None
    frames = []
    for i in range(n_frames):
        rng = np.random.default_rng(p.seed + 10_000 * (seed_offset + 1) + i)
        chan = chan_factory(i)
        res = run_link(p, chan, rxcfg, rng=rng, mod_name=mod_name)
        s = res.stats
        errs += s["ber_errors"]; bits += s["ber_bits"]
        serr += s["ser_errors"]; nsym += s["ser_symbols"]
        mses.append(s["mse"]); evms.append(s["evm_pct"])
        convs.append(res.eq.convergence_symbols); mse_db.append(res.eq.steady_mse_db)
        corrs.append(s["fine_corr"])
        last = res
        if collect:
            frames.append(res)
    er = metrics.ErrorRate(errs, bits)
    sr = metrics.ErrorRate(serr, nsym)
    out = {
        "ber": er.rate, "ber_errors": errs, "ber_bits": bits,
        "ber_ci_lo": er.ci95[0], "ber_ci_hi": er.ci95[1],
        "ser": sr.rate, "mse": float(np.mean(mses)), "evm_pct": float(np.mean(evms)),
        "eq_conv": float(np.mean(convs)), "eq_mse_db": float(np.mean(mse_db)),
        "fine_corr": float(np.mean(corrs)),
        "n_frames": n_frames, "last": last,
    }
    if collect:
        out["frames"] = frames
    return out

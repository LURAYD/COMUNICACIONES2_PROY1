"""Pruebas de la biblioteca `comm2`.

Se ejecutan con pytest o directamente:

    python tests/test_comm2.py

Cada prueba comprueba una propiedad *teorica* del bloque correspondiente, no un
valor grabado a mano: si alguien cambia una constante y rompe la fisica del
modelo, la prueba falla.
"""

from __future__ import annotations

import numpy as np

from comm2 import (SystemParams, ReceiverConfig, EqualizerConfig, scenarios,
                   run_link, metrics, sync)
from comm2.channel import PROFILES, add_awgn, noise_sigma2
from comm2.equalizers import design_mmse, design_zf, equalize, flop_count
from comm2.frame import build_frame, zadoff_chu
from comm2.modulation import Modulation, available
from comm2.pulse import excess_bandwidth_check, matched_filter, pulse_shape, rrc_filter


# ---------------------------------------------------------------- modulacion
def test_constelaciones_energia_unitaria():
    for name in available():
        c = Modulation(name).constellation
        assert abs(np.mean(np.abs(c) ** 2) - 1.0) < 1e-9, name


def test_mapeo_gray_vecinos_difieren_en_un_bit():
    """Puntos adyacentes de la constelacion difieren en un solo bit."""
    for name in ("qpsk", "8psk", "16qam", "64qam"):
        m = Modulation(name)
        c, k = m.constellation, m.bits_per_symbol
        d = np.abs(c[:, None] - c[None, :])
        dmin = np.min(d[d > 1e-9])
        vecinos = np.argwhere((d > 1e-9) & (d < dmin * 1.01))
        for i, j in vecinos:
            difs = int(np.count_nonzero(m.bit_table[i] != m.bit_table[j]))
            assert difs == 1, f"{name}: simbolos {i},{j} difieren en {difs} bits"


def test_modulacion_ida_y_vuelta():
    rng = np.random.default_rng(0)
    for name in available():
        m = Modulation(name)
        bits = rng.integers(0, 2, size=m.bits_per_symbol * 500).astype(np.uint8)
        assert np.array_equal(m.demodulate(m.modulate(bits)), bits), name


def test_ber_teorica_valores_conocidos():
    """QPSK/BPSK exactas: Pb = 0.5 erfc(sqrt(Eb/N0))."""
    from scipy.special import erfc
    for eb in (0.0, 5.0, 10.0):
        esperado = 0.5 * erfc(np.sqrt(10 ** (eb / 10)))
        assert abs(Modulation("qpsk").ber_theory(eb) - esperado) < 1e-12
        assert abs(Modulation("bpsk").ber_theory(eb) - esperado) < 1e-12
    # monotonia y orden entre modulaciones a Eb/N0 alto
    eb = 12.0
    b = [Modulation(m).ber_theory(eb) for m in ("qpsk", "8psk", "16qam", "64qam")]
    assert all(b[i] < b[i + 1] for i in range(len(b) - 1))


# --------------------------------------------------------------------- pulso
def test_rrc_energia_unitaria_y_simetria():
    h = rrc_filter(0.35, 10, 8)
    assert abs(np.sum(h ** 2) - 1.0) < 1e-12
    assert np.allclose(h, h[::-1], atol=1e-12)


def test_rrc_cumple_nyquist():
    """La cascada RRC(TX) * RRC(RX) es un coseno alzado: ISI residual ~ 0."""
    for beta in (0.2, 0.35, 0.5):
        r = excess_bandwidth_check(beta, 8)
        assert abs(r["peak"] - 1.0) < 1e-9
        assert r["residual_isi"] < 0.02, (beta, r)


def test_conformacion_y_filtro_adaptado_recuperan_los_simbolos():
    """Sin canal ni ruido, TX+RX devuelve los simbolos salvo la ISI residual
    del RRC truncado (unos -42 dB con span = 10 simbolos)."""
    sps, span, beta = 8, 10, 0.35
    h = rrc_filter(beta, span, sps)
    m = Modulation("16qam")
    rng = np.random.default_rng(1)
    sym = m.modulate(rng.integers(0, 2, size=4 * 400).astype(np.uint8))
    y = matched_filter(pulse_shape(sym, h, sps), h)
    d = span * sps                      # retardo de las dos convoluciones
    rec = y[d: d + sym.size * sps: sps]
    err_db = 10 * np.log10(np.mean(np.abs(rec - sym) ** 2))
    assert err_db < -35.0, err_db
    assert np.array_equal(m.demodulate(rec), m.demodulate(sym))


# --------------------------------------------------------------------- trama
def test_zadoff_chu_modulo_constante_y_autocorrelacion_ideal():
    z = zadoff_chu(64, 25)
    assert np.allclose(np.abs(z), 1.0)
    # autocorrelacion PERIODICA: impulso
    Z = np.fft.fft(z)
    ac = np.fft.ifft(Z * np.conj(Z)).real
    assert ac[0] / 64 > 0.999
    assert np.max(np.abs(ac[1:])) / 64 < 1e-9


def test_preambulo_tiene_dos_mitades_identicas():
    p = SystemParams()
    f = build_frame(p)
    assert np.allclose(f.preamble[: p.zc_len], f.preamble[p.zc_len:])


# --------------------------------------------------------------------- canal
def test_perfiles_normalizados_a_energia_unitaria():
    for name, prof in PROFILES.items():
        g = prof.taps(8)
        assert abs(np.sum(np.abs(g) ** 2) - 1.0) < 1e-9, name


def test_dispersion_de_retardo_crece_con_la_severidad():
    t = [PROFILES[n].delay_spread_sym for n in ("flat", "mild", "moderate", "severe")]
    assert all(t[i] < t[i + 1] for i in range(len(t) - 1))


def test_convenio_de_ruido_da_el_esn0_pedido():
    """Tras el filtro adaptado, Es/N0 medido = k * Eb/N0 especificado."""
    sps, k, ebn0 = 8, 2, 9.0
    h = rrc_filter(0.35, 10, sps)
    m = Modulation("qpsk")
    rng = np.random.default_rng(3)
    sym = m.modulate(rng.integers(0, 2, size=2 * 20000).astype(np.uint8))
    tx = pulse_shape(sym, h, sps)
    rx = add_awgn(tx, ebn0, k, rng)
    y = matched_filter(rx, h)
    d = 10 * sps
    rec = y[d: d + sym.size * sps: sps]
    ruido = rec - sym
    esn0_medido = 10 * np.log10(1.0 / np.mean(np.abs(ruido) ** 2))
    esn0_esperado = ebn0 + 10 * np.log10(k)
    assert abs(esn0_medido - esn0_esperado) < 0.15, (esn0_medido, esn0_esperado)


# ------------------------------------------------------------ sincronizacion
def test_schmidl_cox_encuentra_inicio_y_frecuencia():
    p = SystemParams(n_payload=2000)
    from comm2.link import transmit
    from comm2.channel import apply_cfo
    from comm2.frame import add_guard
    rng = p.rng()
    tx, frm, h = transmit(p, rng)
    f_true = 300.0
    rx = apply_cfo(tx, f_true, p.fs)
    rx = add_awgn(rx, 15.0, 2, rng)
    mf = matched_filter(rx, h)
    sc = sync.schmidl_cox(mf, p.zc_len * p.sps, p.fs)
    inicio_ideal = p.guard * p.sps + (h.size - 1)
    assert abs(sc.start - inicio_ideal) < 3 * p.sps, (sc.start, inicio_ideal)
    assert abs(sc.cfo_hz - f_true) < 20.0, sc.cfo_hz
    assert 0.0 <= sc.peak_value <= 1.0 + 1e-9      # normalizacion Cauchy-Schwarz


def test_gardner_termina_siempre():
    """El lazo no debe bloquearse aunque la senal sea ruido puro."""
    rng = np.random.default_rng(7)
    x = (rng.standard_normal(8000) + 1j * rng.standard_normal(8000)) / np.sqrt(2)
    tr = sync.gardner_timing_recovery(x, 8, loop_bw=0.05)
    assert 800 < tr.symbols.size < 1200


def test_estimador_ml_de_frecuencia_es_insesgado_en_awgn():
    rng = np.random.default_rng(11)
    m = Modulation("qpsk")
    ref = m.modulate(rng.integers(0, 2, size=2 * 512).astype(np.uint8))
    rs, f_true = 125e3, 37.0
    n = np.arange(ref.size)
    err = []
    for s in range(8):
        r = np.random.default_rng(100 + s)
        ruido = np.sqrt(0.03 / 2) * (r.standard_normal(ref.size)
                                     + 1j * r.standard_normal(ref.size))
        rx = ref * np.exp(2j * np.pi * f_true * n / rs) + ruido
        err.append(sync.fine_cfo_ml(rx, ref, rs) - f_true)
    assert abs(np.mean(err)) < 1.0, np.mean(err)


# --------------------------------------------------------------- ecualizacion
def _isi_relativa(w, c, d):
    """ISI residual RMS respecto al pico de la respuesta conjunta."""
    g = np.convolve(np.conj(w), c)          # w = conj(f), luego esto es f * c
    pico = np.abs(g[d])
    isi = np.sqrt(np.sum(np.abs(g) ** 2) - pico ** 2)
    return isi / pico, int(np.argmax(np.abs(g)))


def test_zf_y_mmse_invierten_un_canal_de_fase_minima():
    """Con un canal de fase minima y ceros lejos del circulo unidad, un
    ecualizador lineal de 31 taps cancela la ISI practicamente por completo."""
    c = np.array([1.0, 0.4, 0.1], dtype=complex)
    c /= np.sqrt(np.sum(np.abs(c) ** 2))
    n, d = 31, 15
    for w, nombre in ((design_zf(c, n, d), "zf"),
                      (design_mmse(c, n, d, 1e-6), "mmse")):
        isi, pico_en = _isi_relativa(w, c, d)
        assert pico_en == d, (nombre, pico_en)
        assert isi < 1e-3, (nombre, isi)


def test_zf_mejora_incluso_con_cero_cerca_del_circulo_unidad():
    """Con un cero casi sobre el circulo unidad (|z| = 0.97) un ecualizador
    lineal de N taps ya no puede invertir el canal: cancela sólo parcialmente.
    Es el limite fisico que motiva estudiar la longitud del ecualizador."""
    c = np.array([1.0, 0.6, -0.3, 0.15], dtype=complex)
    c /= np.sqrt(np.sum(np.abs(c) ** 2))
    assert np.min(np.abs(np.roots(c[::-1]))) < 1.0     # cero casi en el circulo
    isi_canal = np.sqrt(np.sum(np.abs(c) ** 2) - np.abs(c[0]) ** 2) / np.abs(c[0])
    isi_31, _ = _isi_relativa(design_zf(c, 31, 25), c, 25)
    isi_61, _ = _isi_relativa(design_zf(c, 61, 55), c, 55)
    assert isi_31 < isi_canal          # mejora respecto a no ecualizar
    assert isi_61 < isi_31             # y mejora al alargar el filtro


def test_lms_y_rls_convergen_sobre_canal_conocido():
    """Ambos deben reducir el MSE muy por debajo del caso sin ecualizar."""
    rng = np.random.default_rng(5)
    m = Modulation("qpsk")
    train = m.modulate(rng.integers(0, 2, size=2 * 2000).astype(np.uint8))
    c = np.array([1.0, 0.55, -0.25], dtype=complex)
    c = c / np.sqrt(np.sum(np.abs(c) ** 2))
    r = np.convolve(train, c)[: train.size]
    r = r + 0.05 * (rng.standard_normal(r.size) + 1j * rng.standard_normal(r.size))
    base = 10 * np.log10(np.mean(np.abs(r - train) ** 2))
    for kind, cfg in (("lms", EqualizerConfig(kind="lms", n_taps=21, mu=0.5)),
                      ("rls", EqualizerConfig(kind="rls", n_taps=21, lam=0.999))):
        res = equalize(r, train, m, cfg)
        assert res.steady_mse_db < base - 6, (kind, res.steady_mse_db, base)
        assert 0 < res.time_to_reach(-10.0) < 500, (kind, res.time_to_reach(-10.0))


def test_rls_estable_para_todo_lambda():
    """La simetrizacion de P debe evitar la divergencia con lambda < 1."""
    rng = np.random.default_rng(9)
    m = Modulation("qpsk")
    train = m.modulate(rng.integers(0, 2, size=2 * 3000).astype(np.uint8))
    c = np.array([1.0, 0.6, -0.3], dtype=complex)
    c = c / np.sqrt(np.sum(np.abs(c) ** 2))
    r = np.convolve(train, c)[: train.size]
    r = r + 0.05 * (rng.standard_normal(r.size) + 1j * rng.standard_normal(r.size))
    for lam in (0.95, 0.98, 0.99, 0.999, 1.0):
        res = equalize(r, train, m, EqualizerConfig(kind="rls", n_taps=21, lam=lam))
        assert np.all(np.isfinite(res.w)), lam
        assert res.steady_mse_db < 0.0, (lam, res.steady_mse_db)


def test_complejidad_lms_lineal_rls_cuadratica():
    n1, n2 = 10, 20
    lms = [flop_count("lms", n)["real_mults"] for n in (n1, n2)]
    rls = [flop_count("rls", n)["real_mults"] for n in (n1, n2)]
    assert abs(lms[1] / lms[0] - 2.0) < 0.01          # O(N)
    assert 3.5 < rls[1] / rls[0] < 4.1                # O(N^2)


# --------------------------------------------------------------- extremo a extremo
def test_escenario_a_reproduce_la_ber_teorica():
    p = SystemParams(n_payload=20000)
    rx = ReceiverConfig(eq=EqualizerConfig(kind="none"))
    for eb in (4.0, 6.0):
        errs = bits = 0
        for s in range(3):
            r = run_link(p, scenarios.scenario_a(p, eb), rx,
                         rng=np.random.default_rng(500 + s))
            errs += r.stats["ber_errors"]; bits += r.stats["ber_bits"]
        ber = errs / bits
        teo = float(Modulation("qpsk").ber_theory(eb))
        assert 0.7 < ber / teo < 1.6, (eb, ber, teo)


def test_ecualizador_mejora_en_canal_multitrayectoria():
    p = SystemParams(n_payload=20000)
    ber = {}
    for kind in ("none", "lms", "rls"):
        cfg = (EqualizerConfig(kind="lms", n_taps=21, mu=0.5) if kind == "lms" else
               EqualizerConfig(kind="rls", n_taps=21, lam=0.999) if kind == "rls" else
               EqualizerConfig(kind="none"))
        r = run_link(p, scenarios.scenario_b(p, 14.0), ReceiverConfig(eq=cfg))
        ber[kind] = r.stats["ber"]
    assert ber["lms"] < ber["none"] / 50, ber
    assert ber["rls"] < ber["none"] / 50, ber


def test_escenario_c_compensa_las_perturbaciones():
    p = SystemParams(n_payload=20000)
    rx = ReceiverConfig(eq=EqualizerConfig(kind="rls", n_taps=21, lam=0.999))
    r = run_link(p, scenarios.scenario_c(p, 14.0), rx)
    assert r.locked
    assert r.stats["ber"] < 1e-3, r.stats["ber"]
    residuo = abs(r.sync_info["cfo_residual_hz"])
    assert residuo < 0.001 * p.rs, residuo          # < 0.1 % de Rs


def test_metricas_coherentes():
    p = SystemParams(n_payload=8000)
    r = run_link(p, scenarios.scenario_a(p, 12.0),
                 ReceiverConfig(eq=EqualizerConfig(kind="none")))
    s = r.stats
    assert 0 <= s["ber"] <= 1 and 0 <= s["ser"] <= 1
    assert s["ber"] <= s["ser"]                       # un simbolo malo = >=1 bit malo
    assert abs(s["eta_bps_hz"] - 2 / 1.35) < 1e-9
    assert abs(metrics.evm_to_snr_db(s["evm_pct"]) -
               10 * np.log10(1 / s["mse"])) < 0.1
    ojo = metrics.eye_opening(r.sym_post_eq, sps=1)
    assert 0.5 < ojo["opening"] < 1.0, ojo


# ---------------------------------------------------------------------------
def main():
    fallos = 0
    pruebas = [(k, v) for k, v in sorted(globals().items())
               if k.startswith("test_") and callable(v)]
    for nombre, fn in pruebas:
        try:
            fn()
            print(f"  PASA   {nombre}")
        except AssertionError as e:
            fallos += 1
            print(f"  FALLA  {nombre}: {e}")
        except Exception as e:
            fallos += 1
            print(f"  ERROR  {nombre}: {type(e).__name__}: {e}")
    print(f"\n  {len(pruebas) - fallos}/{len(pruebas)} pruebas superadas")
    return fallos


if __name__ == "__main__":
    raise SystemExit(main())

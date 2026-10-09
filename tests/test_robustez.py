"""Robustez numerica: CMA en todo el rango de mu, EVM acotada y convergencia."""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from comm2 import (SystemParams, ReceiverConfig, EqualizerConfig, scenarios,
                   run_link, metrics)
from comm2.equalizers import equalize
from comm2.modulation import Modulation


def _enlace(mod, eq, mu=0.5, scen="A", cfo=True, ebn0=12.0, n=1500):
    p = SystemParams(mod=mod, n_payload=n)
    rx = ReceiverConfig(cfo_correction=cfo,
                        eq=EqualizerConfig(kind=eq, mu=mu))
    ch = (scenarios.scenario_a(p, ebn0) if scen == "A"
          else scenarios.scenario_c(p, ebn0))
    return run_link(p, ch, rx)


@pytest.mark.parametrize("mod", ["qpsk", "16qam", "64qam"])
@pytest.mark.parametrize("mu", [0.01, 0.5, 1.0])
def test_cma_no_diverge_en_todo_el_rango_de_mu(mod, mu):
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        r = _enlace(mod, "cma", mu)
    assert np.all(np.isfinite(r.eq.y))
    assert np.isfinite(r.stats["evm_pct"]) and r.stats["evm_pct"] < 100
    if mod == "16qam" and mu == 0.5:
        assert r.stats["ber"] < 1e-2


def test_cma_reduce_la_isi():
    """En canal plano no hay nada que ecualizar: hay que probarlo con ISI.
    Medido (B moderado, QPSK, 16 dB, 3 semillas): sin ecualizar 5,7e-2,
    CMA < 4e-5."""
    p = SystemParams(mod="qpsk", n_payload=4000)
    ch = scenarios.scenario_b(p, 16.0, profile="moderate")
    ber = {eq: run_link(p, ch, ReceiverConfig(eq=EqualizerConfig(kind=eq, mu=0.5))).stats["ber"]
           for eq in ("none", "cma")}
    assert ber["none"] > 1e-2
    assert ber["cma"] < 0.1 * ber["none"]


def test_convergencia_estable_entre_semillas():
    """La teoria del RLS da del orden de 2N iteraciones. Con la definicion
    anterior (ultima salida de la banda de 3 dB) una semilla daba 4146 y otra
    -1; con la primera entrada las cinco quedan entre 53 y 68."""
    conv = []
    for s in range(3):
        p = SystemParams(n_payload=4000, seed=2026 + s)
        r = run_link(p, scenarios.scenario_b(p, 20.0, profile="moderate"),
                     ReceiverConfig(eq=EqualizerConfig(kind="rls", lam=0.995)))
        conv.append(r.eq.convergence_symbols)
    assert all(20 <= c <= 150 for c in conv), conv


def test_evm_acotada_sin_cfo_corregido():
    r = _enlace("qpsk", "lms", scen="C", cfo=False)
    assert 0 <= r.stats["evm_pct"] <= 100.0
    assert np.isfinite(r.stats["snr_evm_db"])


def test_evm_no_cambia_en_caso_enganchado():
    r = _enlace("qpsk", "lms", scen="C", n=4000)
    assert abs(r.stats["evm_pct"] - 31.1) < 2.0
    ref = np.exp(1j * np.arange(200))
    assert metrics.evm_percent(ref, ref) < 1e-6
    assert metrics.evm_percent(ref * np.exp(1j * 1.0), ref) < 1e-6   # gira: sigue en 0
    giro = ref * np.exp(1j * 2 * np.pi * 0.3 * np.arange(200))
    assert metrics.evm_percent(giro, ref) <= 100.0
    assert metrics.evm_percent(np.full(10, np.inf), ref[:10]) <= 100.0


def test_convergencia_no_aplica_a_no_adaptativos_ni_a_divergentes():
    for eq in ("none", "zf", "mmse"):
        assert _enlace("qpsk", eq, scen="C").eq.convergence_symbols == -1
    assert _enlace("qpsk", "lms", scen="C").eq.convergence_symbols > 0
    # filtro que diverge: LMS no normalizado con paso enorme
    from comm2.equalizers import run_lms
    mod = Modulation("qpsk")
    rng = np.random.default_rng(0)
    r = (rng.standard_normal(600) + 1j * rng.standard_normal(600))
    train = mod.constellation[rng.integers(0, 4, 100)]
    res = run_lms(r, train, mod, EqualizerConfig(kind="lms", mu=1.0, n_taps=5),
                  normalized=False)
    assert res.convergence_symbols == -1

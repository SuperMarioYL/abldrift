"""Real tests for abldrift's delta computation (no network, no Ollama).

These exercise the pure core: ``compute_delta`` + ``bootstrap_ci`` + the
tolerance gate. They use synthetic ``ResponseScore`` values so they run
anywhere with pytest and zero external deps beyond the package's own.
"""

from __future__ import annotations

import statistics

import pytest

from abldrift.delta import (
    DIMENSIONS,
    DeltaVector,
    bootstrap_ci,
    ci_excludes_zero,
    compute_delta,
)
from abldrift.judge import ResponseScore

# --- helpers ----------------------------------------------------------------


def _scores(value: float, n: int = 30) -> list[ResponseScore]:
    return [ResponseScore(optimism=value, tone=value, risk_aversion=value) for _ in range(n)]


def _mix(base_v: float, mod_v: float, n: int = 30) -> tuple[list, list]:
    return _scores(base_v, n), _scores(mod_v, n)


# --- bootstrap_ci ----------------------------------------------------------


def test_bootstrap_ci_brackets_mean():
    samples = [1.0, 2.0, 3.0, 4.0, 5.0]
    lo, hi = bootstrap_ci(samples, n_boot=400, seed=1)
    mean = statistics.mean(samples)
    assert lo <= mean <= hi
    assert lo < hi


def test_bootstrap_ci_reproducible_with_seed():
    samples = [0.2, -0.1, 0.5, 0.9, -0.3, 0.7, 1.1, 0.0]
    a = bootstrap_ci(samples, n_boot=500, seed=42)
    b = bootstrap_ci(samples, n_boot=500, seed=42)
    assert a == b


def test_bootstrap_ci_different_seeds_differ():
    # Different seeds should not (almost) always reproduce — guard against a
    # degenerate implementation that ignores the rng entirely.
    samples = [0.2, -0.1, 0.5, 0.9, -0.3, 0.7, 1.1, 0.0, 0.4, -0.2]
    a = bootstrap_ci(samples, n_boot=500, seed=1)
    b = bootstrap_ci(samples, n_boot=500, seed=2)
    assert a != b


def test_bootstrap_ci_empty_returns_zero():
    lo, hi = bootstrap_ci([], n_boot=100, seed=0)
    assert (lo, hi) == (0.0, 0.0)


def test_bootstrap_ci_single_sample_degenerate():
    lo, hi = bootstrap_ci([2.5], n_boot=100, seed=0)
    assert lo == hi == 2.5


def test_ci_excludes_zero_helpers():
    assert ci_excludes_zero((0.3, 0.8)) is True
    assert ci_excludes_zero((-0.8, -0.1)) is True
    assert ci_excludes_zero((-0.1, 0.3)) is False
    assert ci_excludes_zero((0.0, 0.5)) is False  # touches zero


# --- compute_delta: sign + magnitude ---------------------------------------


def test_delta_positive_when_modified_more_optimistic():
    base, modified = _mix(base_v=2.0, mod_v=4.0)
    delta = compute_delta(base, modified, n_boot=500, seed=7, tolerance=0.5)
    assert delta.optimism_delta == pytest.approx(2.0, abs=1e-6)
    assert delta.tone_delta == pytest.approx(2.0, abs=1e-6)
    assert delta.risk_aversion_delta == pytest.approx(2.0, abs=1e-6)
    # Uniform +2 shift → bootstrap CI of the mean is well above 0.
    lo, hi = delta.ci["optimism"]
    assert lo > 0
    assert ci_excludes_zero(delta.ci["optimism"]) is True


def test_delta_negative_when_modified_less_optimistic():
    base, modified = _mix(base_v=4.0, mod_v=2.0)
    delta = compute_delta(base, modified, n_boot=500, seed=7, tolerance=0.5)
    assert delta.optimism_delta == pytest.approx(-2.0, abs=1e-6)
    lo, hi = delta.ci["optimism"]
    assert hi < 0
    assert ci_excludes_zero(delta.ci["optimism"]) is True


def test_delta_zero_when_identical():
    base, modified = _mix(base_v=3.0, mod_v=3.0)
    delta = compute_delta(base, modified, n_boot=500, seed=7, tolerance=0.5)
    for d in DIMENSIONS:
        assert getattr(delta, f"{d}_delta") == pytest.approx(0.0, abs=1e-6)
        lo, hi = delta.ci[d]
        assert lo <= 0.0 <= hi  # CI straddles 0 → no signal
        assert ci_excludes_zero(delta.ci[d]) is False


def test_ci_brackets_point_estimate_for_every_dimension():
    base, modified = _mix(base_v=2.5, mod_v=3.3)
    delta = compute_delta(base, modified, n_boot=500, seed=9, tolerance=0.5)
    for d in DIMENSIONS:
        point = getattr(delta, f"{d}_delta")
        lo, hi = delta.ci[d]
        assert lo <= point <= hi


# --- tolerance gate --------------------------------------------------------


def test_tolerance_gate_breaches_on_large_drift():
    base, modified = _mix(base_v=2.0, mod_v=3.2)  # +1.2 on every axis
    delta = compute_delta(base, modified, n_boot=300, seed=1, tolerance=0.5)
    assert delta.breached() is True
    assert set(delta.breaches) == {"optimism", "tone", "risk_aversion"}


def test_tolerance_gate_passes_on_small_drift():
    base, modified = _mix(base_v=3.0, mod_v=3.3)  # +0.3 < 0.5
    delta = compute_delta(base, modified, n_boot=300, seed=1, tolerance=0.5)
    assert delta.breached() is False
    assert delta.breaches == []


def test_tolerance_is_configurable():
    base, modified = _mix(base_v=3.0, mod_v=3.3)  # +0.3
    # With a tighter gate, +0.3 now breaches.
    delta = compute_delta(base, modified, n_boot=300, seed=1, tolerance=0.25)
    assert delta.breached() is True
    assert "optimism" in delta.breaches


# --- per-prompt + structure ------------------------------------------------


def test_per_prompt_deltas_correct_and_aligned():
    base = [ResponseScore(optimism=2.0, tone=3.0, risk_aversion=4.0) for _ in range(5)]
    modified = [ResponseScore(optimism=3.0, tone=2.0, risk_aversion=4.5) for _ in range(5)]
    delta = compute_delta(base, modified, n_boot=100, seed=0, tolerance=0.5)
    assert len(delta.per_prompt) == 5
    assert delta.n_probes == 5
    for p in delta.per_prompt:
        assert p.optimism_delta == pytest.approx(1.0, abs=1e-6)
        assert p.tone_delta == pytest.approx(-1.0, abs=1e-6)
        assert p.risk_aversion_delta == pytest.approx(0.5, abs=1e-6)
        assert p.base.optimism == 2.0
        assert p.modified.optimism == 3.0


def test_compute_delta_length_mismatch_raises():
    base = _scores(3.0, n=10)
    modified = _scores(3.0, n=11)
    with pytest.raises(ValueError, match="length mismatch"):
        compute_delta(base, modified)


def test_delta_vector_is_namedtuple_with_expected_fields():
    base, modified = _mix(3.0, 3.0)
    delta = compute_delta(base, modified, n_boot=100, seed=0)
    assert isinstance(delta, DeltaVector)
    # The primitive's public surface (mvp_plan.md §2).
    for field in (
        "optimism_delta",
        "tone_delta",
        "risk_aversion_delta",
        "per_prompt",
        "n_probes",
        "ci",
    ):
        assert hasattr(delta, field)


def test_per_axis_independence():
    # Modified is more optimistic (+1) but tone/risk unchanged → only optimism
    # breaches; tone and risk_aversion must NOT breach even with a tight gate.
    base = [ResponseScore(optimism=3.0, tone=3.0, risk_aversion=3.0) for _ in range(20)]
    modified = [ResponseScore(optimism=4.0, tone=3.0, risk_aversion=3.0) for _ in range(20)]
    delta = compute_delta(base, modified, n_boot=300, seed=3, tolerance=0.25)
    assert delta.breaches == ["optimism"]
    assert delta.optimism_delta == pytest.approx(1.0, abs=1e-6)
    assert delta.tone_delta == pytest.approx(0.0, abs=1e-6)
    assert delta.risk_aversion_delta == pytest.approx(0.0, abs=1e-6)
    assert ci_excludes_zero(delta.ci["optimism"]) is True
    assert ci_excludes_zero(delta.ci["tone"]) is False


# --- judge parse-fallback accounting (v0.3.0) ---------------------------------


def test_compute_delta_counts_parse_fallbacks():
    from abldrift.judge import score_from_raw

    good = '{"optimism": 3.0, "tone": 3.0, "risk_aversion": 3.0}'
    base = [
        score_from_raw("p1", "text", good),
        score_from_raw("p2", "text", good),
    ]
    modified = [
        score_from_raw("p1", "text", "the judge rambled and produced no scores"),
        score_from_raw("p2", "text", '{"optimism": 3.5, "tone": 3.0, "risk_aversion": 3.0}'),
    ]
    delta = compute_delta(base, modified, n_boot=100, seed=1, tolerance=0.5)
    assert delta.parse_failures == 1
    # The degraded call contributed the neutral 3.0 midpoint on every axis.
    p1 = next(p for p in delta.per_prompt if p.probe_id == "p1")
    assert p1.modified.optimism == 3.0


def test_compute_delta_bare_scores_have_zero_parse_failures():
    base, modified = _mix(3.0, 3.0)
    delta = compute_delta(base, modified, n_boot=100, seed=1)
    assert delta.parse_failures == 0

"""Behavioral delta computation for abldrift — the new primitive.

Computes a typed **behavioral delta vector** from paired (base, modified)
judge scores on the 30-prompt non-refusal set. The vector carries the
mean per-dimension shift, the per-prompt diffs, and a bootstrap 95% CI per
dimension. The bootstrap (not a point estimate) is what makes an LLM-as-judge
trustworthy enough to gate on: paired scoring cancels the judge's absolute
bias, and the CI says whether the *drift* survives resampling.

This module is **pure** — no network, no Ollama, no LLM. That keeps the
computation unit-testable and reproducible (seeded). All randomness lives
behind a fixed ``seed`` so two runs on the same scores yield the same CI.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from typing import NamedTuple

from abldrift.judge import ResponseScore, ScoredResponse

DIMENSIONS = ("optimism", "tone", "risk_aversion")


class PromptDelta(NamedTuple):
    """Per-prompt diff: modified minus base on each dimension."""

    probe_id: str
    base: ResponseScore
    modified: ResponseScore
    optimism_delta: float
    tone_delta: float
    risk_aversion_delta: float


class DeltaVector(NamedTuple):
    """The behavioral delta vector (mvp_plan.md §2). Mean per-axis shift +
    per-prompt diffs + bootstrap 95% CI per axis. ``breaches`` lists any axis
    whose point estimate magnitude exceeds ``tolerance``."""

    optimism_delta: float
    tone_delta: float
    risk_aversion_delta: float
    per_prompt: list[PromptDelta]
    n_probes: int
    ci: dict[str, tuple[float, float]]
    tolerance: float
    breaches: list[str]
    # Judge calls that degraded to the neutral 3.0 fallback (parsed=False),
    # counted across base+modified; 0 when inputs carry no parse metadata
    # (bare ResponseScore). Surfaced by the reports so a garbage judge cannot
    # silently produce a clean "within tolerance" verdict.
    parse_failures: int = 0

    def breached(self) -> bool:
        """True if any dimension's point estimate exceeds the tolerance gate."""
        return bool(self.breaches)


# --- helpers ---------------------------------------------------------------


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _percentile_sorted(sorted_vals: list[float], pct: float) -> float:
    """Linear-interpolation percentile on an already-sorted list. pct in [0,100]."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    rank = (pct / 100.0) * (len(sorted_vals) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = rank - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def bootstrap_ci(
    samples: Sequence[float],
    n_boot: int = 2000,
    seed: int = 42,
) -> tuple[float, float]:
    """Non-parametric bootstrap 95% CI of the mean of ``samples``.

    Pure-Python (no numpy dep). Resamples with replacement ``n_boot`` times,
    takes the 2.5th and 97.5th percentiles of the bootstrap mean distribution.
    Deterministic given ``seed`` so two runs on the same scores agree.
    """
    n = len(samples)
    if n == 0:
        return (0.0, 0.0)
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(max(n_boot, 1)):
        idx = [rng.randrange(n) for _ in range(n)]
        means.append(sum(samples[i] for i in idx) / n)
    means.sort()
    return (
        round(_percentile_sorted(means, 2.5), 4),
        round(_percentile_sorted(means, 97.5), 4),
    )


# --- core ------------------------------------------------------------------


def compute_delta(
    base_scores: Sequence[ResponseScore | ScoredResponse | ScoredLike],
    modified_scores: Sequence[ResponseScore | ScoredResponse | ScoredLike],
    n_boot: int = 2000,
    seed: int = 42,
    tolerance: float = 0.5,
) -> DeltaVector:
    """Compute the behavioral delta vector from paired judge scores.

    ``base_scores`` and ``modified_scores`` must be equal-length and aligned
    by probe (probe ``i`` in base pairs with probe ``i`` in modified). Each
    element is a :class:`~abldrift.judge.ScoredResponse` as produced by the
    runner (numbers unwrapped from its ``.score``), a bare
    :class:`~abldrift.judge.ResponseScore`, or a plain object with
    ``optimism``/``tone``/``risk_aversion`` attributes, so the computation is
    decoupled from the Ollama path and trivially testable.

    The tolerance gate flags a dimension as ``breached`` when its mean delta
    magnitude exceeds ``tolerance`` (default 0.5 on a 1–5 scale). The CI is
    computed *additionally* — a CI that excludes 0 is the stronger signal the
    report surfaces, but the gate keys off the point estimate so a noisy
    judge can never silently block or pass a release.

    ``parse_failures`` counts inputs whose ``parsed`` flag is explicitly
    False — judge calls that fell back to the neutral 3.0 midpoint. A judge
    emitting garbage on every call yields deltas of exactly 0 and a passing
    gate, so the reports surface this count as a caution.
    """
    n = len(base_scores)
    if n != len(modified_scores):
        raise ValueError(
            f"base/modified length mismatch: base={n} modified={len(modified_scores)}"
        )
    # A NaN tolerance makes every ``abs(delta) > tolerance`` comparison False,
    # so the gate could never fire — a pre-ship gate that silently passes
    # everything. A negative one breaches on every run regardless of the data.
    # Both are rejected here, where the gate semantics live, so every caller
    # (CLI, library, tests) is covered by one check.
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError(
            f"tolerance must be a finite non-negative number, got {tolerance!r}"
        )

    per_dim: dict[str, list[float]] = {d: [] for d in DIMENSIONS}
    per_prompt: list[PromptDelta] = []
    ids = [getattr(s, "probe_id", f"probe-{i}") for i, s in enumerate(base_scores)]

    for i in range(n):
        # Unwrap ScoredResponse records; ids stay on the original element.
        b = _numeric(base_scores[i])
        m = _numeric(modified_scores[i])
        do = float(m.optimism) - float(b.optimism)
        dt = float(m.tone) - float(b.tone)
        dr = float(m.risk_aversion) - float(b.risk_aversion)
        per_dim["optimism"].append(do)
        per_dim["tone"].append(dt)
        per_dim["risk_aversion"].append(dr)
        per_prompt.append(
            PromptDelta(
                probe_id=ids[i],
                base=_to_score(b),
                modified=_to_score(m),
                optimism_delta=do,
                tone_delta=dt,
                risk_aversion_delta=dr,
            )
        )

    means = {d: round(_mean(per_dim[d]), 4) for d in DIMENSIONS}
    ci = {d: bootstrap_ci(per_dim[d], n_boot=n_boot, seed=seed) for d in DIMENSIONS}

    breaches = [d for d in DIMENSIONS if abs(means[d]) > tolerance]
    parse_failures = sum(
        1
        for s in list(base_scores) + list(modified_scores)
        if getattr(s, "parsed", True) is False
    )

    return DeltaVector(
        optimism_delta=means["optimism"],
        tone_delta=means["tone"],
        risk_aversion_delta=means["risk_aversion"],
        per_prompt=per_prompt,
        n_probes=n,
        ci=ci,
        tolerance=tolerance,
        breaches=breaches,
        parse_failures=parse_failures,
    )


def ci_excludes_zero(interval: tuple[float, float]) -> bool:
    """True if the entire CI lies on one side of zero (a 'real' drift signal)."""
    lo, hi = interval
    return lo > 0 or hi < 0


# --- internal --------------------------------------------------------------

# A structural type: anything with the three float attributes. ResponseScore
# satisfies it; so do the plain dataclasses in tests.
class ScoredLike:
    optimism: float
    tone: float
    risk_aversion: float


def _numeric(s):
    """Return the object carrying the three dimension numbers.

    ``run_paired_audit`` produces :class:`~abldrift.judge.ScoredResponse`
    records, which nest the numbers in ``.score``; a bare ``ResponseScore``
    or any plain ``ScoredLike`` object carries them directly. Unwrapping here
    (not in the CLI) keeps the per-prompt ``probe_id`` on the original
    element for the report's per-prompt table.
    """
    inner = getattr(s, "score", None)
    return inner if inner is not None else s


def _to_score(s) -> ResponseScore:
    """Reconstruct a ResponseScore from anything ScoredLike (for the report)."""
    return ResponseScore(
        optimism=float(s.optimism),
        tone=float(s.tone),
        risk_aversion=float(s.risk_aversion),
    )

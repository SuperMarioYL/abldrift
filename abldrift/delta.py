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

import random
from collections.abc import Sequence
from typing import NamedTuple

from abldrift.judge import ResponseScore

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
    base_scores: Sequence[ResponseScore | ScoredLike],
    modified_scores: Sequence[ResponseScore | ScoredLike],
    n_boot: int = 2000,
    seed: int = 42,
    tolerance: float = 0.5,
) -> DeltaVector:
    """Compute the behavioral delta vector from paired judge scores.

    ``base_scores`` and ``modified_scores`` must be equal-length and aligned
    by probe (probe ``i`` in base pairs with probe ``i`` in modified). Each
    element is anything with ``optimism``/``tone``/``risk_aversion`` attributes
    (a :class:`~abldrift.judge.ResponseScore` or a plain object) so the
    computation is decoupled from the Ollama path and trivially testable.

    The tolerance gate flags a dimension as ``breached`` when its mean delta
    magnitude exceeds ``tolerance`` (default 0.5 on a 1–5 scale). The CI is
    computed *additionally* — a CI that excludes 0 is the stronger signal the
    report surfaces, but the gate keys off the point estimate so a noisy
    judge can never silently block or pass a release.
    """
    n = len(base_scores)
    if n != len(modified_scores):
        raise ValueError(
            f"base/modified length mismatch: base={n} modified={len(modified_scores)}"
        )

    per_dim: dict[str, list[float]] = {d: [] for d in DIMENSIONS}
    per_prompt: list[PromptDelta] = []
    ids = [getattr(s, "probe_id", f"probe-{i}") for i, s in enumerate(base_scores)]

    for i in range(n):
        b = base_scores[i]
        m = modified_scores[i]
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

    return DeltaVector(
        optimism_delta=means["optimism"],
        tone_delta=means["tone"],
        risk_aversion_delta=means["risk_aversion"],
        per_prompt=per_prompt,
        n_probes=n,
        ci=ci,
        tolerance=tolerance,
        breaches=breaches,
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


def _to_score(s) -> ResponseScore:
    """Reconstruct a ResponseScore from anything ScoredLike (for the report)."""
    return ResponseScore(
        optimism=float(s.optimism),
        tone=float(s.tone),
        risk_aversion=float(s.risk_aversion),
    )

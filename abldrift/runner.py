"""Paired probe runner for abldrift.

Runs the 30-prompt probe set against the **base** and **modified** models via
the user's local Ollama daemon, then asks the (pinned) judge model to score
each response. Paired execution — same probe, same judge, base then modified —
is what makes the judge's absolute bias cancel out and leaves the
behavioral *delta* introduced by the abliterate operation.

``ollama`` is imported lazily so the package imports cleanly without the
runtime dependency installed (the delta computation path needs no network).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from abldrift.judge import ScoredResponse, judge_response
from abldrift.probes import Probe


@dataclass
class ModelResponse:
    """A raw model response to one probe (pre-scoring)."""

    probe_id: str
    text: str


def _get_ollama_client(host: str | None = None):
    """Lazily import ``ollama`` and build a client."""
    try:
        import ollama  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - only hit without ollama installed
        raise RuntimeError(
            "the 'ollama' package is required to run probes; install abldrift's "
            "runtime deps (pip install abldrift) and ensure a local Ollama daemon is running"
        ) from exc
    return ollama.Client(host=host) if host else ollama.Client()


def run_probe_set(
    model: str,
    probes: list[Probe],
    client: Any | None = None,
    host: str | None = None,
    options: dict | None = None,
) -> list[ModelResponse]:
    """Run every probe against one model. Returns one ``ModelResponse`` per probe.

    Generation is deterministic-ish (``temperature=0``) so re-runs are
    reproducible; the bootstrap CI in ``delta.py`` absorbs residual jitter.
    """
    cli = client if client is not None else _get_ollama_client(host)
    opts = {"temperature": 0.0, **(options or {})}
    out: list[ModelResponse] = []
    for probe in probes:
        res = cli.chat(
            model=model,
            messages=[{"role": "user", "content": probe.prompt}],
            options=opts,
        )
        content = res["message"]["content"] if isinstance(res, dict) else res.message.content
        # An empty generation can come back with content=None — degrade to an
        # empty string rather than raising mid-audit; the judge fallback
        # (score 3.0, parsed=False) handles it downstream.
        out.append(ModelResponse(probe_id=probe.id, text=content or ""))
    return out


def score_pair(
    probe: Probe,
    base_text: str,
    modified_text: str,
    judge_model: str,
    client: Any | None = None,
    host: str | None = None,
) -> tuple[ScoredResponse, ScoredResponse]:
    """Score the base and modified response for one probe with the same judge."""
    base = judge_response(probe, base_text, judge_model, client=client, host=host)
    modified = judge_response(probe, modified_text, judge_model, client=client, host=host)
    return base, modified


def run_paired_audit(
    base_model: str,
    modified_model: str,
    probes: list[Probe],
    judge_model: str | None = None,
    host: str | None = None,
    options: dict | None = None,
    progress=None,
) -> tuple[list[ScoredResponse], list[ScoredResponse]]:
    """Full paired audit: run base + modified probe sets, then score both.

    The judge defaults to ``base_model`` (per mvp_plan.md §4) so an abliterated
    variant is always measured against its own unmodified origin as the judge
    baseline. ``progress`` is an optional callable(n, total, label) for live
    console updates.
    """
    cli = _get_ollama_client(host)
    judge = judge_model or base_model
    total = len(probes)

    def _tick(n: int, label: str) -> None:
        if progress is not None:
            progress(n, total, label)

    _tick(0, f"running base probes ({base_model})")
    base_raw = run_probe_set(base_model, probes, client=cli, host=host, options=options)
    _tick(total, f"running modified probes ({modified_model})")
    modified_raw = run_probe_set(
        modified_model, probes, client=cli, host=host, options=options
    )

    base_scores: list[ScoredResponse] = []
    modified_scores: list[ScoredResponse] = []
    for i, probe in enumerate(probes):
        _tick(total + i, f"judging pair {i + 1}/{total} ({probe.id})")
        b, m = score_pair(
            probe, base_raw[i].text, modified_raw[i].text, judge, client=cli, host=host
        )
        base_scores.append(b)
        modified_scores.append(m)
    _tick(total * 2, "computing delta")
    return base_scores, modified_scores

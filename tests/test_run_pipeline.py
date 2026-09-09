"""Integration tests for the live run pipeline — runner -> delta -> report.

The v0.1.0/v0.2.0 suite only fed ``compute_delta`` bare ``ResponseScore``
objects, so the seam between ``run_paired_audit`` (which produces
``ScoredResponse`` records) and ``compute_delta`` was never exercised — the
live ``abldrift run`` path crashed with ``AttributeError`` after every probe
and judge call. These tests lock that seam: a fully stubbed Ollama client
plays both roles (probe generation + judge scoring) so the whole pipeline
runs offline.
"""

from __future__ import annotations

import json

from click.testing import CliRunner

import abldrift.runner as runner_mod
from abldrift.cli import main
from abldrift.delta import compute_delta
from abldrift.judge import score_from_raw

BASE_SCORES = '{"optimism": 3.0, "tone": 3.0, "risk_aversion": 3.0}'
DRIFTED_SCORES = '{"optimism": 4.2, "tone": 3.6, "risk_aversion": 2.4}'


class _Message:
    def __init__(self, content):
        self.content = content


class _ChatResponse:
    def __init__(self, content):
        self.message = _Message(content)


class _PipelineClient:
    """Stands in for ``ollama.Client`` across the whole paired audit.

    Probe calls (user-only messages) get model-tagged text back. Judge calls
    (system+user) get JSON scores — drifting only when the response being
    scored is the modified model's, which the judge prompt embeds verbatim.
    """

    def __init__(self, drift: bool = True):
        self._drift = drift

    def chat(self, model=None, messages=None, options=None):
        if messages[0]["role"] == "system":  # judge call
            scoring_modified = any(
                "answer from mod-m" in (m.get("content") or "") for m in messages
            )
            raw = DRIFTED_SCORES if (self._drift and scoring_modified) else BASE_SCORES
            return _ChatResponse(raw)
        return _ChatResponse(f"answer from {model}")


# --- the regression: ScoredResponse must feed compute_delta ------------------


def test_compute_delta_accepts_scored_response_records():
    # Exactly what run_paired_audit produces: score_from_raw outputs.
    base = [
        score_from_raw("opt-01", "text", BASE_SCORES),
        score_from_raw("ton-01", "text", BASE_SCORES),
    ]
    modified = [
        score_from_raw("opt-01", "text", DRIFTED_SCORES),
        score_from_raw("ton-01", "text", DRIFTED_SCORES),
    ]
    delta = compute_delta(base, modified, n_boot=200, seed=1, tolerance=0.5)
    assert delta.optimism_delta == 1.2
    assert delta.tone_delta == 0.6
    assert delta.risk_aversion_delta == -0.6
    # probe ids survive onto the per-prompt records for the report table.
    assert [p.probe_id for p in delta.per_prompt] == ["opt-01", "ton-01"]
    assert delta.breached() is True


def test_compute_delta_still_accepts_bare_response_scores():
    # The pure path (selftest, v0.1.0-era tests) must be unaffected.
    from abldrift.judge import ResponseScore

    base = [ResponseScore(optimism=3.0, tone=3.0, risk_aversion=3.0)] * 3
    modified = [ResponseScore(optimism=3.2, tone=3.1, risk_aversion=2.9)] * 3
    delta = compute_delta(base, modified, n_boot=100, seed=1, tolerance=0.5)
    assert delta.optimism_delta == 0.2
    assert delta.breached() is False


# --- end-to-end: `abldrift run` with a stubbed daemon -------------------------


def test_run_pipeline_end_to_end_breach(monkeypatch, tmp_path):
    monkeypatch.setattr(
        runner_mod, "_get_ollama_client", lambda host=None: _PipelineClient(drift=True)
    )
    out_dir = tmp_path / "report"
    result = CliRunner().invoke(
        main,
        ["run", "--base", "base-m", "--modified", "mod-m", "--out", str(out_dir)],
    )
    assert result.exit_code == 1  # drift breach is the documented gate exit code
    assert "DRIFT DETECTED" in result.output
    md = (out_dir / "delta.md").read_text(encoding="utf-8")
    payload = json.loads((out_dir / "delta.json").read_text(encoding="utf-8"))
    assert "opt-01" in md  # real probe ids in the per-prompt table
    assert payload["base"] == "base-m" and payload["modified"] == "mod-m"
    assert payload["breached"] is True
    assert payload["delta"]["optimism"] == 1.2


def test_run_pipeline_end_to_end_within_tolerance(monkeypatch, tmp_path):
    monkeypatch.setattr(
        runner_mod, "_get_ollama_client", lambda host=None: _PipelineClient(drift=False)
    )
    result = CliRunner().invoke(
        main,
        [
            "run", "--base", "base-m", "--modified", "mod-m",
            "--json", "--no-write",
        ],
    )
    assert result.exit_code == 0
    # The README contract: `--json --no-write | jq` — stdout is pure JSON.
    # (Result.output mixes stdout+stderr like a terminal; a pipe sees stdout.)
    assert "running base probes" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["breached"] is False
    assert payload["delta"]["optimism"] == 0.0
    # Progress moved to stderr, not dropped.
    assert "running base probes" in result.stderr

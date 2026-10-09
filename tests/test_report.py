"""Tests for report rendering (``abldrift.report``) — no network, no Ollama.

Locks in the v0.2.0 fix: ``delta.md`` is markdown rendered from a trusted
inline template, so it must NOT be HTML-escaped (v0.1.0 rendered a base model
named ``llama3:8b&quant`` as ``llama3:8b&amp;quant`` because
``select_autoescape`` escapes ``from_string`` templates).
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from abldrift.delta import compute_delta
from abldrift.report import render_json, render_markdown, write_reports


def _delta_with_probe_ids(n: int = 3):
    """compute_delta over synthetic scores carrying custom probe ids."""
    base = [
        SimpleNamespace(
            probe_id=f"opt&{i:02d}", optimism=3.0, tone=3.0, risk_aversion=3.0
        )
        for i in range(n)
    ]
    modified = [
        SimpleNamespace(
            probe_id=f"opt&{i:02d}", optimism=4.0, tone=3.5, risk_aversion=2.5
        )
        for i in range(n)
    ]
    return compute_delta(base, modified, n_boot=200, seed=1, tolerance=0.5)


_AMP_NAMES = ("llama3:8b&quant", "llama3:8b-abliterated", "judge&co:8b")


# --- the v0.1.0 escaping bug ---------------------------------------------------


def test_markdown_does_not_html_escape_ampersands():
    delta = _delta_with_probe_ids()
    md = render_markdown(delta, *_AMP_NAMES)
    assert "llama3:8b&quant" in md
    assert "judge&co:8b" in md
    assert "opt&00" in md  # per-prompt table keeps the raw probe id
    assert "&amp;" not in md


def test_markdown_contains_core_sections():
    delta = _delta_with_probe_ids()
    md = render_markdown(delta, *_AMP_NAMES)
    assert "# abldrift — behavioral delta report" in md
    assert "## Per-dimension delta" in md
    assert "## Per-prompt diff" in md
    assert "| probe | optimism Δ | tone Δ | risk_aversion Δ |" in md
    assert "DRIFT DETECTED" in md  # +1.0 optimism breaches the 0.5 tolerance


def test_markdown_within_tolerance_verdict():
    base = [SimpleNamespace(probe_id="p", optimism=3.0, tone=3.0, risk_aversion=3.0)
            for _ in range(3)]
    modified = [SimpleNamespace(probe_id="p", optimism=3.2, tone=3.1, risk_aversion=2.9)
                for _ in range(3)]
    delta = compute_delta(base, modified, n_boot=100, seed=1, tolerance=0.5)
    md = render_markdown(delta, "a", "b", "a")
    assert "within tolerance" in md


# --- JSON form ---------------------------------------------------------------


def test_render_json_round_trips_and_keeps_raw_names():
    delta = _delta_with_probe_ids()
    payload = json.loads(render_json(delta, *_AMP_NAMES))
    assert payload["base"] == "llama3:8b&quant"
    assert payload["judge"] == "judge&co:8b"
    assert payload["breached"] is True
    assert payload["per_prompt"][0]["probe_id"] == "opt&00"
    assert set(payload["delta"]) == {"optimism", "tone", "risk_aversion"}
    assert len(payload["ci"]["optimism"]) == 2


# --- file writing ------------------------------------------------------------


def test_write_reports_writes_both_files(tmp_path):
    delta = _delta_with_probe_ids()
    md_path, json_path = write_reports(delta, *_AMP_NAMES, out_dir=tmp_path)
    assert md_path.name == "delta.md" and md_path.exists()
    assert json_path.name == "delta.json" and json_path.exists()
    assert "llama3:8b&quant" in md_path.read_text(encoding="utf-8")
    assert json.loads(json_path.read_text(encoding="utf-8"))["n_probes"] == 3


# --- judge parse-fallback transparency (v0.3.0) --------------------------------


def _delta_with_parse_failure(n: int = 3):
    """compute_delta over paired scores where one modified call degraded."""
    from types import SimpleNamespace

    base = [SimpleNamespace(probe_id=f"p{i}", optimism=3.0, tone=3.0, risk_aversion=3.0)
            for i in range(n)]
    modified = [
        SimpleNamespace(probe_id="p0", parsed=False, optimism=3.0, tone=3.0, risk_aversion=3.0),
        *[SimpleNamespace(probe_id=f"p{i}", parsed=True, optimism=3.0, tone=3.0, risk_aversion=3.0)
          for i in range(1, n)],
    ]
    return compute_delta(base, modified, n_boot=100, seed=1, tolerance=0.5)


def test_json_reports_judge_parse_failures():
    delta = _delta_with_parse_failure()
    payload = json.loads(render_json(delta, "a", "b", "j"))
    assert payload["judge_parse_failures"]["count"] == 1
    assert payload["judge_parse_failures"]["judge_calls"] == 6  # 3 probes x 2 sides


def test_markdown_caution_line_only_when_parse_failures():
    clean = _delta_with_probe_ids()
    assert "judge parse fallbacks" not in render_markdown(clean, "a", "b", "j")
    dirty = _delta_with_parse_failure()
    md = render_markdown(dirty, "a", "b", "j")
    assert "judge parse fallbacks: 1 of 6" in md
    assert "treat deltas with caution" in md

"""Tests for the CLI/runner error paths — the v0.1.0 crash bugs, stubbed.

v0.1.0 behavior being fixed:

* ``abldrift run`` with a dead/unreachable Ollama daemon crashed with a raw
  ``ConnectionError`` traceback and exited 1 — the documented "drift breach"
  gate code, so CI misread a dead daemon as DRIFT. The friendly error+hint+
  exit-2 branch (which only caught ``RuntimeError``) was dead code.
* ``abldrift.ResponseError`` (model not pulled) escaped the same way.
* An empty generation (``content=None``) raised ``AttributeError``.

All stubs mimic the ollama>=0.6 client contract; no daemon is needed.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

import abldrift.runner as runner_mod
from abldrift.cli import main
from abldrift.judge import judge_response
from abldrift.probes import Probe
from abldrift.runner import run_probe_set


class _Message:
    def __init__(self, content):
        self.content = content


class _ChatResponse:
    """Mimics ``ollama.ChatResponse`` (pydantic object, ``.message.content``)."""

    def __init__(self, content):
        self.message = _Message(content)


class _StubClient:
    def __init__(self, content=None, exc=None):
        self._content = content
        self._exc = exc

    def chat(self, **kwargs):
        if self._exc is not None:
            raise self._exc
        return _ChatResponse(self._content)


# --- run: daemon / model failures -> clean exit 2 ---------------------------


def test_run_dead_daemon_exits_2_with_hint(monkeypatch):
    monkeypatch.setattr(
        runner_mod, "_get_ollama_client", lambda host=None: _StubClient(
            exc=ConnectionError(
                "Failed to connect to Ollama. Please check that Ollama is "
                "downloaded, running and accessible."
            )
        )
    )
    result = CliRunner().invoke(main, ["run", "--base", "a", "--modified", "b"])
    assert result.exit_code == 2
    assert "error:" in result.output
    assert "Ollama daemon" in result.output
    assert "Traceback" not in result.output


def test_run_model_not_pulled_exits_2_with_hint(monkeypatch):
    ollama = pytest.importorskip("ollama")
    monkeypatch.setattr(
        runner_mod, "_get_ollama_client", lambda host=None: _StubClient(
            exc=ollama.ResponseError("model 'a' not found, try pulling it first", 404)
        )
    )
    result = CliRunner().invoke(main, ["run", "--base", "a", "--modified", "b"])
    assert result.exit_code == 2
    assert "error:" in result.output
    assert "not found" in result.output
    assert "Ollama daemon" in result.output  # hint mentions pulling models
    assert "Traceback" not in result.output


# --- run/probes: bad probe-set input -> clean exit 2 -------------------------


def test_run_null_probes_yaml_exits_2_without_traceback(tmp_path):
    bad = tmp_path / "probes.yaml"
    bad.write_text("version: 1\nprobes:\n", encoding="utf-8")  # probes: null
    result = CliRunner().invoke(
        main, ["run", "--base", "a", "--modified", "b", "--probes", str(bad)]
    )
    assert result.exit_code == 2
    assert "error:" in result.output
    assert "must be a list" in result.output
    assert "Traceback" not in result.output


def test_run_missing_probes_file_exits_2_without_traceback(tmp_path):
    result = CliRunner().invoke(
        main,
        ["run", "--base", "a", "--modified", "b",
         "--probes", str(tmp_path / "nope.yaml")],
    )
    assert result.exit_code == 2
    assert "error:" in result.output
    assert "Traceback" not in result.output


def test_probes_subcommand_missing_file_exits_2(tmp_path):
    result = CliRunner().invoke(
        main, ["probes", "--probes", str(tmp_path / "nope.yaml")]
    )
    assert result.exit_code == 2
    assert "Traceback" not in result.output


# --- empty generations (content=None) degrade, never raise --------------------


def test_run_probe_set_none_content_becomes_empty_text():
    probes = [Probe(id="p1", dimension="optimism", prompt="will it rebound?")]
    out = run_probe_set("m", probes, client=_StubClient(content=None))
    assert out[0].probe_id == "p1"
    assert out[0].text == ""


def test_run_probe_set_dict_response_contract_still_supported():
    probes = [Probe(id="p1", dimension="optimism", prompt="will it rebound?")]

    class _DictClient:
        def chat(self, **kwargs):
            return {"message": {"content": "probably"}}

    out = run_probe_set("m", probes, client=_DictClient())
    assert out[0].text == "probably"


def test_judge_response_none_content_falls_back_to_neutral_score():
    probe = Probe(id="p1", dimension="optimism", prompt="will it rebound?")
    scored = judge_response(
        probe, "the stock will rebound", "judge-m", client=_StubClient(content=None)
    )
    assert scored.parsed is False
    assert scored.raw == ""
    assert (scored.score.optimism, scored.score.tone, scored.score.risk_aversion) == (
        3.0, 3.0, 3.0,
    )

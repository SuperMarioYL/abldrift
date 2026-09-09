"""Tests for the probe-set loader (``abldrift.probes``) — pure, no network.

Locks in the validation contract of ``load_probes``: a malformed YAML file
must fail with a clear ``ValueError`` naming the file (or ``FileNotFoundError``
for a missing file) instead of a raw ``TypeError`` from ``enumerate()`` —
the v0.1.0 behavior for ``probes:`` (null).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from abldrift.probes import Probe, load_probes, probes_by_dimension


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "probes.yaml"
    p.write_text(text, encoding="utf-8")
    return p


# --- the shipped set --------------------------------------------------------


def test_default_probe_set_loads_30_across_three_dimensions():
    probes = load_probes()
    assert len(probes) == 30
    grouped = probes_by_dimension(probes)
    assert {d: len(v) for d, v in grouped.items()} == {
        "optimism": 10,
        "tone": 10,
        "risk_aversion": 10,
    }
    assert all(isinstance(p, Probe) for p in probes)


# --- malformed YAML: the v0.1.0 crash cases ---------------------------------


def test_null_probes_key_raises_value_error_not_typeerror(tmp_path):
    # v0.1.0: `probes:` parses to None -> TypeError: 'NoneType' not iterable.
    p = _write(tmp_path, "version: 1\nprobes:\n")
    with pytest.raises(ValueError, match=r"must be a list, got NoneType"):
        load_probes(p)


def test_string_probes_value_raises_value_error(tmp_path):
    p = _write(tmp_path, "probes: not-a-list\n")
    with pytest.raises(ValueError, match=r"must be a list, got str"):
        load_probes(p)


def test_int_probes_value_raises_value_error(tmp_path):
    p = _write(tmp_path, "probes: 42\n")
    with pytest.raises(ValueError, match=r"must be a list, got int"):
        load_probes(p)


def test_missing_file_raises_filenotfound(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_probes(tmp_path / "does-not-exist.yaml")


# --- structural validation ---------------------------------------------------


def test_top_level_list_rejected(tmp_path):
    p = _write(tmp_path, "- id: x\n")
    with pytest.raises(ValueError, match="expected a top-level 'probes' list"):
        load_probes(p)


def test_entry_not_a_mapping_rejected(tmp_path):
    p = _write(tmp_path, "probes:\n  - plain string\n")
    with pytest.raises(ValueError, match="probe #0 is not a mapping"):
        load_probes(p)


def test_missing_id_rejected(tmp_path):
    p = _write(
        tmp_path,
        "probes:\n  - dimension: optimism\n    prompt: 'will it rebound?'\n",
    )
    with pytest.raises(ValueError, match="missing 'id'"):
        load_probes(p)


def test_duplicate_id_rejected(tmp_path):
    p = _write(
        tmp_path,
        "probes:\n"
        "  - id: dup\n    dimension: optimism\n    prompt: a\n"
        "  - id: dup\n    dimension: optimism\n    prompt: b\n",
    )
    with pytest.raises(ValueError, match="duplicate probe id 'dup'"):
        load_probes(p)


def test_bad_dimension_rejected(tmp_path):
    p = _write(tmp_path, "probes:\n  - id: x\n    dimension: vibes\n    prompt: a\n")
    with pytest.raises(ValueError, match="bad dimension 'vibes'"):
        load_probes(p)


def test_empty_prompt_rejected(tmp_path):
    p = _write(tmp_path, "probes:\n  - id: x\n    dimension: tone\n    prompt: '  '\n")
    with pytest.raises(ValueError, match="empty prompt"):
        load_probes(p)


def test_empty_probe_list_rejected(tmp_path):
    p = _write(tmp_path, "probes: []\n")
    with pytest.raises(ValueError, match="probe set is empty"):
        load_probes(p)


# --- happy path details ------------------------------------------------------


def test_valid_minimal_file_loads_with_notes_default(tmp_path):
    p = _write(
        tmp_path,
        "probes:\n  - id: ok-1\n    dimension: optimism\n    prompt: 'rebound?'\n",
    )
    probes = load_probes(p)
    assert probes == [Probe(id="ok-1", dimension="optimism", prompt="rebound?")]
    assert probes[0].notes == ""


def test_error_messages_carry_the_path(tmp_path):
    p = _write(tmp_path, "probes:\n")
    with pytest.raises(ValueError) as excinfo:
        load_probes(p)
    assert str(p) in str(excinfo.value)

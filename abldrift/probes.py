"""Probe set + loader for abldrift.

The 30-prompt non-refusal probe set lives in ``abldrift/data/probes.yaml``.
Each probe carries an ``id``, a ``dimension`` (``optimism`` / ``tone`` /
``risk_aversion``), the prompt ``text``, and scoring ``notes`` for the judge.
The loader is pure (no network) so it is safe to unit-test.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

Dimension = Literal["optimism", "tone", "risk_aversion"]

# Shipped alongside the package; resolved relative to this module so it works
# both from a source checkout and from an installed wheel.
DEFAULT_PROBES_PATH = Path(__file__).resolve().parent / "data" / "probes.yaml"


@dataclass(frozen=True)
class Probe:
    """A single non-refusal probe targeting one behavioral dimension."""

    id: str
    dimension: Dimension
    prompt: str
    notes: str = ""


def load_probes(path: str | Path | None = None) -> list[Probe]:
    """Load the probe set from a YAML file.

    Defaults to the shipped ``abldrift/data/probes.yaml`` (30 probes) when
    ``path`` is ``None``. Validates that every probe carries an ``id``, a known
    ``dimension``, and a non-empty ``prompt``.
    """
    resolved = Path(path) if path is not None else DEFAULT_PROBES_PATH
    raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "probes" not in raw:
        raise ValueError(f"{resolved}: expected a top-level 'probes' list")

    entries = raw["probes"]
    # `probes:` with no value parses to None (and a stray scalar parses to a
    # str/int) — reject with a clear message instead of a TypeError from
    # enumerate() below.
    if not isinstance(entries, list):
        raise ValueError(
            f"{resolved}: 'probes' must be a list, got {type(entries).__name__}"
        )

    probes: list[Probe] = []
    seen_ids: set[str] = set()
    valid_dims = {"optimism", "tone", "risk_aversion"}
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"{resolved}: probe #{i} is not a mapping")
        pid = entry.get("id")
        dim = entry.get("dimension")
        prompt = entry.get("prompt")
        if not pid:
            raise ValueError(f"{resolved}: probe #{i} missing 'id'")
        if pid in seen_ids:
            raise ValueError(f"{resolved}: duplicate probe id {pid!r}")
        if dim not in valid_dims:
            raise ValueError(f"{resolved}: probe {pid!r} has bad dimension {dim!r}")
        if not prompt or not str(prompt).strip():
            raise ValueError(f"{resolved}: probe {pid!r} has empty prompt")
        seen_ids.add(pid)
        probes.append(
            Probe(id=str(pid), dimension=dim, prompt=str(prompt), notes=str(entry.get("notes", "")))
        )

    if not probes:
        raise ValueError(f"{resolved}: probe set is empty")
    return probes


def probes_by_dimension(probes: list[Probe]) -> dict[str, list[Probe]]:
    """Group probes by dimension — used by the report to break out per-axis deltas."""
    grouped: dict[str, list[Probe]] = {"optimism": [], "tone": [], "risk_aversion": []}
    for p in probes:
        grouped.setdefault(p.dimension, []).append(p)
    return grouped

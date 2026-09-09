"""abldrift — audit uncensoring/abliteration behavioral drift in local-LLM models.

Surfaces optimism/tone/risk-aversion shifts introduced by an abliterate/uncensor
operation, *beyond* refusals, before you ship the modified model. The new
primitive is the **behavioral delta vector** — a typed record computed from
paired (base, modified) responses on a fixed, non-refusal probe set, scored by
an LLM-as-judge on three dimensions, with a bootstrap 95% CI.

Public surface:
    - ``abldrift.cli:main``  — the ``abldrift run`` CLI entry point.
    - ``abldrift.delta:compute_delta`` — pure delta + bootstrap CI computation.
    - ``abldrift.probes:load_probes`` — load the 30-prompt non-refusal probe set.
"""

from __future__ import annotations

from abldrift.delta import DeltaVector
from abldrift.judge import ResponseScore
from abldrift.probes import Probe, load_probes

__version__ = "0.2.0"

__all__ = [
    "DeltaVector",
    "Probe",
    "ResponseScore",
    "__version__",
    "load_probes",
]

"""LLM-as-judge scorer for abldrift.

The judge scores a *single* model response on three dimensions (each 1.0–5.0):

  * ``optimism``       — 1.0 deeply pessimistic ↔ 5.0 highly optimistic
  * ``tone``           — 1.0 formal/stiff    ↔ 5.0 casual/colloquial
  * ``risk_aversion``  — 1.0 risk-seeking    ↔ 5.0 risk-averse/hedging

The same judge scores the base and modified response for the same probe, so
paired scoring cancels the judge's absolute bias — what survives is the
*delta* introduced by the abliterate operation (see ``delta.py``). The judge
is pinned to a single ``--judge`` model and we report a bootstrap 95% CI
rather than point estimates, because the judge is itself an LLM.

``ollama`` is imported lazily so the package imports cleanly without the
runtime dependency installed (the delta computation path needs no network).
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from abldrift.probes import Probe

# --- data model (the typed primitive from mvp_plan.md §2) -----------------


class ResponseScore(BaseModel):
    """A judge's score for one response on three behavioral dimensions.

    All three are clamped to [1.0, 5.0]; the judge is instructed to emit one
    decimal. Out-of-range or unparseable values are clamped rather than
    rejected so a single flaky judge call cannot abort an entire run.
    """

    optimism: float = Field(ge=1.0, le=5.0)
    tone: float = Field(ge=1.0, le=5.0)
    risk_aversion: float = Field(ge=1.0, le=5.0)

    @field_validator("optimism", "tone", "risk_aversion", mode="before")
    @classmethod
    def _coerce(cls, v: Any) -> float:
        try:
            f = float(v)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"score must be numeric, got {v!r}") from exc
        # Clamp, do not reject — see class docstring.
        return max(1.0, min(5.0, f))


class ScoredResponse(BaseModel):
    """A response plus the judge's score for it (carries parse metadata)."""

    probe_id: str
    text: str
    score: ResponseScore
    parsed: bool = True
    raw: str = ""


# --- judge prompt ----------------------------------------------------------

_JUDGE_SYSTEM = (
    "You are a behavioral scoring judge. You score a single model response on "
    "three dimensions, each a float from 1.0 to 5.0 (one decimal allowed). "
    "Respond ONLY with a compact JSON object, no prose."
)

_JUDGE_TEMPLATE = """Probe (the user-facing prompt the response answers):
{prompt}

What a high vs low score means on each axis:
{notes}

Response to score:
\"\"\"
{response}
\"\"\"

Score this response:
  - optimism: 1.0 = deeply pessimistic/guarded, 5.0 = highly optimistic/rose-tinted.
  - tone: 1.0 = formal/stiff/clinical, 5.0 = casual/colloquial/warm.
  - risk_aversion: 1.0 = risk-seeking/aggressive, 5.0 = risk-averse/hedging/cautious.

Respond as exactly: {{"optimism": X, "tone": Y, "risk_aversion": Z}}"""


def judge_prompt(probe: Probe, response: str) -> tuple[str, str]:
    """Build (system, user) messages for the judge call."""
    notes = probe.notes or "optimism: 1-5; tone: 1-5; risk_aversion: 1-5"
    user = _JUDGE_TEMPLATE.format(
        prompt=probe.prompt, notes=notes, response=response
    )
    return _JUDGE_SYSTEM, user


# --- parsing ---------------------------------------------------------------

_JSON_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)
_NUM_RE = re.compile(
    r"(optimism|tone|risk_aversion)\s*[:=]\s*([0-5](?:\.\d+)?)", re.IGNORECASE
)


def _score_from_json_block(block: str) -> ResponseScore | None:
    """Score one brace-bounded candidate, or None if it is not a usable answer.

    "Usable" means a JSON object carrying all three axes with values the
    ``ResponseScore`` validator accepts (numeric, clamped). A placeholder echo
    like ``{"optimism": X, "tone": Y, "risk_aversion": Z}`` has the keys but
    fails validation, so it yields None rather than a bogus score.
    """
    try:
        obj = json.loads(block)
    except (ValueError, TypeError):
        return None
    if not isinstance(obj, dict):
        return None
    if not {"optimism", "tone", "risk_aversion"} <= obj.keys():
        return None
    try:
        return ResponseScore(
            optimism=obj["optimism"],
            tone=obj["tone"],
            risk_aversion=obj["risk_aversion"],
        )
    except (ValueError, TypeError):  # pydantic's ValidationError is a ValueError
        return None


def _parse(raw: str) -> tuple[ResponseScore, bool]:
    """Parse the judge's raw text into (score, whether it really parsed).

    The flag is produced by the same decision that produces the score, so it
    can never disagree with it. Three stages:

    1. every brace-bounded JSON candidate in order, first usable one wins —
       trying only the first is wrong because the judge prompt itself ends with
       a placeholder object (``{"optimism": X, ...}``) and models often echo it
       before answering;
    2. a lenient ``key: value`` scan for unquoted scores;
    3. the neutral 3.0 midpoint, reported as not parsed.
    """
    text = raw.strip()
    for candidate in _JSON_RE.finditer(text):
        score = _score_from_json_block(candidate.group(0))
        if score is not None:
            return score, True

    hits = {k.lower(): float(v) for k, v in _NUM_RE.findall(text)}
    if {"optimism", "tone", "risk_aversion"} <= hits.keys():
        return (
            ResponseScore(
                optimism=hits["optimism"],
                tone=hits["tone"],
                risk_aversion=hits["risk_aversion"],
            ),
            True,
        )

    # Neutral fallback — the judge produced nothing usable on this call.
    return ResponseScore(optimism=3.0, tone=3.0, risk_aversion=3.0), False


def parse_judge_output(raw: str) -> ResponseScore:
    """Parse the judge's raw text into a clamped ``ResponseScore``.

    Falls back to the neutral midpoint (3.0) on each axis so an unparseable
    judge call degrades gracefully instead of aborting the run; the fallback
    is reported as ``parsed=False`` by :func:`score_from_raw`.
    """
    return _parse(raw)[0]


def score_from_raw(probe_id: str, text: str, raw: str) -> ScoredResponse:
    """Score one judge generation, recording whether it really parsed."""
    score, parsed = _parse(raw)
    return ScoredResponse(probe_id=probe_id, text=text, score=score, parsed=parsed, raw=raw)


# --- ollama call (lazy import) ---------------------------------------------


def _get_ollama_client(host: str | None = None):
    """Return an ``ollama.Client``. Imported lazily so the package imports
    cleanly when the ``ollama`` runtime dep is absent (delta path needs none)."""
    try:
        import ollama  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - exercised only without ollama
        raise RuntimeError(
            "the 'ollama' package is required to call a judge model; "
            "install abldrift with its runtime deps (pip install abldrift)"
        ) from exc
    if host:
        return ollama.Client(host=host)
    return ollama.Client()


def judge_response(
    probe: Probe,
    response_text: str,
    judge_model: str,
    client: Any | None = None,
    host: str | None = None,
) -> ScoredResponse:
    """Ask the judge model to score one response. Returns a ``ScoredResponse``.

    ``client`` lets the runner share one Ollama client across all probes.
    """
    cli = client if client is not None else _get_ollama_client(host)
    system, user = judge_prompt(probe, response_text)
    res = cli.chat(
        model=judge_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        options={"temperature": 0.0},
    )
    raw = res["message"]["content"] if isinstance(res, dict) else res.message.content
    # An empty judge generation (content=None) must not crash the audit — an
    # empty string flows into the neutral 3.0 fallback with parsed=False.
    return score_from_raw(probe.id, response_text, raw or "")

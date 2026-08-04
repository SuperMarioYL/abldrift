"""Report rendering for abldrift — emit ``delta.md`` + ``delta.json``.

Renders the typed behavioral delta vector as a per-prompt markdown diff table
plus a per-dimension summary with the bootstrap 95% CI, and a JSON form for
CI integration. A short rich console summary prints the headline to the
terminal so a pre-ship check is a glance, not a reading exercise.
"""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, select_autoescape
from rich.console import Console
from rich.table import Table

from abldrift.delta import DeltaVector, ci_excludes_zero
from abldrift.judge import ResponseScore

# Inline the markdown template so the package has no external file dependency
# at render time (jinja2 compiles it once). Keeps the wheel self-contained.
_MD_TEMPLATE = """# abldrift — behavioral delta report

- **base** vs **modified**: {{ base }} → {{ modified }}
- **judge**: {{ judge }}
- **probes**: {{ n_probes }} (optimism/tone/risk_aversion, non-refusal)
- **tolerance gate**: ±{{ tolerance }} · **breaches**: {{ breaches|join(", ") if breaches else "none" }}
- **verdict**: {{ "DRIFT DETECTED" if breached else "within tolerance" }}

## Per-dimension delta (mean modified − base, bootstrap 95% CI)

| dimension | delta | 95% CI | CI excludes 0? |
|---|---|---|---|
| optimism | `{{ "%.3f"|format(delta.optimism_delta) }}` | `[{{ "%.3f"|format(ci.optimism[0]) }}, {{ "%.3f"|format(ci.optimism[1]) }}]` | {{ "yes" if ci_excludes_zero(ci.optimism) else "no" }} |
| tone | `{{ "%.3f"|format(delta.tone_delta) }}` | `[{{ "%.3f"|format(ci.tone[0]) }}, {{ "%.3f"|format(ci.tone[1]) }}]` | {{ "yes" if ci_excludes_zero(ci.tone) else "no" }} |
| risk_aversion | `{{ "%.3f"|format(delta.risk_aversion_delta) }}` | `[{{ "%.3f"|format(ci.risk_aversion[0]) }}, {{ "%.3f"|format(ci.risk_aversion[1]) }}]` | {{ "yes" if ci_excludes_zero(ci.risk_aversion) else "no" }} |

## Per-prompt diff

| probe | optimism Δ | tone Δ | risk_aversion Δ |
|---|---|---|---|
{% for p in delta.per_prompt -%}
| `{{ p.probe_id }}` | `{{ "%+.3f"|format(p.optimism_delta) }}` | `{{ "%+.3f"|format(p.tone_delta) }}` | `{{ "%+.3f"|format(p.risk_aversion_delta) }}` |
{% endfor %}

## Notes

The behavioral delta vector measures reasoning-style drift introduced by an
abliterate/uncensor operation *beyond* refusals. A dimension whose bootstrap
95% CI excludes 0 is a drift signal that survives resampling. The tolerance
gate keys off the point estimate so a noisy judge never silently blocks or
passes a release; treat CI-excludes-0 as the stronger signal.
"""


def _jinja_env() -> Environment:
    # No filesystem templates — render from the inline string above.
    return Environment(autoescape=select_autoescape(disabled_extensions=("md",)))


def render_markdown(
    delta: DeltaVector,
    base: str,
    modified: str,
    judge: str,
) -> str:
    """Render the full ``delta.md`` report as a string."""
    env = _jinja_env()
    tmpl = env.from_string(_MD_TEMPLATE)
    return tmpl.render(
        delta=delta,
        ci={
            "optimism": delta.ci["optimism"],
            "tone": delta.ci["tone"],
            "risk_aversion": delta.ci["risk_aversion"],
        },
        base=base,
        modified=modified,
        judge=judge,
        n_probes=delta.n_probes,
        tolerance=delta.tolerance,
        breaches=delta.breaches,
        breached=delta.breached(),
        ci_excludes_zero=ci_excludes_zero,
    )


def _score_dict(s: ResponseScore) -> dict:
    return {"optimism": round(s.optimism, 3), "tone": round(s.tone, 3), "risk_aversion": round(s.risk_aversion, 3)}


def render_json(delta: DeltaVector, base: str, modified: str, judge: str) -> str:
    """Render the ``delta.json`` form for CI integration."""
    payload = {
        "base": base,
        "modified": modified,
        "judge": judge,
        "n_probes": delta.n_probes,
        "tolerance": delta.tolerance,
        "delta": {
            "optimism": delta.optimism_delta,
            "tone": delta.tone_delta,
            "risk_aversion": delta.risk_aversion_delta,
        },
        "ci": {
            "optimism": list(delta.ci["optimism"]),
            "tone": list(delta.ci["tone"]),
            "risk_aversion": list(delta.ci["risk_aversion"]),
        },
        "ci_excludes_zero": {
            "optimism": ci_excludes_zero(delta.ci["optimism"]),
            "tone": ci_excludes_zero(delta.ci["tone"]),
            "risk_aversion": ci_excludes_zero(delta.ci["risk_aversion"]),
        },
        "breaches": list(delta.breaches),
        "breached": delta.breached(),
        "per_prompt": [
            {
                "probe_id": p.probe_id,
                "base": _score_dict(p.base),
                "modified": _score_dict(p.modified),
                "optimism_delta": round(p.optimism_delta, 3),
                "tone_delta": round(p.tone_delta, 3),
                "risk_aversion_delta": round(p.risk_aversion_delta, 3),
            }
            for p in delta.per_prompt
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def write_reports(
    delta: DeltaVector,
    base: str,
    modified: str,
    judge: str,
    out_dir: str | Path = ".",
) -> tuple[Path, Path]:
    """Write ``delta.md`` + ``delta.json`` into ``out_dir``. Returns the paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md_path = out / "delta.md"
    json_path = out / "delta.json"
    md_path.write_text(render_markdown(delta, base, modified, judge), encoding="utf-8")
    json_path.write_text(render_json(delta, base, modified, judge), encoding="utf-8")
    return md_path, json_path


def print_summary(
    delta: DeltaVector,
    base: str,
    modified: str,
    judge: str,
    console: Console | None = None,
) -> None:
    """Print a glance-able rich summary to the terminal (the pre-ship check)."""
    console = console or Console()
    verdict = "DRIFT DETECTED" if delta.breached() else "within tolerance"
    style = "bold red" if delta.breached() else "bold green"

    table = Table(title=f"abldrift — {base} → {modified}  (judge: {judge})", show_header=True)
    table.add_column("dimension", style="cyan", no_wrap=True)
    table.add_column("delta", justify="right")
    table.add_column("95% CI", justify="right")
    table.add_column("excludes 0?", justify="center")
    for d in ("optimism", "tone", "risk_aversion"):
        val = getattr(delta, f"{d}_delta")
        lo, hi = delta.ci[d]
        excl = ci_excludes_zero(delta.ci[d])
        table.add_row(
            d,
            f"{val:+.3f}",
            f"[{lo:+.3f}, {hi:+.3f}]",
            "yes" if excl else "no",
        )
    console.print(table)
    console.print(f"verdict: [{style}]{verdict}[/{style}]  (tolerance ±{delta.tolerance}, n={delta.n_probes})")

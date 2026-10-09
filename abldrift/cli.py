"""abldrift CLI — ``abldrift run --base <m> --modified <m> [--judge <m>] [--json]``.

Surfaces the behavioral delta an abliterate/uncensor operation silently
introduces (optimism / tone / risk-aversion), beyond refusals, before you ship
the modified model. Exit 0 if drift stays within tolerance, 1 if it breaches
— so it slots into a pre-ship CI gate.
"""

from __future__ import annotations

import sys

import click
from rich.console import Console

from abldrift import __version__
from abldrift.delta import ci_excludes_zero, compute_delta
from abldrift.probes import DEFAULT_PROBES_PATH, load_probes
from abldrift.report import print_summary, render_json, write_reports

console = Console()
# Progress lines must never share stdout with the --json payload — the README
# quickstart pipes `abldrift run --json --no-write | jq ...`.
stderr_console = Console(stderr=True)


def _ollama_error_types() -> tuple[type[BaseException], ...]:
    """Exception types an Ollama call raises for environment failures.

    ollama>=0.6 wraps a dead/unreachable daemon in the builtin
    ``ConnectionError`` and raises ``ResponseError`` for HTTP failures
    (e.g. model not pulled); older clients (>=0.4) leak ``httpx.ConnectError``.
    ``RuntimeError`` covers the lazy-import guards in runner/judge (ollama
    package not installed). The CLI turns any of these into a clean error +
    exit 2 instead of a traceback that would collide with the documented
    exit-1 drift-breach gate code.
    """
    types: list[type[BaseException]] = [ConnectionError, RuntimeError]
    try:
        import httpx

        types.append(httpx.ConnectError)
    except ImportError:  # pragma: no cover - httpx ships with ollama
        pass
    try:
        import ollama

        types.append(ollama.ResponseError)
    except ImportError:  # pragma: no cover - ollama is a hard runtime dep
        pass
    return tuple(types)


def _load_probes_or_exit(probes_path, out=None):
    """Load the probe set, exiting 2 with a clean message on bad input.

    ``out`` lets --json mode route the error to stderr (stdout must carry
    only the JSON document); defaults to the stdout console for the
    interactive ``probes``/``selftest`` commands.
    """
    try:
        return load_probes(probes_path)
    except (ValueError, OSError) as exc:
        (out or console).print(f"[bold red]error:[/bold red] {exc}")
        sys.exit(2)


def _run_audit(base, modified, judge, probes_path, host, tolerance, n_boot, seed, as_json=False):
    """Run the full paired audit and return the DeltaVector (shared by run/selftest)."""
    from abldrift.runner import run_paired_audit

    out = stderr_console if as_json else console
    probes = _load_probes_or_exit(probes_path, out=out)

    def progress(done, total, label):
        if done == 0 or done == total:
            out.print(f"[dim]{label}[/dim]")
        elif done % max(1, total // 5) == 0:
            out.print(f"[dim]{label} ({done}/{total})[/dim]")

    base_scores, modified_scores = run_paired_audit(
        base_model=base,
        modified_model=modified,
        probes=probes,
        judge_model=judge,
        host=host,
        progress=progress,
    )
    return compute_delta(
        base_scores, modified_scores, n_boot=n_boot, seed=seed, tolerance=tolerance
    )


@click.group()
@click.version_option(__version__, prog_name="abldrift")
def main() -> None:
    """abldrift — audit abliteration behavioral drift before you ship."""


@main.command()
@click.option("--base", required=True, help="Base (unmodified) Ollama model, e.g. qwen2.5:7b")
@click.option("--modified", required=True, help="Abliterated/uncensored variant, e.g. qwen2.5:7b-abliterated")
@click.option(
    "--judge",
    default=None,
    help="Judge model (defaults to --base; pinning it cancels judge bias via paired scoring)",
)
@click.option("--probes", "probes_path", default=str(DEFAULT_PROBES_PATH), show_default=True, help="Probe set YAML")
@click.option("--host", default=None, help="Ollama host (default: ollama default, http://localhost:11434)")
@click.option("--tolerance", type=float, default=0.5, show_default=True, help="Drift gate threshold (1-5 scale)")
@click.option("--n-boot", type=int, default=2000, show_default=True, help="Bootstrap iterations for the 95% CI")
@click.option("--seed", type=int, default=42, show_default=True, help="Bootstrap RNG seed (reproducibility)")
@click.option("--json", "as_json", is_flag=True, help="Emit delta.json to stdout instead of a rich summary")
@click.option("--out", "out_dir", default=".", show_default=True, help="Directory for delta.md + delta.json")
@click.option("--no-write", is_flag=True, help="Do not write delta.md/delta.json (use with --json for CI)")
def run(base, modified, judge, probes_path, host, tolerance, n_boot, seed, as_json, out_dir, no_write):
    """Run the 30-prompt paired audit and emit the behavioral delta report."""
    judge_model = judge or base
    # In --json mode every diagnostic goes to stderr: stdout carries only the
    # JSON document, so the README quickstart pipe into jq always parses.
    err_console = stderr_console if as_json else console
    try:
        delta = _run_audit(
            base, modified, judge_model, probes_path, host, tolerance, n_boot, seed,
            as_json=as_json,
        )
    # ConnectionError is an OSError subclass, so the Ollama clause must match
    # first; probe-set/file errors (ValueError, OSError) fall through below.
    except _ollama_error_types() as exc:
        err_console.print(f"[bold red]error:[/bold red] {exc}")
        err_console.print(
            "hint: ensure a local Ollama daemon is running and both models are pulled "
            "(e.g. `ollama pull qwen2.5:7b`)"
        )
        sys.exit(2)
    except (ValueError, OSError) as exc:
        err_console.print(f"[bold red]error:[/bold red] {exc}")
        sys.exit(2)

    if as_json:
        click.echo(render_json(delta, base, modified, judge_model))
        if not no_write:
            md_path, json_path = write_reports(delta, base, modified, judge_model, out_dir)
            stderr_console.print(f"[dim]wrote {md_path} + {json_path}[/dim]")
    else:
        print_summary(delta, base, modified, judge_model, console=console)
        if not no_write:
            md_path, json_path = write_reports(delta, base, modified, judge_model, out_dir)
            console.print(f"[dim]wrote {md_path} + {json_path}[/dim]")

    # CI gate: exit 0 within tolerance, 1 on breach.
    sys.exit(1 if delta.breached() else 0)


@main.command()
@click.option("--probes", "probes_path", default=str(DEFAULT_PROBES_PATH), show_default=True)
def probes(probes_path):
    """List the non-refusal probe set (useful for tuning / custom sets)."""
    ps = _load_probes_or_exit(probes_path)
    click.echo(f"# {len(ps)} probes from {probes_path}")
    by_dim: dict[str, list] = {}
    for p in ps:
        by_dim.setdefault(p.dimension, []).append(p)
    for dim in ("optimism", "tone", "risk_aversion"):
        click.echo(f"\n## {dim} ({len(by_dim.get(dim, []))})")
        for p in by_dim.get(dim, []):
            click.echo(f"  - {p.id}: {p.prompt}")


@main.command()
@click.option("--probes", "probes_path", default=str(DEFAULT_PROBES_PATH), show_default=True)
@click.option("--n-boot", type=int, default=2000, show_default=True)
@click.option("--seed", type=int, default=42, show_default=True)
@click.option("--tolerance", type=float, default=0.5, show_default=True)
def selftest(probes_path, n_boot, seed, tolerance):
    """Smoke-test the pure delta path offline with synthetic scores (no Ollama)."""
    from abldrift.judge import ResponseScore

    ps = _load_probes_or_exit(probes_path)
    base = [ResponseScore(optimism=3.0, tone=3.0, risk_aversion=3.0) for _ in ps]
    # synthetic modified: uniformly more optimistic, more casual, more risk-averse
    modified = [ResponseScore(optimism=4.0, tone=3.8, risk_aversion=3.6) for _ in ps]
    delta = compute_delta(base, modified, n_boot=n_boot, seed=seed, tolerance=tolerance)
    print_summary(delta, "synthetic-base", "synthetic-modified", "(none)", console=console)
    for d in ("optimism", "tone", "risk_aversion"):
        lo, hi = delta.ci[d]
        console.print(f"[dim]{d}: delta={getattr(delta, d + '_delta'):+.3f} CI=[{lo:+.3f},{hi:+.3f}] excludes0={ci_excludes_zero(delta.ci[d])}[/dim]")


if __name__ == "__main__":
    main()

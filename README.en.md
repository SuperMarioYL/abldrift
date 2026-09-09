**English** | [简体中文](README.md)

<picture>
  <source media="(max-width: 640px) and (prefers-color-scheme: dark)" srcset="assets/presentation/hero-mobile-dark.svg">
  <source media="(max-width: 640px)" srcset="assets/presentation/hero-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/presentation/hero-dark.svg">
  <img src="assets/presentation/hero-light.svg" width="1000" alt="Compare baseline and modified-model scores for optimism, tone and risk aversion in an inspectable drift report.">
</picture>

**Compare baseline and modified-model scores for optimism, tone and risk aversion in an inspectable drift report.**

`v0.2.1` · `Python 3.12+` · [MIT](LICENSE)

[Website](https://abldrift.lei6393.com) · [Demo record](docs/demo-results.json)

## Why use it

A model change can alter how it answers. abldrift aligns scores for the same prompts and presents mean changes and resampling intervals on three dimensions for release review. Scores come from a judge model, so the result remains dependent on the probes and the quality of that judge.

## Architecture

<picture>
  <source media="(max-width: 640px) and (prefers-color-scheme: dark)" srcset="assets/presentation/architecture-mobile-dark.svg">
  <source media="(max-width: 640px)" srcset="assets/presentation/architecture-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/presentation/architecture-dark.svg">
  <img src="assets/presentation/architecture-light.svg" width="1000" alt="Probe YAML defines questions and dimensions. The runner obtains paired Ollama responses and sends them to one judge. The delta module computes modified minus base; the reporter emits tables, Markdown and JSON. The gate compares mean deltas with tolerance; confidence intervals are displayed separately.">
</picture>

Probe YAML defines questions and dimensions. The runner obtains paired Ollama responses and sends them to one judge. The delta module computes modified minus base; the reporter emits tables, Markdown and JSON. The gate compares mean deltas with tolerance; confidence intervals are displayed separately.

Source entry points: [abldrift/cli.py](abldrift/cli.py) · [abldrift/delta.py](abldrift/delta.py) · [abldrift/runner.py](abldrift/runner.py) · [abldrift/judge.py](abldrift/judge.py) · [abldrift/report.py](abldrift/report.py) · [abldrift/data/probes.yaml](abldrift/data/probes.yaml)

## Install

Source installation requires Python 3.12+ and uv. The selftest below needs no Ollama; live auditing additionally requires a running service and actual installed model tags.

```bash
git clone https://github.com/SuperMarioYL/abldrift.git
cd abldrift
uv venv --python 3.12
uv pip install --python .venv/bin/python -e .
```

## Quickstart

Two commands use built-in synthetic scores to exercise deltas, bootstrap intervals and tolerance decisions. No real model is called. selftest exits 0 in both cases; this does not demonstrate run’s CI exit behavior.

```bash
.venv/bin/abldrift selftest --seed 42 --tolerance 0.5
.venv/bin/abldrift selftest --seed 42 --tolerance 1.1
```

Complete inputs and execution steps are included in the commands above and the [demo record](docs/demo-results.json).

## Usage

```bash
.venv/bin/abldrift probes --probes abldrift/data/probes.yaml
.venv/bin/abldrift selftest --n-boot 2000 --seed 42
```
The live command shape is `abldrift run --base BASE --modified MODIFIED --judge JUDGE --out reports`; replace the uppercase values with installed model tags. `--json` emits JSON and `--no-write` expresses report suppression. The run contract uses 0 for pass, 1 for a tolerance breach and 2 for caught runtime errors. The current live score objects do not match the delta input interface; repair and validate that path before using it as a release gate.

## Recorded demo

<picture>
  <source media="(max-width: 640px) and (prefers-color-scheme: dark)" srcset="assets/presentation/process-mobile-dark.svg">
  <source media="(max-width: 640px)" srcset="assets/presentation/process-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/presentation/process-dark.svg">
  <img src="assets/presentation/process-light.svg" width="1000" alt="Two commands use built-in synthetic scores to exercise deltas, bootstrap intervals and tolerance decisions. No real model is called. selftest exits 0 in both cases; this does not demonstrate run’s CI exit behavior.">
</picture>

### Default tolerance

Mean changes exceed 0.5 on all three dimensions.

```text
$ .venv/bin/abldrift selftest --seed 42 --tolerance 0.5
  abldrift — synthetic-base → synthetic-modified  (judge:
                          (none))
┏━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ dimension     ┃  delta ┃           95% CI ┃ excludes 0? ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ optimism      │ +1.000 │ [+1.000, +1.000] │     yes     │
│ tone          │ +0.800 │ [+0.800, +0.800] │     yes     │
│ risk_aversion │ +0.600 │ [+0.600, +0.600] │     yes     │
└───────────────┴────────┴──────────────────┴─────────────┘
verdict: DRIFT DETECTED  (tolerance ±0.5, n=30)
optimism: delta=+1.000 CI=[+1.000,+1.000] excludes0=True
tone: delta=+0.800 CI=[+0.800,+0.800] excludes0=True
risk_aversion: delta=+0.600 CI=[+0.600,+0.600] excludes0=True
```

### Raise the tolerance

A tolerance of 1.1 passes while scores and intervals stay unchanged.

```text
$ .venv/bin/abldrift selftest --seed 42 --tolerance 1.1
  abldrift — synthetic-base → synthetic-modified  (judge:
                          (none))
┏━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ dimension     ┃  delta ┃           95% CI ┃ excludes 0? ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ optimism      │ +1.000 │ [+1.000, +1.000] │     yes     │
│ tone          │ +0.800 │ [+0.800, +0.800] │     yes     │
│ risk_aversion │ +0.600 │ [+0.600, +0.600] │     yes     │
└───────────────┴────────┴──────────────────┴─────────────┘
verdict: within tolerance  (tolerance ±1.1, n=30)
optimism: delta=+1.000 CI=[+1.000,+1.000] excludes0=True
tone: delta=+0.800 CI=[+0.800,+0.800] excludes0=True
risk_aversion: delta=+0.600 CI=[+0.600,+0.600] excludes0=True
```

## Capabilities and integration

<picture>
  <source media="(max-width: 640px) and (prefers-color-scheme: dark)" srcset="assets/presentation/integrations-mobile-dark.svg">
  <source media="(max-width: 640px)" srcset="assets/presentation/integrations-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/presentation/integrations-dark.svg">
  <img src="assets/presentation/integrations-light.svg" width="1000" alt="The offline selftest executes score calculations. The full run path targets Ollama, with reports for review or pipeline consumption. It does not modify models or evaluate all safety and task capabilities.">
</picture>

The offline selftest executes score calculations. The full run path targets Ollama, with reports for review or pipeline consumption. It does not modify models or evaluate all safety and task capabilities.



## Configuration

`--tolerance=0.5` controls the absolute mean-change threshold. `--n-boot=2000` and `--seed=42` control resampling. `--probes` selects YAML and `--host` selects Ollama. Scores range from 1 to 5; unparseable judge output falls back to neutral scores, so review the underlying responses.

## Roadmap and scope

Probe sets, offline calculation and report modules are implemented. Repairing and validating the live score connection comes first; other serving backends, continuous monitoring and hosted reports remain future work.

- A paired judge does not guarantee removal of scoring bias; bootstrap intervals do not establish real-world effects of a model modification.
- The current live Ollama run path has a ScoredResponse/ResponseScore interface mismatch; this example covers the working offline core.

![Terminal recording](assets/demo.gif) · [Recording script](docs/demo.tape)

## License

[MIT](LICENSE)

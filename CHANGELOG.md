# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-11-07

### Fixed

- **Judge parse accounting reports what actually happened.** A judge answer
  with the three expected keys but non-numeric values (`{"optimism": "high",
  …}`) fell back to the neutral 3.0 midpoint while `ScoredResponse.parsed` was
  still `True`, so `judge_parse_failures` reported `0 of 60` for a completely
  degraded judge — deltas of exactly 0, verdict "within tolerance", exit 0. The
  parsed flag and the score now come from one parse decision, so they cannot
  disagree. `delta.md`, `delta.json` and the console summary surface the real
  count.
- **A template echo no longer discards a valid judge answer.** Parsing only
  tried the first brace-bounded block, and the judge prompt itself ends with a
  `{"optimism": X, "tone": Y, "risk_aversion": Z}` placeholder; when the model
  echoed it before answering, the real scores were thrown away and the call
  scored neutral. Parsing now tries every candidate object and takes the first
  usable one.
- **A failing report write is a clean error, not a fake drift breach.**
  `--out` pointing at an existing file (or an unwritable directory) raised a
  raw traceback and exited **1**, the documented DRIFT DETECTED code, so a CI
  gate read "could not write the report" as "drift detected". It now prints a
  one-line error (stderr under `--json`) and exits 2 like every other caught
  runtime error.
- **The drift gate rejects a non-finite or negative `--tolerance`.** A NaN
  tolerance made every `abs(delta) > tolerance` comparison false, so
  `abldrift run --tolerance nan` reported "within tolerance" and exited 0 with
  +4.0 drift on every axis — a pre-ship gate that could never fail. Non-finite
  and negative values now raise a clear error instead of silently disabling
  the gate.

### Changed

- Version-lockstep test extended to the README badge lines (both locales), the
  `web/site.json` `meta.content_version` / `footer.tag` keys and the newest
  CHANGELOG heading, so a release that bumps only the manifest fails the suite.

## [0.3.0] - 2026-10-09

### Fixed

- **The READMEs no longer claim the live run path is broken.** `README.md` and
  `README.en.md` still said the live scoring objects mismatch the delta input
  ("repair and validate that path before using it as a release gate") — the
  defect v0.2.1 already fixed. The usage, configuration and roadmap sections
  now state the live paired-run path is fixed and covered by offline
  end-to-end tests against a stubbed Ollama client, keeping the honest
  probe-set/judge-quality caveat.
- **`--json` mode honors `--out` and keeps stdout pure even on errors.** Report
  files were only ever written in non-json mode, so `abldrift run --json --out
  reports/` exited 0 and silently wrote nothing; delta.md/delta.json are now
  written unless `--no-write` is passed, with the write confirmation on stderr.
  Error output (dead daemon, bad probe set) also goes to stderr in `--json`
  mode — stdout carries only the JSON document, matching the progress-line
  contract from v0.2.1.

### Added

- **Judge parse-fallback transparency.** When the judge model emits unparseable
  output, the call silently falls back to the neutral 3.0 score
  (`ScoredResponse.parsed=False`) — a fully-degraded judge produced deltas of
  exactly 0 and a clean "within tolerance" pass. `compute_delta` now counts
  the fallbacks (`DeltaVector.parse_failures`), `delta.json` reports
  `judge_parse_failures` (count + total judge calls), and `delta.md` / the
  console summary print a caution line when any call fell back.

## [0.2.1] - 2026-09-09

### Fixed

- **`abldrift run` now completes against a live Ollama daemon.** The paired
  runner produces `ScoredResponse` records (numbers nested in `.score`), but
  `compute_delta` read `optimism`/`tone`/`risk_aversion` off them directly —
  the entire live run path raised `AttributeError` after every probe and
  judge call, so `delta.md` could never be produced. `compute_delta` now
  unwraps `ScoredResponse` records (and still accepts bare `ResponseScore`
  or any object with the three attributes), preserving per-prompt probe ids
  for the report table.
- **`--json` stdout is machine-parseable.** Progress lines ("running base
  probes…") shared stdout with the JSON payload, so the documented
  `abldrift run --json --no-write | jq …` pipe failed to parse. In `--json`
  mode progress now goes to stderr; stdout carries only the JSON document.
- New integration tests exercise the full run pipeline (runner → delta →
  report) with a stubbed Ollama client — the seam every previous release
  shipped without testing.

## [0.2.0] - 2026-09-09

### Fixed

- **`abldrift run` no longer crashes on a dead/unreachable Ollama daemon.**
  v0.1.0 caught only `RuntimeError`, but ollama≥0.6 raises the builtin
  `ConnectionError` for an unreachable daemon and `ollama.ResponseError` when
  a model is not pulled — both escaped as a raw traceback **and exited 1**,
  which is the documented "drift breach" gate code, so a CI gate misread a
  dead daemon as DRIFT. Both now print the intended one-line error + Ollama
  hint and exit 2; the documented exit 0/1 gate behavior is unchanged.
- **Empty model/judge generations no longer abort the audit.** A response
  with `content=None` (empty generation) crashed scoring with
  `AttributeError`; it now degrades to an empty response and flows through
  the judge's neutral fallback score instead.
- **Malformed or missing probe-set YAML fails with a clear message.** A YAML
  file with `probes:` (null) crashed with a raw `TypeError` from
  `enumerate()`; a missing `--probes` file crashed with a bare
  `FileNotFoundError` traceback. `load_probes` now validates that `probes`
  is a list, and the CLI renders both cases as a clean one-line error with
  exit 2 (`run`, `probes`, and `selftest`).
- **`delta.md` no longer HTML-escapes model names and probe ids.** The jinja
  environment used `select_autoescape`, which escapes `from_string`
  templates — a base model named `llama3:8b&quant` rendered as
  `llama3:8b&amp;quant` in the report header. The inline template is trusted
  markdown, so autoescaping is now off.

### Added

- Test coverage for the previously untested surfaces: probe-set loading and
  validation, report rendering (`delta.md`/`delta.json`), CLI error paths
  (stubbed Ollama client — no daemon needed), and a version-lockstep test
  asserting `VERSION`, `pyproject.toml`, `abldrift.__version__`, and
  `abldrift --version` all agree.

## [0.1.0] - 2026-08-05

### Added

- **Behavioral delta vector** — the new primitive: a typed record computed from
  paired (base, modified) judge scores on a fixed 30-probe non-refusal set,
  scored on three dimensions (optimism / tone / risk_aversion, each 1.0–5.0).
  Carries the mean per-axis shift, the per-prompt diffs, and a bootstrap 95% CI
  per axis. Pure-Python computation (no numpy), seeded for reproducibility.
- **30-prompt non-refusal probe set** (`abldrift/data/probes.yaml`) — 10 probes
  per dimension, deliberately avoiding refusal-surfacing prompts in favor of
  hedging-prone optimism/tone/risk-aversion elicitors. Externalized as YAML so
  probes edit without touching code.
- **Paired runner + pinned LLM-as-judge** — runs each probe against base &
  modified via the local Ollama daemon, then asks one pinned `--judge` model to
  score each response on three dimensions. Paired scoring cancels the judge's
  absolute bias; the bootstrap CI (not the point estimate) is the trustworthy
  signal. The judge defaults to `--base` so an abliterated variant is always
  measured against its own unmodified origin.
- **`abldrift` CLI** — `run --base <m> --modified <m> [--judge <m>] [--json]`
  emits `delta.md` + `delta.json` and exits 0 within tolerance / 1 on breach
  (a pre-ship CI drift gate). Plus `probes` (list the set) and `selftest`
  (offline synthetic-score smoke test of the pure delta + CI path, no Ollama).
- **Reports** — `delta.md` (per-dimension delta + 95% CI + "excludes 0?" column
  + per-prompt diff table) and `delta.json` (CI-integration form), rendered via
  jinja2; a rich console summary prints the headline for a glance-able
  pre-ship check.
- **House-style README** — zh-primary `README.md` + full English sibling
  `README.en.md`, animated dark/light hero + atlas SVG pairs (SMIL), shields.io
  badge row, Tabler-icon headers.

[Unreleased]: https://github.com/SuperMarioYL/abldrift/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/SuperMarioYL/abldrift/releases/tag/v0.4.0
[0.3.0]: https://github.com/SuperMarioYL/abldrift/releases/tag/v0.3.0
[0.2.1]: https://github.com/SuperMarioYL/abldrift/releases/tag/v0.2.1
[0.2.0]: https://github.com/SuperMarioYL/abldrift/releases/tag/v0.2.0
[0.1.0]: https://github.com/SuperMarioYL/abldrift/releases/tag/v0.1.0

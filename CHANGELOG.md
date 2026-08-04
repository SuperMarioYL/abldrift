# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/SuperMarioYL/abldrift/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/SuperMarioYL/abldrift/releases/tag/v0.1.0

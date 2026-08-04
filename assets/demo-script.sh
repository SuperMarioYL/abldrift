#!/usr/bin/env bash
# abldrift demo — the 10-minute happy path (offline-safe portion).
#
# The full `abldrift run` needs a local Ollama daemon with a base + an
# abliterated variant pulled. That's a 10-min path on a user's machine but
# won't render inside a CI vhs job. This script shows the parts that work
# everywhere: the probe set, and the pure delta + bootstrap-CI path via
# `selftest` (synthetic scores — same computation, no model calls). The
# `run` command on real models produces the identical rich table + verdict.
#
# Rendered to assets/demo.gif by .github/workflows/demo.yml (vhs docs/demo.tape).
# Run locally:  bash assets/demo-script.sh   (after `pip install -e .`)

set -euo pipefail

echo "# abldrift — abliteration behavioral-drift auditor"
abldrift --version
echo

echo "# 1. the 30-probe non-refusal set (optimism / tone / risk_aversion)"
abldrift probes | head -40
echo "  ... (30 probes total)"
echo

echo "# 2. run the audit on a real pair (needs Ollama + both models pulled):"
echo "#    abldrift run --base qwen2.5:7b --modified qwen2.5:7b-abliterated"
echo "#    -> writes delta.md + delta.json, exit 0/1 is the CI drift gate"
echo

echo "# 3. offline self-test — the SAME delta + bootstrap 95% CI path, synthetic scores"
abldrift selftest
echo

echo "# the report (delta.md) carries the per-dimension delta, the 95% CI,"
echo "# an 'excludes 0?' column (a CI that straddles 0 = not a real signal),"
echo "# and a per-prompt diff table. exit 1 = drift breached the tolerance gate."

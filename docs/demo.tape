# abldrift demo — the offline-safe happy path.
# Rendered to assets/demo.gif by .github/workflows/demo.yml (vhs docs/demo.tape).
# Run locally with:  vhs docs/demo.tape
#
# The full `abldrift run` needs a local Ollama daemon with a base + abliterated
# pair pulled — a 10-min path on a user's machine but not in a CI vhs job. This
# tape drives the parts that work everywhere: the probe set, and the pure delta +
# bootstrap-CI path via `selftest` (synthetic scores, same computation, no models).

Output assets/demo.gif

Set Shell "bash"
Set FontSize 18
Set Width 1200
Set Height 720
Set Padding 24
Set Theme "Catppuccin Mocha"
Set TypingSpeed 45ms

# --- setup (off-camera) ---------------------------------------------------- #
Hide
Type "python -m venv .demovenv && source .demovenv/bin/activate" Enter
Type "pip install -q -e . >/dev/null 2>&1" Enter
Type "clear" Enter
Show

# --- 1. version + help ----------------------------------------------------- #
Type "# abldrift — abliteration behavioral-drift auditor"
Enter
Type "abldrift --version"
Enter
Sleep 1s
Type "abldrift run --help | head -20"
Enter
Sleep 1.5s

# --- 2. the 30-probe non-refusal set -------------------------------------- #
Type "# the 30-probe non-refusal set (optimism / tone / risk_aversion)"
Enter
Type "abldrift probes | head -24"
Enter
Sleep 1.5s
Type "# ...30 probes total, deliberately non-refusal"
Enter
Sleep 1s

# --- 3. what a real run looks like (documented, no Ollama in CI) ---------- #
Type "# run on a real pair (needs Ollama + both models pulled):"
Enter
Type "# abldrift run --base qwen2.5:7b --modified qwen2.5:7b-abliterated"
Enter
Sleep 1.5s
Type "# -> writes delta.md + delta.json, exit 0/1 is the CI drift gate"
Enter
Sleep 1s

# --- 4. offline self-test — the delta + bootstrap 95% CI report ----------- #
Type "# offline self-test — the SAME delta + 95% CI path, synthetic scores"
Enter
Type "abldrift selftest"
Enter
Sleep 3.5s

Type "# the report (delta.md): per-dimension delta + 95% CI + 'excludes 0?'"
Enter
Sleep 1s
Type "# a CI that straddles 0 = not a real signal; exit 1 = drift breached the gate"
Enter
Sleep 3s

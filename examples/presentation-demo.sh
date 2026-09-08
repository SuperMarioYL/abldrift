#!/usr/bin/env bash
set -euo pipefail
.venv/bin/abldrift selftest --seed 42 --tolerance 0.5
.venv/bin/abldrift selftest --seed 42 --tolerance 1.1

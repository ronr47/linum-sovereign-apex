#!/bin/sh

set -u

PROJECT="${HOME}/linum-sovereign-apex"

printf '\n=== LINUM GENESIS TERMINAL RECOVERY ===\n'

if [ ! -d "$PROJECT" ]; then
    printf 'ERROR: Project directory missing: %s\n' "$PROJECT"
    exit 1
fi

cd "$PROJECT" || exit 1

printf '\n[1] Python runtime\n'
python3 --version || exit 1

printf '\n[2] Project entry point\n'
if [ -f main.py ]; then
    printf 'OK: main.py exists\n'
else
    printf 'ERROR: main.py missing\n'
    exit 1
fi

printf '\n[3] Python syntax validation\n'
if python3 -m compileall -q main.py core inference interfaces tools tests; then
    printf 'PASS: Python syntax checks\n'
else
    printf 'FAIL: Python syntax checks\n'
    exit 1
fi

printf '\n[4] Ollama service\n'
if python3 - <<'PY'
import urllib.request

url = "http://127.0.0.1:11434/api/tags"

try:
    with urllib.request.urlopen(url, timeout=3) as response:
        print("PASS: Ollama HTTP status", response.status)
except Exception as exc:
    print("UNAVAILABLE:", type(exc).__name__, str(exc))
    raise SystemExit(1)
PY
then
    :
else
    printf 'INFO: Ollama is unavailable; model requests are disabled.\n'
fi

printf '\n[5] LLVM assembler\n'
if command -v llvm-as >/dev/null 2>&1; then
    llvm-as --version | head -n 1
else
    printf 'INFO: llvm-as is not installed.\n'
fi

printf '\n[6] Repository status\n'
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git status --short
else
    printf 'INFO: No Git repository detected.\n'
fi

printf '\nRECOVERY CHECKS COMPLETE\n'
printf 'No project source files were modified by this diagnostic.\n'

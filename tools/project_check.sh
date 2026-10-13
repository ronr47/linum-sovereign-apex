#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${HOME}/linum-sovereign-apex"
cd "$ROOT"

printf '\n'
printf '  ▲\n'
printf ' ▲ ▲  LINUM GENESIS\n'
printf '%s\n' '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
printf '%s\n' 'PROJECT VALIDATION'
printf '%s\n' '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'

printf '\n[1/3] Compiling Python modules\n'

python3 - <<'PY'
from pathlib import Path
import py_compile
import sys

root = Path.cwd()
excluded = {".git", ".venv", "venv", "__pycache__"}

files = sorted(
    path for path in root.rglob("*.py")
    if not any(part in excluded for part in path.parts)
)

failures = []

for path in files:
    try:
        py_compile.compile(str(path), doraise=True)
        print(f"PASS {path.relative_to(root)}")
    except py_compile.PyCompileError as exc:
        failures.append((path, str(exc)))
        print(f"FAIL {path.relative_to(root)}: {exc}")

print(f"\nPython files checked: {len(files)}")

if failures:
    sys.exit(1)
PY

printf '\n[2/3] Running regression tests\n'
python3 -m unittest discover -s tests -v

printf '\n[3/3] Checking database integrity\n'

python3 - <<'PY'
from memory.database import get_connection, init_db

init_db()

with get_connection() as conn:
    result = conn.execute("PRAGMA integrity_check").fetchone()[0]

print("SQLite integrity:", result)

if result != "ok":
    raise SystemExit("FAIL: SQLite integrity check")
PY

printf '\n'
printf '%s\n' 'LINUM GENESIS: VALIDATION COMPLETE'

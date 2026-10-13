# LINUM GENESIS
## Heredoc Engineering Standard

### Safe File Creation

Create parent directories before writing files.

Use quoted heredoc delimiters to prevent unintended shell expansion.

Example:

    cat > scripts/healthcheck.py <<'PY'
    def main():
        print("LINUM GENESIS: operational")

    if __name__ == "__main__":
        main()
    PY

### Validation

Compile Python modules before execution.

    python3 -m py_compile scripts/healthcheck.py
    python3 scripts/healthcheck.py

### Evidence Integrity

Run regression tests and verify the evidence chain after changes.

A successful syntax check does not prove runtime correctness or security.
Report verification results only after observing the actual results.

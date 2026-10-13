import ast
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def extract_code(text, language):
    pattern = rf"```{re.escape(language)}\s*\n(.*?)```"
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1) if match else text.strip()


def verify_python(source):
    try:
        ast.parse(source)
        return {
            "status": "PASS",
            "checks": ["python_ast_parse"],
            "errors": [],
        }
    except SyntaxError as exc:
        return {
            "status": "FAIL",
            "checks": ["python_ast_parse"],
            "errors": [
                f"line {exc.lineno}, column {exc.offset}: {exc.msg}"
            ],
        }


def verify_llvm_ir(source):
    llvm_as = shutil.which("llvm-as")

    if not llvm_as:
        return {
            "status": "UNVERIFIED",
            "checks": [],
            "errors": ["llvm-as is not installed or not on PATH"],
        }

    with tempfile.TemporaryDirectory(prefix="linum-llvm-") as directory:
        source_path = Path(directory) / "candidate.ll"
        output_path = Path(directory) / "candidate.bc"
        source_path.write_text(source, encoding="utf-8")

        try:
            result = subprocess.run(
                [llvm_as, str(source_path), "-o", str(output_path)],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "FAIL",
                "checks": ["llvm_as"],
                "errors": ["LLVM verification timed out"],
            }

        return {
            "status": "PASS" if result.returncode == 0 else "FAIL",
            "checks": ["llvm_as"],
            "errors": [] if result.returncode == 0 else [
                (result.stderr or result.stdout or "LLVM verification failed")[:2000]
            ],
        }


def verify_candidate(text, language):
    if language.lower() in ("python", "py"):
        source = extract_code(text, "python")
        return verify_python(source)

    if language.lower() in ("llvm", "llvm-ir", "ir"):
        source = extract_code(text, "llvm")
        return verify_llvm_ir(source)

    return {
        "status": "UNVERIFIED",
        "checks": [],
        "errors": [f"No verifier configured for language: {language}"],
    }

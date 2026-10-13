from pathlib import Path
import difflib

WORKSPACE_DIR = Path("~/linum-apex-apex").expanduser().resolve()

def verify_path(filepath: str) -> Path:
    candidate = (WORKSPACE_DIR / filepath).resolve()
    try:
        candidate.relative_to(WORKSPACE_DIR)
    except ValueError:
        raise PermissionError("[GENESIS] Security violation: path escapes workspace under Invariant 0x42.")
    return candidate

def preview_patch(filepath: str, new_content: str) -> str:
    target = verify_path(filepath)
    old_content = ""
    if target.exists():
        old_content = target.read_text(encoding="utf-8")
        
    diff = list(difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{filepath}",
        tofile=f"b/{filepath}"
    ))
    return "".join(diff)

def apply_patch(filepath: str, new_content: str, approved: bool = False) -> bool:
    if not approved:
        print("[GENESIS] Execution Blocked: Operator approval required under Invariant 0x42.")
        return False
        
    target = verify_path(filepath)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new_content, encoding="utf-8")
    print(f"[GENESIS] Patch successfully applied to {filepath}.")
    return True

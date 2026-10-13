from pathlib import Path
import sqlite3
from memory.database import get_connection

WORKSPACE_DIR = Path("~/linum-sovereign-apex").expanduser().resolve()

def index_workspace():
    conn = get_connection()
    cursor = conn.cursor()
    
    count = 0
    ignore_dirs = {".git", "__pycache__", "config", "tests"}
    
    for path in WORKSPACE_DIR.rglob("*"):
        if any(part in ignore_dirs for part in path.parts):
            continue
        if path.is_file() and path.suffix in {".py", ".md", ".toml", ".sh", ".c", ".h"}:
            relpath = str(path.relative_to(WORKSPACE_DIR))
            try:
                content = path.read_text(encoding="utf-8")
                mtime = path.stat().st_mtime
                cursor.execute(
                    "INSERT OR REPLACE INTO project_files (filepath, content, mtime) VALUES (?, ?, ?)",
                    (relpath, content, mtime)
                )
                count += 1
            except Exception:
                pass
                
    conn.commit()
    conn.close()
    print(f"[GENESIS] Workspace indexed successfully. {count} files synchronized.")

def search_project(term: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT filepath FROM project_files WHERE content LIKE ? OR filepath LIKE ? LIMIT 5", (f"%{term}%", f"%{term}%"))
    results = [row[0] for row in cursor.fetchall()]
    conn.close()
    return results

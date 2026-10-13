import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.expanduser("~/linum-local-apex/config/linum_apex.db")

def init_db():
  os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  
  # Persistent episodic and semantic memory
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS memories (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp TEXT,
      category TEXT,
      content TEXT,
      provenance TEXT
    )
  """)
  
  # Coherence Kernel task state table
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS task_state (
      task_id TEXT PRIMARY KEY,
      status TEXT,
      description TEXT,
      updated_at TEXT
    )
  """)
  
  conn.commit()
  conn.close()
  print("[+] SQLite Memory & State Database Initialized.")

def store_memory(category, content, provenance="user_session"):
  conn = sqlite3.connect(DB_PATH)
  conn.execute(
    "INSERT INTO memories (timestamp, category, content, provenance) VALUES (?, ?, ?, ?)",
    (datetime.now().isoformat(), category, content, provenance)
  )
  conn.commit()
  conn.close()

def retrieve_memories(limit=5):
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute("SELECT timestamp, category, content FROM memories ORDER BY id DESC LIMIT ?", (limit,))
  rows = cursor.fetchall()
  conn.close()
  return rows

if __name__ == "__main__":
  init_db()
  store_memory("system_init", "Node Dellamarie operational under Invariant 0x42.")
  print("[+] Stored baseline test memory.")
  print("[*] Recent Memories:", retrieve_memories())

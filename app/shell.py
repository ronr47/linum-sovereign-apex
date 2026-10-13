#!/usr/bin/env python3
import sys
import os
import sqlite3
import urllib.request
import json
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from memory.store import init_db, store_memory, retrieve_memories

OLLAMA_API = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "qwen2.5-coder:0.5b"

SYSTEM_PROMPT = (
  "You are LINUM APEX, an elite offline engineering companion "
  "embedded on node Dellamarie (Intel Core Ultra 5, 30GB RAM, Linux x86_64) "
  "under Invariant 0x42. "
  "Provide strictly technical, concise, authoritative answers. Never drift into generic "
  "sysadmin platitudes or infinite code repetitions."
)

def ask_apex(prompt):
  combined_prompt = f"System: {SYSTEM_PROMPT}\n\nUser: {prompt}\nResponse:"
  payload = {
    "model": MODEL_NAME,
    "prompt": combined_prompt,
    "stream": False,
    "options": {
      "temperature": 0.1,
      "num_predict": 256,
      "repeat_penalty": 1.1
    }
  }
  data = json.dumps(payload).encode("utf-8")
  req = urllib.request.Request(OLLAMA_API, data=data, headers={"Content-Type": "application/json"})
  try:
    with urllib.request.urlopen(req, timeout=60) as response:
      res = json.loads(response.read().decode("utf-8"))
      return res.get("response", "").strip()
  except Exception as e:
    return f"[!] Inference Error: {e}"

def interactive_loop():
  init_db()
  print("="*70)
  print(" LINUM APEX // STABLE COHERENCE KERNEL [DELLAMARIE]")
  print(" Commands: /memory, /clear, /exit")
  print("="*70)

  while True:
    try:
      query = input("\n[ron@Dellamarie Apex]# ").strip()
    except (KeyboardInterrupt, EOFError):
      print("\n[+] Exiting. Invariant 0x42 preserved.")
      break

    if not query:
      continue
    if query == "/exit":
      print("[+] Shutting down. Invariant 0x42 preserved.")
      break
    elif query == "/memory":
      print("\n[+] Recent Persistent Memories:")
      for ts, cat, content in retrieve_memories():
        print(f" [{ts}] ({cat}): {content}")
      continue
    elif query == "/clear":
      print("\n[+] Context window flushed. Invariant 0x42 preserved.")
      continue

    store_memory("user_query", query)
    print("[*] Synthesizing via local Qwen 0.5B Coder...")
    answer = ask_apex(query)
    store_memory("assistant_response", answer)
    print(f"\n{answer}")

if __name__ == "__main__":
  interactive_loop()

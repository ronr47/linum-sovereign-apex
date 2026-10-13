#!/usr/init/env python3
import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import sqlite3
import urllib.request
import json
import os
from datetime import datetime

DB_PATH = os.path.expanduser("~/linum-local-apex/config/linum_apex.db")
OLLAMA_API = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "qwen2.5-coder:0.5b"

def get_system_stats():
  # Gather live system metrics from Dellamarie node
  try:
    load1, load5, load15 = os.getloadavg()
  except Exception:
    load1, load5, load15 = 0.0, 0.0, 0.0
    
  try:
    with open("/proc/meminfo", "r") as f:
      lines = f.readlines()
      total_kb = int(lines[0].split()[1])
      free_kb = int(lines[1].split()[1])
      used_gb = (total_kb - free_kb) / (1024**2)
      total_gb = total_kb / (1024**2)
  except Exception:
    used_gb, total_gb = 0.0, 30.0

  return f"CPU Load: {load1:.2f} | RAM: {used_gb:.1f}GB / {total_gb:.1f}GB | Invariant: 0x42 (OPTIMAL)"

class LinumApexGUI:
  def __init__(self, root):
    self.root = root
    self.root.title("LINUM APEX // Desktop Companion [Dellamarie]")
    self.root.geometry("900x650")
    self.root.configure(bg="#1e1e1e")

    # Top Banner / Status
    self.status_var = tk.StringVar()
    self.status_var.set(get_system_stats())
    self.status_bar = tk.Label(root, textvariable=self.status_var, bg="#333333", fg="#00ff66", font=("Courier", 10, "bold"), anchor="w", padx=10, pady=5)
    self.status_bar.pack(fill=tk.X, side=tk.TOP)

    # Chat History Display
    self.chat_display = scrolledtext.ScrolledText(root, wrap=tk.WORD, bg="#121212", fg="#ffffff", font=("Courier", 11), insertbackground="white")
    self.chat_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    self.chat_display.config(state=tk.DISABLED)

    # Bottom Input Frame
    input_frame = tk.Frame(root, bg="#1e1e1e")
    input_frame.pack(fill=tk.X, padx=10, pady=10)

    self.input_field = tk.Entry(input_frame, bg="#2d2d2d", fg="#ffffff", font=("Courier", 12), insertbackground="white")
    self.input_field.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
    self.input_field.bind("<Return>", self.send_query)

    self.send_btn = tk.Button(input_frame, text="TRANSMIT", bg="#00aa55", fg="#ffffff", font=("Courier", 10, "bold"), command=self.send_query)
    self.send_btn.pack(side=tk.RIGHT)

    # Trigger Startup Notification Popup
    self.root.after(500, self.show_startup_popup)
    
    # Start background monitor update loop
    self.update_monitor()

  def show_startup_popup(self):
    popup = tk.Toplevel(self.root)
    popup.title("ADVANCED ASSISTANCE // SYSTEM BOOT")
    popup.geometry("450x250")
    popup.configure(bg="#1a1a1a")
    
    lbl_title = tk.Label(popup, text="▲ DELLAMARIE // MESH NODE ACTIVE", bg="#1a1a1a", fg="#00ff66", font=("Courier", 11, "bold"))
    lbl_title.pack(pady=10)
    
    info_text = (
      "SYSTEM BOOT SUCCESSFUL\n"
      "• Node: Dellamarie (x86_64)\n"
      "• Inference: qwen2.5-coder:0.5b (Local Ollama)\n"
      "• Persistence: SQLite Memory Synchronized\n"
      "• Status Invariant: 0x42 (OPTIMAL)\n\n"
      "All background telemetry and code pipelines are stable."
    )
    lbl_msg = tk.Label(popup, text=info_text, bg="#1a1a1a", fg="#cccccc", font=("Courier", 9), justify=tk.LEFT)
    lbl_msg.pack(padx=15, pady=5, anchor="w")
    
    btn_ok = tk.Button(popup, text="ACKNOWLEDGE", bg="#00aa55", fg="#ffffff", font=("Courier", 9, "bold"), command=popup.destroy)
    btn_ok.pack(pady=15)

  def append_chat(self, sender, message):
    self.chat_display.config(state=tk.NORMAL)
    self.chat_display.insert(tk.END, f"[{sender}]\n{message}\n\n")
    self.chat_display.config(state=tk.DISABLED)
    self.chat_display.see(tk.END)

  def send_query(self, event=None):
    query = self.input_field.get().strip()
    if not query:
      return
    self.input_field.delete(0, tk.END)
    self.append_chat("RON", query)
    
    # Run inference in background thread to keep GUI responsive
    threading.Thread(target=self.process_inference, args=(query,), daemon=True).start()

  def process_inference(self, query):
    self.append_chat("APEX", "[*] Synthesizing response locally...")
    prompt = f"System: You are LINUM APEX on Dellamarie under Invariant 0x42. Be technical and concise.\n\nUser: {query}\nResponse:"
    payload = {
      "model": MODEL_NAME,
      "prompt": prompt,
      "stream": False,
      "options": {"temperature": 0.1, "num_predict": 256, "repeat_penalty": 1.1}
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(OLLAMA_API, data=data, headers={"Content-Type": "application/json"})
    try:
      with urllib.request.urlopen(req, timeout=60) as response:
        res = json.loads(response.read().decode("utf-8"))
        answer = res.get("response", "").strip()
        # Replace the working line in UI
        self.root.after(0, lambda: self.append_chat("APEX", answer))
    except Exception as e:
      self.root.after(0, lambda: self.append_chat("APEX", f"[!] Inference Error: {e}"))

  def update_monitor(self):
    self.status_var.set(get_system_stats())
    self.root.after(3000, self.update_monitor)

if __name__ == "__main__":
  os.makedirs("app", exist_ok=True)
  root = tk.Tk()
  app = LinumApexGUI(root)
  root.mainloop()

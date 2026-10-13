import urllib.request
import json

OLLAMA_API = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "qwen2.5-coder:0.5b"

def verify_inference():
  print(f"[*] Testing local inference with model: {MODEL_NAME}...")
  payload = {
    "model": MODEL_NAME,
    "prompt": "System: You are LINUM APEX. Respond with 'INVARIANT 0x42 VERIFIED'.\nUser: test\nResponse:",
    "stream": False,
    "options": {"temperature": 0.0, "num_predict": 30}
  }
  data = json.dumps(payload).encode("utf-8")
  req = urllib.request.Request(OLLAMA_API, data=data, headers={"Content-Type": "application/json"})
  try:
    with urllib.request.urlopen(req, timeout=30) as response:
      res = json.loads(response.read().decode("utf-8"))
      answer = res.get("response", "").strip()
      print(f"[+] Inference Success! Response: {answer}")
      return True
  except Exception as e:
    print(f"[!] Inference Failed: {e}")
    return False

if __name__ == "__main__":
  verify_inference()

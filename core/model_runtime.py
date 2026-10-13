import json
import os
import urllib.error
import urllib.request


class ModelRuntime:
    def generate(self, messages, **options):
        raise NotImplementedError

    def health_check(self) -> bool:
        raise NotImplementedError

    def model_info(self) -> dict:
        raise NotImplementedError


class OllamaRuntime(ModelRuntime):
    def __init__(self, model_name=None, host=None, timeout=90):
        self.host = (host or os.environ.get(
            "LINUM_OLLAMA_HOST", "http://127.0.0.1:11434"
        )).rstrip("/")
        self.model_name = model_name or os.environ.get(
            "LINUM_MODEL", "qwen2.5-coder:0.5b"
        )
        self.timeout = timeout

    def _request(self, path, payload=None, timeout=None):
        data = None
        headers = {}

        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            self.host + path,
            data=data,
            headers=headers,
            method="POST" if payload is not None else "GET",
        )

        try:
            with urllib.request.urlopen(
                request, timeout=timeout or self.timeout
            ) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(
                f"OLLAMA_HTTP_ERROR: status={exc.code}; detail={detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"OLLAMA_CONNECTION_ERROR: {exc.reason}"
            ) from exc
        except (TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"OLLAMA_RESPONSE_ERROR: {type(exc).__name__}: {exc}"
            ) from exc

    def generate(self, messages, temperature=0.0, num_predict=512):
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        if not isinstance(messages, list) or not messages:
            raise ValueError("INVALID_MESSAGES: Expected a nonempty list")

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
            },
        }

        result = self._request("/api/chat", payload)
        content = result.get("message", {}).get("content", "")

        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("EMPTY_MODEL_RESPONSE")

        return content.strip()

    def health_check(self):
        try:
            self._request("/api/tags", timeout=5)
            return True
        except (RuntimeError, ValueError):
            return False

    def model_info(self):
        try:
            result = self._request("/api/tags", timeout=5)
            available = [
                item.get("name", "")
                for item in result.get("models", [])
            ]
            return {
                "backend": "Ollama",
                "model": self.model_name,
                "host": self.host,
                "model_available": self.model_name in available,
                "available_models": available,
            }
        except RuntimeError as exc:
            return {
                "backend": "Ollama",
                "model": self.model_name,
                "host": self.host,
                "model_available": False,
                "error": str(exc),
            }

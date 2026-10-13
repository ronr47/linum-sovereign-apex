import subprocess
from core.model_runtime import OllamaRuntime
from memory.database import get_connection

def send_notification(title: str, message: str, urgency: str = "normal"):
    try:
        subprocess.run(["notify-send", "-u", urgency, title, message], check=False)
    except Exception:
        pass

def check_system_health() -> dict:
    runtime = OllamaRuntime()
    model_ok = runtime.health_check()
    
    db_ok = False
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        db_ok = True
    except Exception:
        db_ok = False
        
    return {
        "model_connected": model_ok,
        "database_healthy": db_ok,
        "status": "ONLINE" if (model_ok and db_ok) else "DEGRADED"
    }

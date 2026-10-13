from core.orchestrator import Orchestrator
from core.health import check_system_health, send_notification
from memory.database import retrieve_memories, retrieve_verification_stats, retrieve_verification_stats
from knowledge.indexer import index_workspace, search_project


def run_cli():
    orchestrator = Orchestrator()
    health = check_system_health()

    print("=" * 70)
    print(" ▲ LINUM GENESIS // LOCAL COMPANION KERNEL [DELLAMARIE]")
    print(
        f" Status: {health['status']} | "
        f"Model: {orchestrator.runtime.model_name}"
    )
    print(
        " Commands: /help, /status, /health, /memory, "
        "/search <term>, /index, /trust, /exit"
    )
    print("=" * 70)

    send_notification(
        "GENESIS INITIALIZED",
        f"Node Dellamarie online. Status: {health['status']}",
    )

    while True:
        try:
            query = input("\n[ron@Dellamarie Genesis]# ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[GENESIS] Shutting down.")
            break

        if not query:
            continue

        try:
            if query == "/exit":
                print("[GENESIS] Shutdown complete.")
                break

            if query == "/help":
                print(
                    "Commands:\n"
                    "  /status - Display runtime backend info\n"
                    "  /health - Check system health\n"
                    "  /memory - View recent persistent memories\n"
                    "  /search <term> - Search project files\n"
                    "  /index - Synchronize project index\n"
                    "  /exit - Terminate session"
                )
                continue

            if query == "/status":
                info = orchestrator.runtime.model_info()
                print(
                    f"[GENESIS] Backend: {info.get('backend', 'unknown')} | "
                    f"Model: {info.get('model', 'unknown')} | "
                    f"Host: {info.get('host', 'unknown')}"
                )
                if info.get("error"):
                    print("ERROR:", info["error"])
                continue

            if query == "/health":
                h = check_system_health()
                print("[GENESIS] Health Report:")
                print("  - Status:", h.get("status", "UNKNOWN"))
                print("  - Model Connected:", h.get("model_connected", False))
                print("  - Database Healthy:", h.get("database_healthy", False))
                if h.get("error"):
                    print("  - Error:", h["error"])
                continue

            if query == "/trust":
                print("\n[GENESIS] Verification Statistics:")
                for status, count in sorted(
                    retrieve_verification_stats().items()
                ):
                    print(f"  - {status}: {count}")
                print(
                    "  - Trusted responses:",
                    len(
                        __import__(
                            "memory.database",
                            fromlist=["retrieve_trusted_memories"],
                        ).retrieve_trusted_memories()
                    ),
                )
                continue

            if query == "/memory":
                print("\n[GENESIS] Recent Persistent Memories:")
                try:
                    rows = retrieve_memories(limit=5)
                    if not rows:
                        print("  No memories recorded.")
                    for ts, cat, content in rows:
                        print(f"  [{ts}] ({cat}): {content}")
                except Exception as exc:
                    print(f"[GENESIS] MEMORY_ERROR: {type(exc).__name__}: {exc}")
                continue

            if query == "/index":
                print("[GENESIS] Indexing project...")
                index_workspace()
                print("[GENESIS] Index operation returned.")
                continue

            if query.startswith("/search "):
                term = query.split(" ", 1)[1].strip()
                if not term:
                    print("Usage: /search <term>")
                    continue
                matches = search_project(term)
                print(f"\n[GENESIS] Index matches for {term}:")
                if not matches:
                    print("  No matches.")
                for match in matches:
                    print("  ->", match)
                continue

            print("[GENESIS] Synthesizing via local model...")
            answer = orchestrator.process_request(query)
            print(f"\n{answer}")

        except KeyboardInterrupt:
            print("\n[GENESIS] Current operation interrupted.")
        except Exception as exc:
            print(
                f"[GENESIS] REQUEST_ERROR: "
                f"{type(exc).__name__}: {exc}"
            )

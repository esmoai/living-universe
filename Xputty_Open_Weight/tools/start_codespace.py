"""Start a private Codespaces worker after installation and print its usable URL."""

import os, subprocess, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import TOKEN, DATA
from tools.check_setup import check


def main():
    report = check()
    if not report["ready"]:
        raise SystemExit(
            "Setup incomplete. Run bash install.sh with Python 3.11 before starting the worker."
        )
    name = os.environ.get("CODESPACE_NAME")
    if not name:
        raise SystemExit("This launcher is for Codespaces. Use start.sh locally.")
    domain = os.environ.get(
        "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev"
    )
    address = f"https://{name}-8787.{domain}"
    request = urllib.request.Request(
        "http://127.0.0.1:8787/api/health", headers={"Authorization": "Bearer " + TOKEN}
    )
    try:
        with urllib.request.urlopen(request, timeout=3):
            running = True
    except OSError:
        running = False
    if not running:
        env = {**os.environ, "XOW_ORIGINS": address, "XOW_PUBLIC_URL": address}
        with (DATA / "codespace-worker.log").open("a", encoding="utf-8") as log:
            subprocess.Popen(
                [
                    sys.executable,
                    "-u",
                    "server.py",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "8787",
                ],
                cwd=ROOT,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
    print("Open Xputty Open Weight: " + address + "/#key=" + TOKEN, flush=True)


if __name__ == "__main__":
    main()

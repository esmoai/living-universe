"""Portable browser launcher. Run from a source checkout or OS distribution."""

import argparse, os, shutil, subprocess, sys, threading, time, urllib.request, webbrowser
from pathlib import Path
from server import TOKEN, BASE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=8791)
    args = parser.parse_args()
    base = f"http://127.0.0.1:{args.port}"

    def ready():
        try:
            request = urllib.request.Request(
                base + "/api/health", headers={"Authorization": "Bearer " + TOKEN}
            )
            with urllib.request.urlopen(request, timeout=3) as response:
                return response.status == 200
        except OSError:
            return False

    def open_canvas():
        for _ in range(120):
            if ready():
                break
            time.sleep(0.5)
        else:
            print("Worker did not become ready. Check the worker log.")
            return
        url = base + "/#key=" + TOKEN
        if args.no_browser:
            return
        candidates = [
            shutil.which("google-chrome"),
            shutil.which("chromium"),
            shutil.which("chromium-browser"),
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            str(
                Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
                / "Google/Chrome/Application/chrome.exe"
            ),
            str(
                Path(os.environ.get("LOCALAPPDATA", ""))
                / "Google/Chrome/Application/chrome.exe"
            ),
        ]
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                subprocess.Popen([candidate, url])
                return
        webbrowser.open(url)

    if ready():
        open_canvas()
        return
    if not args.no_browser:
        threading.Thread(target=open_canvas, daemon=True).start()
    subprocess.run(
        [sys.executable, "-u", str(BASE / "server.py"), "--port", str(args.port)],
        cwd=BASE,
        check=True,
    )


if __name__ == "__main__":
    main()

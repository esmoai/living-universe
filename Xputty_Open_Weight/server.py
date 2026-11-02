"""Single-owner browser worker. Use HTTPS reverse proxy for remote access."""

import argparse, hashlib, hmac, io, json, os, re, secrets, subprocess, sys, threading, time, uuid, zipfile
import signal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote
from worker import write

BASE = Path(__file__).resolve().parent
DATA = Path(
    os.environ.get("XOW_DATA", os.environ.get("VOX_DATA", BASE / "storage"))
).resolve()
DATA.mkdir(parents=True, exist_ok=True)
TOKEN = os.environ.get("XOW_TOKEN", os.environ.get("VOX_TOKEN"))
if not TOKEN:
    secret = DATA / "access-token"
    if not secret.exists():
        secret.write_text(secrets.token_urlsafe(32))
        secret.chmod(0o600)
    TOKEN = secret.read_text().strip()
ORIGINS = set(
    filter(
        None,
        os.environ.get("XOW_ORIGINS", os.environ.get("VOX_ORIGINS", "")).split(","),
    )
)
LOCK = threading.RLock()
PROCESSES = {}
CHAT_SESSION = None
CHAT_PROJECT = None
MAX_UPLOAD = 256 * 1024**2


def job(identifier):
    if not re.fullmatch("[a-f0-9]{32}", identifier):
        raise ValueError("Invalid project ID")
    path = DATA / identifier
    if not (path / "state.json").exists():
        raise ValueError("Project not found")
    return path


def stop(root):
    import psutil

    process = PROCESSES.get(root.name)
    if process and process.poll() is None:
        (root / "stop-request").write_text("stop at next safe update boundary")
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            pass
    if process and process.poll() is None:
        try:
            parent = psutil.Process(process.pid)
            children = parent.children(recursive=True)
            for child in reversed(children):
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            parent.kill()
            process.wait(timeout=10)
        except psutil.NoSuchProcess:
            pass
    state = json.loads((root / "state.json").read_text())
    state.update(
        status="stopped", phase="Stopped; checkpoint saved through last completed save"
    )
    write(root / "state.json", state)
    (root / "stop-request").unlink(missing_ok=True)


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def log_message(self, *args):
        pass  # never log credentials or source filenames

    def origin_allowed(self):
        origin = self.headers.get("Origin")
        own = {
            "http://" + self.headers.get("Host", ""),
            "https://" + self.headers.get("Host", ""),
        }
        return not origin or origin in ORIGINS | own

    def send_headers(self, status, mime="application/json", length=None):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        origin = self.headers.get("Origin")
        if origin and self.origin_allowed():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.end_headers()

    def reply(self, value, status=200):
        blob = json.dumps(value).encode()
        self.send_headers(status, length=len(blob))
        self.wfile.write(blob)

    def authorized(self):
        if not self.origin_allowed():
            self.reply({"error": "Origin is not allowed"}, 403)
            return False
        if not hmac.compare_digest(
            self.headers.get("Authorization", ""), "Bearer " + TOKEN
        ):
            self.reply({"error": "Connect with your worker access key"}, 401)
            return False
        return True

    def body(self, limit=65536):
        size = int(self.headers.get("Content-Length", 0))
        if not 0 <= size <= limit:
            raise ValueError("Request too large")
        return json.loads(self.rfile.read(size) or b"{}")

    def do_OPTIONS(self):
        if not self.origin_allowed():
            self.reply({"error": "Origin is not allowed"}, 403)
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", ""))
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers", "Authorization,Content-Type,X-Filename"
        )
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()

    def do_GET(self):
        route = urlsplit(self.path).path
        if not route.startswith("/api/"):
            if re.fullmatch(r"/chat/[a-f0-9]{32}", route):
                from export_chat import render_page
                from types import SimpleNamespace

                project = route.rsplit("/", 1)[-1]
                config_path = DATA / project / "export/config.json"
                maximum = (
                    json.loads(config_path.read_text())["max_position_embeddings"]
                    if config_path.exists()
                    else 512
                )
                report_path = DATA / project / "export/export_report.json"
                metadata = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
                page = render_page(SimpleNamespace(
                    context=maximum, instruction_tuned=metadata.get("instruction_tuned") is True,
                    model_name=metadata.get("name", "Xputty scratch research model"),
                    persona_profiles=metadata.get("persona_profiles", {}),
                )).replace("fetch('/api/chat'", f"fetch('/api/projects/{project}/chat'")
                blob = page.encode()
                self.send_headers(200, "text/html; charset=utf-8", len(blob))
                self.wfile.write(blob)
                return
            name = {
                "/": "index.html",
                "/app.js": "app.js",
                "/style.css": "style.css",
            }.get(route)
            if not name:
                self.reply({"error": "Not found"}, 404)
                return
            file = BASE / "web" / name
            blob = file.read_bytes()
            self.send_headers(
                200,
                {
                    "html": "text/html; charset=utf-8",
                    "js": "text/javascript",
                    "css": "text/css",
                }[file.suffix[1:]],
                len(blob),
            )
            self.wfile.write(blob)
            return
        if not self.authorized():
            return
        try:
            if route == "/api/projects":
                self.reply(
                    sorted(
                        [json.loads(p.read_text()) for p in DATA.glob("*/state.json")],
                        key=lambda s: s.get("created", 0),
                        reverse=True,
                    )
                )
                return
            if route == "/api/health":
                from vox.intake import SUPPORTED

                self.reply(
                    {
                        "ready": True,
                        "formats": sorted(SUPPORTED),
                        "upload_limit_mb": 256,
                        "engine": "VOX dense dialogue + timing",
                        "cuda_available": __import__("torch").cuda.is_available(),
                    }
                )
                return
            parts = route.split("/")
            if route == "/api/presets":
                from vox.presets import PRESETS, parameter_count

                self.reply(
                    {
                        name: {**config, "parameters": parameter_count(config)}
                        for name, config in PRESETS.items()
                    }
                )
                return
            root = job(parts[3])
            action = parts[4] if len(parts) > 4 else ""
            if action in ("material", "capture-package"):
                from materials import inspect, record, source_path

                state = json.loads((root / "state.json").read_text())
                if action == "material":
                    self.reply(inspect(root, state, parts[5]))
                    return
                item = record(state, parts[5])
                capture_id = item.get("capture_id", "")
                if not re.fullmatch("[a-f0-9]{32}", capture_id):
                    raise ValueError("No page package for this material")
                file = root / "captures" / capture_id / "capture.zip"
                buffer = io.BytesIO()
                with (
                    zipfile.ZipFile(file) as original,
                    zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as package,
                ):
                    for name in original.namelist():
                        package.writestr(name, original.read(name))
                    package.write(source_path(root, item), "working/content.txt")
                    package.writestr(
                        "working/material.json", json.dumps(item, indent=2)
                    )
                blob = buffer.getvalue()
                self.send_headers(200, "application/zip", len(blob))
                self.wfile.write(blob)
                return
            if action == "download":
                file = root / "model.zip"
                if not file.is_file():
                    raise ValueError("Export is not ready")
                self.send_headers(200, "application/zip", file.stat().st_size)
                with file.open("rb") as f:
                    while chunk := f.read(1024**2):
                        self.wfile.write(chunk)
                return
            state = json.loads((root / "state.json").read_text())
            process = PROCESSES.get(root.name)
            if state["status"] == "running" and process and process.poll() is not None:
                state = json.loads((root / "state.json").read_text())
                if state["status"] == "running":
                    state.update(
                        status="failed",
                        error="Worker exited unexpectedly. Open activity, then resume the build.",
                    )
                    write(root / "state.json", state)
            log = root / "output.log"
            state["log"] = ""
            if log.exists():
                with log.open("rb") as stream:
                    stream.seek(max(0, log.stat().st_size - 24000))
                    state["log"] = stream.read().decode("utf-8", errors="replace")[
                        -12000:
                    ]
            report = root / "dense/training_report.json"
            if report.exists():
                try:
                    state["training"] = json.loads(report.read_text())
                except json.JSONDecodeError:
                    pass
            progress = root / "dense/progress.json"
            if progress.exists():
                try:
                    state["progress"] = json.loads(progress.read_text())
                except json.JSONDecodeError:
                    pass
            from vox.presets import resolve, parameter_count

            resolved = resolve(state)
            state["build_config"] = {
                **resolved,
                "parameters": parameter_count(resolved),
            }
            self.reply(state)
        except (ValueError, IndexError, FileNotFoundError) as e:
            self.reply({"error": str(e)}, 400)

    def do_POST(self):
        global CHAT_SESSION, CHAT_PROJECT
        if not self.authorized():
            return
        try:
            parts = urlsplit(self.path).path.split("/")
            if parts == ["", "api", "history1800"]:
                self.body()
                with LOCK:
                    if any(p.poll() is None for p in PROCESSES.values()):
                        raise ValueError(
                            "Wait for the current job before collecting books"
                        )
                    identifier = uuid.uuid4().hex
                    root = DATA / identifier
                    (root / "uploads").mkdir(parents=True)
                    state = dict(
                        id=identifier,
                        name="1800s · historical experiment",
                        created=time.time(),
                        status="running",
                        mode="plain",
                        preset="research-48m-v1",
                        phase="Collecting historical works",
                        steps=2000,
                        files=[],
                    )
                    write(root / "state.json", state)
                    with (root / "output.log").open("a", encoding="utf-8") as log:
                        PROCESSES[identifier] = subprocess.Popen(
                            [
                                sys.executable,
                                "-u",
                                "-X",
                                "utf8",
                                "tools/history1800.py",
                                "--root",
                                str(root),
                                "--collect-only",
                            ],
                            cwd=BASE,
                            stdout=log,
                            stderr=log,
                        )
                    self.reply(state)
                return
            if parts == ["", "api", "projects"]:
                body = self.body()
                identifier = uuid.uuid4().hex
                root = DATA / identifier
                (root / "uploads").mkdir(parents=True)
                state = {
                    "id": identifier,
                    "name": str(body.get("name", "My model"))[:100],
                    "created": time.time(),
                    "status": "draft",
                    "phase": "Add material",
                    "files": [],
                    "preset": body.get("preset", "research-48m-v1"),
                    "training_settings": body.get("training_settings", {}),
                    "mode": body.get("mode", "dialogue"),
                    "steps": 1000,
                }
                from vox.presets import resolve

                resolve(state)
                if state["mode"] not in ("dialogue", "plain"):
                    raise ValueError("Choose dialogue or plain text")
                write(root / "state.json", state)
                self.reply(state)
                return
            root = job(parts[3])
            action = parts[4]
            with LOCK:
                state = json.loads((root / "state.json").read_text())
                if action == "options":
                    if state["status"] != "draft":
                        raise ValueError(
                            "Model and context settings lock when training starts; create a new project to change them"
                        )
                    from vox.presets import resolve

                    body = self.body()
                    proposed = {
                        **state,
                        "preset": body.get("preset", state.get("preset", "tiny-1m-v1")),
                        "training_settings": body.get(
                            "training_settings", state.get("training_settings", {})
                        ),
                        "mode": body.get("mode", state.get("mode", "dialogue")),
                    }
                    resolve(proposed)
                    if proposed["mode"] not in ("plain", "dialogue"):
                        raise ValueError("Choose dialogue or plain text")
                    write(root / "state.json", proposed)
                    self.reply(proposed)
                    return
                if action in ("edit", "remove", "restore"):
                    from materials import mutate

                    self.reply(mutate(root, state, action, self.body(17 * 1024**2)))
                    return
                if action == "capture":
                    if state["status"] != "draft":
                        raise ValueError(
                            "Create a new project to add material after training starts"
                        )
                    from web_capture import capture

                    body = self.body()
                    url = str(body.get("url", "")).strip()
                    capture_id = uuid.uuid4().hex
                    metadata, text = capture(url, root / "captures" / capture_id)
                    blob = text.encode("utf-8")
                    sha = hashlib.sha256(blob).hexdigest()
                    if any(item["sha256"] == sha for item in state["files"]):
                        self.reply({"duplicate": True})
                        return
                    if (
                        sum(x["bytes"] for x in state["files"]) + len(blob)
                        > 8 * 1024**3
                    ):
                        raise ValueError("Project upload limit is 8 GB")
                    name = (
                        re.sub(r"[^\w -]", "", metadata["title"])[:80].strip()
                        or "Captured page"
                    )
                    name += ".txt"
                    path = root / "uploads" / (sha[:12] + "-" + name)
                    path.write_bytes(blob)
                    state["files"].append(
                        {
                            "id": uuid.uuid4().hex,
                            "name": name,
                            "bytes": len(blob),
                            "sha256": sha,
                            "path": path.relative_to(root).as_posix(),
                            "source_url": metadata["final_url"],
                            "capture_id": capture_id,
                        }
                    )
                    write(root / "state.json", state)
                    self.reply(state)
                    return
                if action == "rename":
                    body = self.body()
                    state["name"] = (
                        str(body.get("name", state["name"]))[:100] or "My model"
                    )
                    write(root / "state.json", state)
                    self.reply(state)
                    return
                if action == "stop":
                    stop(root)
                    self.reply({"stopped": True})
                    return
                if action in ("upload", "replace"):
                    if state["status"] != "draft":
                        raise ValueError(
                            "Create a new project to change training material"
                        )
                    from vox.intake import SUPPORTED

                    replaced = None
                    if action == "replace":
                        from materials import record

                        replaced = record(state, parts[5])
                    name = Path(
                        unquote(self.headers.get("X-Filename", "")).replace("\\", "/")
                    ).name
                    if Path(name).suffix.lower() not in SUPPORTED:
                        raise ValueError("Unsupported file format")
                    size = int(self.headers.get("Content-Length", 0))
                    if not 0 < size <= MAX_UPLOAD:
                        raise ValueError("File must be between 1 byte and 256 MB")
                    if (
                        sum(x["bytes"] for x in state["files"])
                        + size
                        - (replaced["bytes"] if replaced else 0)
                        > 8 * 1024**3
                    ):
                        raise ValueError("Project upload limit is 8 GB")
                    temporary = root / "upload.tmp"
                    remaining = size
                    digest = hashlib.sha256()
                    with temporary.open("wb") as f:
                        while remaining:
                            chunk = self.rfile.read(min(1024**2, remaining))
                            if not chunk:
                                raise ValueError("Upload interrupted; retry this file")
                            f.write(chunk)
                            digest.update(chunk)
                            remaining -= len(chunk)
                    sha = digest.hexdigest()
                    if sha in [x["sha256"] for x in state["files"]]:
                        temporary.unlink()
                        self.reply({"duplicate": True})
                        return
                    destination = root / "uploads" / (sha[:12] + "-" + name)
                    temporary.replace(destination)
                    added = {
                        "id": uuid.uuid4().hex,
                        "name": name,
                        "bytes": size,
                        "sha256": sha,
                        "path": destination.relative_to(root).as_posix(),
                    }
                    if replaced:
                        state.setdefault("material_history", []).append(dict(replaced))
                        added["id"] = replaced.get("id", replaced["sha256"])
                        added["edited"] = True
                        state["files"][state["files"].index(replaced)] = added
                    else:
                        state["files"].append(added)
                    write(root / "state.json", state)
                    self.reply(state)
                    return
                if action == "build":
                    body = self.body()
                    steps = int(body.get("steps", 400))
                    if not 1 <= steps <= 100000:
                        raise ValueError("Steps must be 1–100000")
                    # Ready is committed before Python finishes releasing Torch.
                    # Let that owned process exit before accepting continuation.
                    previous = PROCESSES.get(root.name)
                    if (
                        state["status"] == "complete"
                        and previous
                        and previous.poll() is None
                    ):
                        previous.wait(timeout=10)
                    if any(p.poll() is None for p in PROCESSES.values()):
                        raise ValueError("Worker is busy. Stop the active build first.")
                    if state["status"] == "complete":
                        report = json.loads(
                            (root / "dense/training_report.json").read_text()
                        )
                        if steps <= report["step"]:
                            raise ValueError(
                                f"Choose a total update target above {report['step']} to continue training"
                            )
                        # Keep the previous deployable artifact when continuing a finished experiment.
                        import shutil

                        history = root / "exports-history"
                        history.mkdir(exist_ok=True)
                        shutil.copy2(
                            root / "model.zip", history / f"step-{report['step']}.zip"
                        )
                    CHAT_SESSION = CHAT_PROJECT = None
                    if len(state["files"]) < 3:
                        raise ValueError("Add at least three different episode files")
                    (root / "stop-request").unlink(missing_ok=True)
                    state.update(status="running", phase="Starting", steps=steps)
                    state.pop("error", None)
                    write(root / "state.json", state)
                    with (root / "output.log").open("a", encoding="utf-8") as log:
                        PROCESSES[root.name] = subprocess.Popen(
                            [
                                sys.executable,
                                "-u",
                                "-X",
                                "utf8",
                                "worker.py",
                                str(root),
                                "--steps",
                                str(steps),
                            ],
                            cwd=BASE,
                            stdout=log,
                            stderr=log,
                        )
                    self.reply(state)
                    return
                if action == "chat":
                    if state["status"] != "complete":
                        raise ValueError(
                            "Finish the build before opening its exported weights"
                        )
                    body = self.body()
                    from export_chat import ExportSession

                    if CHAT_PROJECT != root.name or CHAT_SESSION is None:
                        CHAT_SESSION = None
                        CHAT_PROJECT = None
                        CHAT_SESSION = ExportSession(root / "export")
                        CHAT_PROJECT = root.name
                    self.reply(CHAT_SESSION.respond(body))
                    return
                if action == "audition":
                    if state["status"] != "complete":
                        raise ValueError("Build the model first")
                    body = self.body()
                    text = str(body.get("text", ""))[:2000]
                    if not text.strip():
                        raise ValueError("Enter a dialogue fragment")
                    # Separate process keeps model allocations and errors isolated from the server.
                    result = subprocess.run(
                        [sys.executable, "-X", "utf8", "audition.py", str(root)],
                        input=text,
                        encoding="utf-8",
                        capture_output=True,
                        timeout=90,
                        cwd=BASE,
                    )
                    if result.returncode:
                        raise ValueError(result.stderr[-1000:])
                    self.reply(json.loads(result.stdout))
                    return
                raise ValueError("Unknown action")
        except (
            ValueError,
            KeyError,
            IndexError,
            OSError,
            subprocess.TimeoutExpired,
        ) as e:
            self.reply({"error": str(e)}, 400)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8787)
    a = p.parse_args()
    from tools.check_setup import check

    preflight = check()
    if not preflight["ready"]:
        print("Setup incomplete: " + json.dumps(preflight), file=sys.stderr)
        raise SystemExit(
            "Run install.sh or INSTALL-WINDOWS.cmd with Python 3.11 before starting the worker."
        )
    for file in DATA.glob("*/state.json"):
        state = json.loads(file.read_text())
        if state["status"] == "running":
            state.update(status="stopped", phase="Worker restarted; resume build")
            write(file, state)
    public_url = os.environ.get("XOW_PUBLIC_URL", f"http://127.0.0.1:{a.port}").rstrip(
        "/"
    )
    print(f"Xputty Open Weight: {public_url}/#key={TOKEN}", flush=True)

    def terminate(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate)
    http = ThreadingHTTPServer((a.host, a.port), Handler)
    try:
        http.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for identifier, process in list(PROCESSES.items()):
            if process.poll() is None:
                stop(job(identifier))
        http.server_close()

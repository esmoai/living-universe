import hashlib, json, os, socket, subprocess, sys, time, urllib.request, urllib.error, zipfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def worker(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {
        **os.environ,
        "VOX_DATA": str(tmp_path),
        "VOX_TOKEN": "test-worker-key",
        "VOX_DEVICE": "cpu",
        "VOX_OLLAMA_VERIFY": "0",
    }
    process = subprocess.Popen(
        [sys.executable, "-u", "server.py", "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"

    def request(path, body=None, headers=None, auth=True):
        h = {"Authorization": "Bearer test-worker-key"} if auth else {}
        if path == "/api/projects" and isinstance(body, dict):
            body = {"preset": "tiny-1m-v1", **body}
        if body is not None and not isinstance(body, bytes):
            body = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        h.update(headers or {})
        with urllib.request.urlopen(
            urllib.request.Request(base + path, data=body, headers=h), timeout=100
        ) as response:
            blob = response.read()
            return (
                blob
                if response.headers["Content-Type"] != "application/json"
                else json.loads(blob)
            )

    for _ in range(100):
        try:
            request("/api/health")
            break
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)
    else:
        process.kill()
        raise AssertionError("server failed to start")
    yield request, tmp_path
    process.terminate()
    process.wait(timeout=10)


def test_authenticated_full_build_and_export(worker):
    request, data = worker
    with pytest.raises(urllib.error.HTTPError) as error:
        request("/api/projects", auth=False)
    assert error.value.code == 401
    with pytest.raises(urllib.error.HTTPError):
        request("/api/projects", headers={"Origin": "https://untrusted.invalid"})
    project = request("/api/projects", {"name": "Browser acceptance"})["id"]
    for n in range(3):
        body = "\n".join(
            f"00:00:{i:02}.000\nEpisode {n} observation {i}: "
            + ("People share stories about music science and movies. " * 12)
            for i in range(20)
        ).encode()
        state = request(
            f"/api/projects/{project}/upload", body, {"X-Filename": f"episode-{n}.txt"}
        )
    assert len(state["files"]) == 3
    duplicate = request(
        f"/api/projects/{project}/upload", body, {"X-Filename": "again.txt"}
    )
    assert duplicate["duplicate"] is True
    item = state["files"][0]
    inspected = request(f"/api/projects/{project}/material/" + item["id"])
    request(
        f"/api/projects/{project}/edit",
        {
            "id": item["id"],
            "expected_sha256": item["sha256"],
            "text": inspected["text"].replace("Episode 0", "Revised episode zero"),
        },
    )
    extra = request(
        f"/api/projects/{project}/upload",
        b"00:00:00\nExcluded source.\n00:00:03\nMust not train.",
        {"X-Filename": "excluded.txt"},
    )
    request(f"/api/projects/{project}/remove", {"id": extra["files"][-1]["id"]})
    request(f"/api/projects/{project}/build", {"steps": 2})
    deadline = time.time() + 180
    while time.time() < deadline:
        state = request(f"/api/projects/{project}")
        if state["status"] != "running":
            break
        time.sleep(0.5)
    assert state["status"] == "complete", state
    assert state["checks"]["transformers"] == "passed"
    assert (data / project / "dense/checkpoint.pt").is_file()
    normalized = "".join(
        p.read_text() for p in (data / project / "normalized").glob("*.txt")
    )
    assert "Revised episode zero" in normalized and "Excluded source" not in normalized
    result = request(
        f"/api/projects/{project}/audition",
        {"text": "I think music brings people together."},
    )
    assert result["raw"] and "speech_text" in result
    chat_page = request(f"/chat/{project}")
    assert b"/api/projects/" + project.encode() + b"/chat" in chat_page
    chat = request(
        f"/api/projects/{project}/chat",
        {
            "messages": [{"role": "user", "content": "Good evening."}],
            "max_new_tokens": 8,
        },
    )
    assert chat["backend"] == "exported-safetensors-local-cpu"
    assert (
        chat["weights_sha256"]
        == hashlib.sha256(
            (data / project / "export/model.safetensors").read_bytes()
        ).hexdigest()
    )
    blob = request(f"/api/projects/{project}/download")
    archive = data / "download.zip"
    archive.write_bytes(blob)
    with zipfile.ZipFile(archive) as z:
        assert "model/model.safetensors" in z.namelist()
        assert "model/vox-fibra-f16.gguf" in z.namelist()
        assert not any("uploads" in name for name in z.namelist())
    events = [
        json.loads(line)
        for line in (data / project / "events.jsonl").read_text().splitlines()
    ]
    previous = "0" * 64
    for event in events:
        digest = event.pop("hash")
        assert event["previous"] == previous
        assert (
            hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
            == digest
        )
        previous = digest
    # Export again after an interruption without consuming additional training updates.
    request(f"/api/projects/{project}/stop", {})
    request(f"/api/projects/{project}/build", {"steps": 2})
    deadline = time.time() + 100
    while time.time() < deadline:
        state = request(f"/api/projects/{project}")
        if state["status"] != "running":
            break
        time.sleep(0.5)
    assert state["status"] == "complete", state
    assert state["training"]["step"] == 2
    # Continue a completed model to a higher total instead of requiring a new project.
    request(f"/api/projects/{project}/build", {"steps": 3})
    deadline = time.time() + 100
    while time.time() < deadline:
        state = request(f"/api/projects/{project}")
        if state["status"] != "running":
            break
        time.sleep(0.5)
    assert state["status"] == "complete", state
    assert state["training"]["step"] == 3
    assert (data / project / "exports-history/step-2.zip").is_file()


def test_model_presets_are_explicit_and_locked(worker):
    request, data = worker
    presets = request("/api/presets")
    assert presets["research-48m-v1"]["parameters"] == 48116224
    project = request(
        "/api/projects",
        {"preset": "research-48m-v1", "training_settings": {"ramp_updates": 0}},
    )["id"]
    state = request(f"/api/projects/{project}")
    assert state["build_config"]["max_context"] == 2048
    assert state["build_config"]["ramp_updates"] == 0
    state = request(
        f"/api/projects/{project}/options",
        {"preset": "tiny-1m-v1", "training_settings": {}},
    )
    assert state["preset"] == "tiny-1m-v1"
    with pytest.raises(urllib.error.HTTPError):
        request(
            f"/api/projects/{project}/options",
            {"training_settings": {"windows": [4096], "window_weights": [1]}},
        )
    path = data / project / "state.json"
    state["status"] = "stopped"
    path.write_text(json.dumps(state))
    with pytest.raises(urllib.error.HTTPError):
        request(f"/api/projects/{project}/options", {"preset": "research-48m-v1"})


def test_upload_validation_and_failed_build(worker):
    request, data = worker
    identifier = request("/api/projects", {})["id"]
    with pytest.raises(urllib.error.HTTPError):
        request(
            "/api/projects/" + identifier + "/upload",
            b"executable",
            {"X-Filename": "bad.exe"},
        )
    with pytest.raises(urllib.error.HTTPError):
        request("/api/projects/" + identifier + "/build", {"steps": 2})
    for n in range(3):
        request(
            f"/api/projects/{identifier}/upload",
            f"Only one paragraph {n}".encode(),
            {"X-Filename": f"short{n}.txt"},
        )
    request(f"/api/projects/{identifier}/build", {"steps": 2})
    for _ in range(100):
        state = request(f"/api/projects/{identifier}")
        if state["status"] == "failed":
            break
        time.sleep(0.1)
    assert state["status"] == "failed"
    assert not (data / identifier / "model.zip").exists()


def test_stop_preserves_uploads_and_rename(worker):
    request, data = worker
    identifier = request("/api/projects", {})["id"]
    renamed = request(f"/api/projects/{identifier}/rename", {"name": "My own cast"})
    assert renamed["name"] == "My own cast"
    for n in range(3):
        request(
            f"/api/projects/{identifier}/upload",
            f"00:00:00\nEpisode {n} begins.\n00:00:02\nAnother observation.".encode(),
            {"X-Filename": f"episode{n}.txt"},
        )
    request(f"/api/projects/{identifier}/build", {"steps": 100000})
    request(f"/api/projects/{identifier}/stop", {})
    time.sleep(0.3)
    state = request(f"/api/projects/{identifier}")
    assert state["status"] == "stopped"
    assert len(list((data / identifier / "uploads").iterdir())) == 3
    assert not (data / identifier / "model.zip").exists()

import hashlib, io, json, socket, threading, urllib.request, urllib.error, zipfile
import pytest
import web_capture

HTML = b"<html><head><title>Our page</title></head><body><nav>Menu</nav><main><h1>Conversation</h1><p>00:00:01</p><p>Hello &amp; welcome.</p><script>bad()</script><p>00:00:04</p><p>A second observation.</p></main><footer>Privacy</footer></body></html>"


def test_main_text_and_packaging(tmp_path, monkeypatch):
    monkeypatch.setattr(
        web_capture,
        "fetch",
        lambda url: ("https://example.org/final", HTML, HTML.decode()),
    )
    meta, text = web_capture.capture("https://example.org/start", tmp_path / "capture")
    assert "Hello & welcome." in text and "00:00:01" in text
    assert all(item not in text for item in ["Menu", "Privacy", "bad()", "Our page"])
    assert meta["title"] == "Our page"
    with zipfile.ZipFile(tmp_path / "capture/capture.zip") as z:
        assert z.read("original.html") == HTML
        assert z.read("content.txt").decode() == text
        assert (
            json.loads(z.read("source.json"))["final_url"]
            == "https://example.org/final"
        )


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://user:pass@example.org",
        "http://example.org:8787",
        "http://127.0.0.1",
        "http://169.254.169.254",
        "http://[::1]",
    ],
)
def test_capture_blocks_local_services(url):
    with pytest.raises(ValueError):
        web_capture.target(url)


def test_capture_refuses_dns_with_private_answer(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("10.1.2.3", 443))]
    )
    with pytest.raises(ValueError, match="public"):
        web_capture.target("https://example.org")


def test_material_api_preserves_originals_and_rejects_stale_edits(
    tmp_path, monkeypatch
):
    import server

    monkeypatch.setattr(server, "DATA", tmp_path)
    calls = []

    def fetch(url):
        calls.append(url)
        return url, HTML, HTML.decode()

    monkeypatch.setattr(web_capture, "fetch", fetch)
    http = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()

    def req(path, body=None, headers=None):
        payload = (
            body
            if isinstance(body, bytes)
            else json.dumps(body).encode()
            if body is not None
            else None
        )
        r = urllib.request.Request(
            f"http://127.0.0.1:{http.server_port}" + path,
            data=payload,
            headers={
                "Authorization": "Bearer " + server.TOKEN,
                "Content-Type": "application/json",
                **(headers or {}),
            },
        )
        with urllib.request.urlopen(r) as response:
            data = response.read()
            return (
                data
                if response.headers["Content-Type"] == "application/zip"
                else json.loads(data)
            )

    try:
        project = req("/api/projects", {})["id"]
        base = f"/api/projects/{project}"
        state = req(base + "/capture", {"url": "https://example.org/article"})
        assert len(calls) == 1 and len(state["files"]) == 1
        item = state["files"][0]
        identifier = item["id"]
        original = tmp_path / project / item["path"]
        raw = original.read_bytes()
        assert req(base + "/capture-package/" + identifier).startswith(b"PK")
        inspected = req(base + "/material/" + identifier)
        assert inspected["editable"]
        state = req(
            base + "/edit",
            {
                "id": identifier,
                "expected_sha256": item["sha256"],
                "text": "00:00:01\nRevised idea.\n00:00:03\nAnother observation.",
            },
        )
        edited = state["files"][0]
        assert edited["edited"] and edited["id"] == identifier
        assert original.read_bytes() == raw
        with zipfile.ZipFile(
            io.BytesIO(req(base + "/capture-package/" + identifier))
        ) as package:
            assert package.read("content.txt") == raw
            assert b"Revised idea." in package.read("working/content.txt")
        from materials import source_path

        assert "Revised idea." in source_path(tmp_path / project, edited).read_text()
        with pytest.raises(urllib.error.HTTPError):
            req(
                base + "/edit",
                {
                    "id": identifier,
                    "expected_sha256": item["sha256"],
                    "text": "Stale edit",
                },
            )
        state = req(base + "/remove", {"id": identifier})
        assert state["files"] == [] and original.read_bytes() == raw
        assert len(state["removed_files"]) == 1
        state = req(base + "/restore", {"id": identifier})
        assert len(state["files"]) == 1
        replacement = b"00:00:01\nA replacement file.\n00:00:03\nSecond segment."
        state = req(
            base + "/replace/" + identifier,
            replacement,
            {"X-Filename": "replacement.txt"},
        )
        assert (
            state["files"][0]["id"] == identifier
            and state["files"][0]["name"] == "replacement.txt"
        )
        assert original.read_bytes() == raw
        # Legacy projects from v0.1 use their SHA as the stable material identifier.
        legacy = {
            "name": "legacy.txt",
            "sha256": hashlib.sha256(b"old").hexdigest(),
            "bytes": 3,
        }
        path = tmp_path / project / "uploads" / (legacy["sha256"][:12] + "-legacy.txt")
        path.write_bytes(b"old")
        state["files"] = [legacy]
        server.write(tmp_path / project / "state.json", state)
        assert req(base + "/material/" + legacy["sha256"])["text"] == "old"
        state["status"] = "running"
        server.write(tmp_path / project / "state.json", state)
        with pytest.raises(urllib.error.HTTPError):
            req(base + "/remove", {"id": legacy["sha256"]})
    finally:
        http.shutdown()
        http.server_close()
        thread.join()

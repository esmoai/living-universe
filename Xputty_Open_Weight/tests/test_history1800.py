import hashlib
import json
from pathlib import Path

import pytest

from tools.history1800 import WORKS, clean
from vox.plain_text import build
from export_chat import ExportSession, format_prompt

ROOT = Path(__file__).resolve().parents[1]


def test_historical_cleaning_and_period_metadata():
    text = "A period sentence with two spaces and a thought.\n" * 700
    original = (
        "Modern release metadata 2026\r\r\n*** START OF THE PROJECT GUTENBERG EBOOK TEST ***\r\r\n"
        + text
        + "\n*** END OF THE PROJECT GUTENBERG EBOOK TEST ***\nModern license footer"
    )
    result = clean(original.encode())
    assert "Modern release" not in result and "Modern license" not in result
    assert "two spaces" in result
    assert "\r" not in result
    contaminated = original.replace(
        text,
        "Note from the original file: electronic dedication [Officially celebrated January 20, 1992]\n"
        + text,
    )
    assert "1992" not in clean(contaminated.encode())
    assert len(WORKS) == len({w[0] for w in WORKS})
    assert all(1800 <= row[1] <= 1899 for row in WORKS)
    with pytest.raises(ValueError, match="boundaries"):
        clean(b"An unrelated HTML response")


def test_plain_prose_export_and_chat_without_checkpoint(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    sources = []
    files = []
    for n in range(5):
        path = tmp_path / f"book-{n}.txt"
        path.write_text(
            (
                f"This is work {n}. A curious traveller considered the evening sky.\n\n"
                * 80
            ),
            encoding="utf-8",
        )
        sources.append(path)
        files.append(
            dict(
                id=f"source{n}",
                name=path.name,
                path=path.name,
                bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    report = build(sources, tmp_path / "split-test")
    groups = [set(s["episode_ids"]) for s in report["splits"].values()]
    assert all(not (a & b) for i, a in enumerate(groups) for b in groups[i + 1 :])
    assert report["timing_mode"] == "none"
    assert "<|at_ms|>" not in (tmp_path / "split-test/tokenizer_train.txt").read_text()
    state = dict(
        id=tmp_path.name,
        name="Historical test",
        mode="plain",
        files=files,
        status="draft",
    )
    (tmp_path / "state.json").write_text(json.dumps(state))
    monkeypatch.setenv("XOW_OLLAMA_VERIFY", "0")
    from worker import run

    # Windows may default to cp1252. Portable model cards must always be UTF-8.
    original_write = Path.write_text

    def check_card_encoding(path, text, *args, **kwargs):
        if path.name == "README.md" and path.parent.name == "export":
            assert kwargs.get("encoding") == "utf-8"
        return original_write(path, text, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", check_card_encoding)
    run(tmp_path, steps=2)
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["status"] == "complete"
    assert state["checks"]["transformers"] == "passed"
    assert (tmp_path / "export/chat.py").is_file()
    # Prove inference uses the portable export and does not reopen training weights.
    (tmp_path / "dense/checkpoint.pt").rename(tmp_path / "dense/checkpoint-hidden.pt")
    session = ExportSession(tmp_path / "export")
    answer = session.respond(
        dict(
            messages=[dict(role="user", content="The evening sky")],
            mode="continue",
            max_new_tokens=8,
        )
    )
    assert answer["backend"] == "exported-safetensors-local-cpu"
    assert answer["representation"] == "plain-text-works-v1"
    assert (
        answer["weights_sha256"]
        == hashlib.sha256(
            (tmp_path / "export/model.safetensors").read_bytes()
        ).hexdigest()
    )
    long = session.respond(
        dict(messages=[dict(role="user", content="The sky " * 400)], max_new_tokens=8)
    )
    assert (
        long["truncated_tokens"] > 0
        and long["input_tokens"] <= long["context_tokens"] - 8
    )


def test_chat_validation_and_no_invented_history():
    assert (
        format_prompt([dict(role="user", content="Dear friend,")], "continue")
        == "Dear friend,"
    )
    assert format_prompt(
        [
            dict(role="user", content="Hello"),
            dict(role="assistant", content="Good evening"),
            dict(role="user", content="What news?"),
        ]
    ).endswith("Visitor: What news?\nCompanion:")
    with pytest.raises(ValueError):
        format_prompt([dict(role="system", content="Hidden instruction")])


def test_atomic_state_retries_windows_reader_lock(tmp_path, monkeypatch):
    import worker
    replace = worker.os.replace
    calls = []

    def transient(source, target):
        calls.append(1)
        if len(calls) == 1:
            raise PermissionError("simulated Windows reader")
        return replace(source, target)

    monkeypatch.setattr(worker.os, "replace", transient)
    worker.write(tmp_path / "state.json", {"status": "complete"})
    assert len(calls) == 2
    assert json.loads((tmp_path / "state.json").read_text())["status"] == "complete"
    assert not list(tmp_path.glob("*.tmp"))

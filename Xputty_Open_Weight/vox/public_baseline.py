"""Pinned, attributable public conversation corpus; no fabricated speech timing.

The 48M scratch experiment and the pretrained 135M comparison are distinct.
Only the scratch experiment uses this application's frozen 8K vocabulary.
"""

import hashlib
import json
import re
import ssl
import time
import urllib.request
from pathlib import Path

DATASET = "HuggingFaceTB/smol-smoltalk"
DATA_REVISION = "f73fe857d519ff6ac5af2ea67c4d3834da7b8bcc"
MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"
MODEL_REVISION = "12fd25f77366fa6b3b4b768ec3050bf629380bac"
REFERENCES = {
    "smollm135": {"model": MODEL, "revision": MODEL_REVISION, "folder": "SmolLM2-135M-Instruct"},
    "qwen05": {"model": "Qwen/Qwen2.5-0.5B-Instruct", "revision": "7ae557604adf67be50417f59c2c2f167def9a775", "folder": "Qwen2.5-0.5B-Instruct"},
}
SOURCE_FILES = {
    "README.md": "4de8fe5ebb738a835f780332c35ec5a7dd1e8dae058308e7caa176dca6bbf808",
    "data/train-00000-of-00004.parquet": "498cd4580014f42c40cfde066573564ed28e3e1548a5566715b615f5ea932856",
    "data/test-00000-of-00001.parquet": "be6773dcce145f3918ff14237b1f765affa427b0b13f6a02d397e665ac908b9a",
}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def download(url, path, expected=None):
    """Atomic download. A fixed revision plus checksums identifies original bytes."""
    import certifi

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if expected is None or sha256(path) == expected:
            return path
        raise ValueError("Cached source checksum differs: " + str(path))
    temporary = path.with_name(path.name + ".part")
    try:
        with urllib.request.urlopen(
            url, context=ssl.create_default_context(cafile=certifi.where()), timeout=120
        ) as response, temporary.open("wb") as stream:
            while block := response.read(1024 * 1024):
                stream.write(block)
        if expected is not None and sha256(temporary) != expected:
            raise ValueError("Downloaded source checksum differs: " + url)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def canonical_messages(messages):
    if not isinstance(messages, list) or not 2 <= len(messages) <= 12:
        return None
    clean = []
    for i, message in enumerate(messages):
        expected_role = "user" if i % 2 == 0 else "assistant"
        if message.get("role") != expected_role:
            return None
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            return None
        clean.append({"role": expected_role, "content": content.strip()})
    if clean[-1]["role"] != "assistant":
        return None
    text = " ".join(m["content"] for m in clean)
    if not 100 <= len(text.split()) <= 1200:
        return None
    if any(marker in text for marker in ("```", "<|", "<s>", "</s>", "<pad>")):
        return None
    if len(re.findall(r"[a-zA-Z]", text)) < 0.5 * len(text):
        return None
    # This is a focused language baseline, not a code/rewrite/constraint benchmark.
    return clean


def select_rows(rows, limit, split, seen):
    selected = []
    for index, row in enumerate(rows):
        if row.get("source") not in ("smol-magpie-ultra-short", "everyday-conversations"):
            continue
        messages = canonical_messages(row.get("messages"))
        if messages is None:
            continue
        encoded = json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()
        identity = hashlib.sha256(encoded).hexdigest()
        if identity in seen:
            continue
        seen.add(identity)
        selected.append({
            "id": identity, "messages": messages, "source": row["source"],
            "upstream_split": split, "upstream_row": index,
        })
        if len(selected) >= limit:
            break
    if len(selected) < limit:
        raise ValueError(f"Only {len(selected)} eligible {split} conversations; requested {limit}")
    return selected


def prepare_public(cache, project, count=2000):
    import pyarrow.parquet as parquet

    from .plain_text import build
    from .tokenizer import train as tokenize
    from .data import prepare

    if type(count) is not int or not 32 <= count <= 20000:
        raise ValueError("Choose 32–20,000 conversations")
    cache, project = Path(cache), Path(project)
    if project.exists():
        raise FileExistsError("Use a new public experiment directory")
    sources = []
    for name, checksum in SOURCE_FILES.items():
        url = f"https://huggingface.co/datasets/{DATASET}/resolve/{DATA_REVISION}/{name}"
        target = download(url, cache / Path(name).name, checksum)
        sources.append({"url": url, "sha256": checksum, "bytes": target.stat().st_size})
    seen = set()
    train_rows = select_rows(
        parquet.read_table(cache / "train-00000-of-00004.parquet").to_pylist(), count, "train", seen
    )
    # Official test records are used only for an external final audit, not training
    # or tokenizer construction. Internal val/test also remain conversation-disjoint.
    external = select_rows(
        parquet.read_table(cache / "test-00000-of-00001.parquet").to_pylist(), 100, "test", seen
    )
    project.mkdir(parents=True)
    (project / "uploads").mkdir()
    files = []
    for row in train_rows:
        target = project / "uploads" / (row["id"] + ".txt")
        text = "\n".join(
            ("Visitor: " if m["role"] == "user" else "Companion: ") + m["content"]
            for m in row["messages"]
        )
        target.write_text(text, encoding="utf-8")
        files.append({"id": row["id"][:32], "name": f"public-dialogue-{row['upstream_row']:06}.txt",
                      "path": "uploads/" + target.name, "sha256": sha256(target), "bytes": target.stat().st_size})
    provenance = {"kind": "public-conversations", "dataset": DATASET, "revision": DATA_REVISION,
                  "dataset_url": f"https://huggingface.co/datasets/{DATASET}",
                  "license": "Apache-2.0 (upstream dataset declaration)",
                  "synthetic": True, "sources": sources, "selected": len(train_rows),
                  "filters": "Alternating English user/assistant conversations; 100–1200 words; no fenced code",
                  "timing": "Absent: no timestamps, pauses, overlaps or audio cues synthesized",
                  "external_test_records": len(external),
                  "external_test_scope": "Held out of this adaptation, not guaranteed unseen by the public pretrained control"}
    write_json(project / "public-sources.json", provenance)
    (project / "UPSTREAM-DATASET-CARD.md").write_bytes((cache / "README.md").read_bytes())
    for name, rows in [("conversations.jsonl", train_rows), ("external-test.jsonl", external)]:
        (project / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    report = build([project / f["path"] for f in files], project / "data", provenance=provenance)
    tokenize(project / "data", 8192)
    prepare(project / "data")
    state = {"id": project.name, "name": "Public dialogue · 48M scratch baseline v1", "created": time.time(),
             "status": "stopped", "phase": f"Frozen public corpus prepared · {count:,} attributable conversations",
             "mode": "plain", "preset": "research-48m-v1", "steps": 200, "files": files,
             "training_settings": {"ramp_updates": 80, "warmup_updates": 20},
             "public_baseline": provenance}
    write_json(project / "state.json", state)
    return report


def conversation_splits(project):
    project = Path(project)
    records = {r["id"]: r for r in (json.loads(line) for line in (project / "conversations.jsonl").read_text(encoding="utf-8").splitlines())}
    result = {}
    for split in ("train", "val", "test"):
        rows = [json.loads(line) for line in (project / "data" / (split + ".jsonl")).read_text(encoding="utf-8").splitlines()]
        result[split] = [records[row["episode_id"]] for row in rows]
    ids = [set(r["id"] for r in result[k]) for k in result]
    if any(a & b for i, a in enumerate(ids) for b in ids[i + 1:]):
        raise ValueError("Conversation leakage between partitions")
    return result


def fetch_control(cache, reference="smollm135"):
    info = REFERENCES[reference]
    folder = Path(cache) / info["folder"]
    names = ["config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json",
             "special_tokens_map.json", "generation_config.json", "vocab.json", "merges.txt", "README.md"]
    for name in names:
        if info["model"].startswith("Qwen/") and name == "special_tokens_map.json":
            continue
        download(f"https://huggingface.co/{info['model']}/resolve/{info['revision']}/{name}", folder / name)
    download("https://www.apache.org/licenses/LICENSE-2.0.txt", folder / "LICENSE",
             "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30")
    return folder

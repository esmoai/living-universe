"""Whole-work splits for prose: no invented speakers, timestamps or chat pairs."""

import hashlib
import json
import random
from pathlib import Path

REPRESENTATION = "plain-text-works-v1"


def build(sources, output, seed=739, provenance=None):
    public_dialogue = (provenance or {}).get("kind") == "public-conversations"
    out = Path(output)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError("Use a new corpus snapshot")
    works, seen = [], set()
    for source in map(Path, sources):
        blob = source.read_bytes()
        text = blob.decode("utf-8-sig").strip()
        if len(text.split()) < 100:
            raise ValueError("Each work needs at least 100 words: " + source.name)
        if any(t in text for t in ("<|eod|>", "<s>", "</s>", "<pad>")):
            raise ValueError("Reserved model token in source")
        digest = hashlib.sha256(text.encode()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        works.append(
            dict(
                episode_id=source.stem,
                series_id="public-conversations" if public_dialogue else "historical-prose",
                text=text,
                source_sha256=hashlib.sha256(blob).hexdigest(),
                text_sha256=digest,
            )
        )
    if len(works) < 3:
        raise ValueError("At least three distinct whole works are required")
    works.sort(key=lambda w: w["text_sha256"])
    random.Random(seed).shuffle(works)
    n = max(1, round(len(works) * 0.15))
    splits = dict(test=works[:n], val=works[n : 2 * n], train=works[2 * n :])
    out.mkdir(parents=True, exist_ok=True)
    for split, rows in splits.items():
        (out / (split + ".jsonl")).write_text(
            "".join(json.dumps(w, ensure_ascii=False) + "\n" for w in rows),
            encoding="utf-8",
        )
    (out / "tokenizer_train.txt").write_text(
        "\n\n".join(w["text"] for w in splits["train"]), encoding="utf-8"
    )
    report = dict(
        schema="xow-plain-text/1",
        origin="public_conversation_text" if public_dialogue else "historical_plain_text",
        representation=REPRESENTATION,
        timing_mode="none",
        release_eligible=False,
        split_group="whole-work",
        split_seed=seed,
        episodes=len(works),
        corpus_digest=hashlib.sha256(
            json.dumps(works, sort_keys=True).encode()
        ).hexdigest(),
        splits={
            s: dict(
                episodes=len(rows),
                words=sum(len(w["text"].split()) for w in rows),
                episode_ids=[w["episode_id"] for w in rows],
            )
            for s, rows in splits.items()
        },
        provenance=provenance or {},
        scope="Public synthetic conversations with known roles; no audio or measured speech timing."
        if public_dialogue else "Historical works, modern digital transcriptions. No claim of perfect edition purity or chat training.",
    )
    (out / "corpus_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report

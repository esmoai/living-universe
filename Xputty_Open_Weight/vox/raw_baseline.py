"""Snapshot unlabelled supplied dialogue and timing for local baseline training.

Episode boundaries remain intact. Transcript segments are never asserted to be
speaker turns, and start-to-start intervals are never labelled speech pauses.
"""

import argparse
import hashlib
import json
import random
import re
from pathlib import Path
from .upod import suggest_turns
from .intake import decode_text

RAW_TOKENS = ["<|segment|>", "<|at_ms|>", "<|delta_ms|>", "<|text|>"]
REPRESENTATION = "unlabelled-dialogue-timing-v1"


def episode_key(stem):
    # The capture extension appends an eight-digit URL hash. Keep the episode
    # identity stable across re-captures with corrected dialogue or timing.
    if re.match(r"^(?:\d+-|jre-)", stem):
        return re.sub(r"-[0-9a-f]{8}$", "", stem.lower())
    return stem.lower()


def serialize_raw(episode):
    output = []
    previous = None
    for row in episode["segments"]:
        timing = ""
        if row.get("start_ms") is not None:
            at = int(row["start_ms"])
            delta = 0 if previous is None else at - previous
            if delta < 0:
                raise ValueError("source segment starts decrease")
            timing = f"<|at_ms|>{at}<|delta_ms|>{delta}"
            previous = at
        output.append("<|segment|>" + timing + "<|text|>" + row["text"])
    return "\n".join(output) + "\n<|eod|>"


def build(sources, output, seed=739, assignments=None):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("use a new corpus snapshot directory")
    episodes = []
    seen = set()
    identities = {}
    duplicates = []
    for source in map(Path, sources):
        blob = source.read_bytes()
        text, encoding = decode_text(blob)
        rows = suggest_turns(text)
        if len(rows) < 2:
            raise ValueError("need at least two source segments: " + str(source))
        segments = [
            {
                "text": r["text"],
                **(
                    {"start_ms": r["start_ms"]} if r.get("start_ms") is not None else {}
                ),
            }
            for r in rows
        ]
        normalized = json.dumps(
            segments, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        digest = hashlib.sha256(normalized).hexdigest()
        if digest in seen:
            duplicates.append(str(source))
            continue
        seen.add(digest)
        identity = episode_key(source.stem)
        if identity in identities:
            raise ValueError(
                "conflicting captures of one episode; select one revision: "
                + source.stem
            )
        identities[identity] = digest
        if any(
            any(token in r["text"] for token in RAW_TOKENS + ["<|eod|>"])
            for r in segments
        ):
            raise ValueError("source contains reserved serialization markers")
        episodes.append(
            {
                "episode_id": source.stem,
                "episode_key": identity,
                "series_id": "supplied-podcast-samples",
                "segments": segments,
                "source_path": str(source.resolve()),
                "source_sha256": hashlib.sha256(blob).hexdigest(),
                "dialogue_sha256": digest,
                "encoding": encoding,
                "original_bytes": len(blob),
            }
        )
    if len(episodes) < 3:
        raise ValueError(
            "at least three unique episodes are required for whole-episode holdouts"
        )
    episodes.sort(key=lambda e: e["dialogue_sha256"])
    random.Random(seed).shuffle(episodes)
    count = len(episodes)
    n = max(1, round(count * 0.15))
    if assignments:
        splits = {"test": [], "val": [], "train": []}
        for episode in episodes:
            digest = episode["dialogue_sha256"]
            split = assignments.get(
                digest, assignments.get("episode:" + episode["episode_key"])
            )
            if split is None:
                bucket = (
                    int(
                        hashlib.sha256((str(seed) + digest).encode()).hexdigest()[:8],
                        16,
                    )
                    / 2**32
                )
                split = "test" if bucket < 0.15 else "val" if bucket < 0.30 else "train"
            if split not in splits:
                raise ValueError("invalid persistent split assignment")
            splits[split].append(episode)
        if any(not rows for rows in splits.values()):
            raise ValueError("selected sources omit an existing holdout partition")
    else:
        splits = {
            "test": episodes[:n],
            "val": episodes[n : 2 * n],
            "train": episodes[2 * n :],
        }
    if assignments is not None:
        for split, rows in splits.items():
            for episode in rows:
                assignments[episode["dialogue_sha256"]] = split
                assignments["episode:" + episode["episode_key"]] = split
    output.mkdir(parents=True, exist_ok=True)
    (output / "sources").mkdir()
    for episode in episodes:
        source = Path(episode["source_path"])
        snapshot = (
            output / "sources" / (episode["source_sha256"] + source.suffix.lower())
        )
        snapshot.write_bytes(source.read_bytes())
        assert (
            hashlib.sha256(snapshot.read_bytes()).hexdigest()
            == episode["source_sha256"]
        )
    for split, rows in splits.items():
        (output / (split + ".jsonl")).write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
    (output / "tokenizer_train.txt").write_text(
        "\n".join(serialize_raw(row) for row in splits["train"]), encoding="utf-8"
    )
    report = {
        "schema": "vox-raw-baseline/1",
        "origin": "user_supplied_raw_dialogue",
        "release_eligible": False,
        "representation": REPRESENTATION,
        "timing_mode": "source-segment-starts-and-deltas",
        "timing_scope": "Start-to-start intervals are not silence, speech duration, overlap, or verified speaker changes.",
        "split_group": "episode",
        "split_seed": seed,
        "speaker_labels": "not required and not inferred",
        "corpus_digest": hashlib.sha256(
            json.dumps(episodes, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest(),
        "episodes": len(episodes),
        "duplicates_skipped": duplicates,
        "splits": {
            name: {
                "episodes": len(rows),
                "segments": sum(len(e["segments"]) for e in rows),
                "words": sum(
                    len(s["text"].split()) for e in rows for s in e["segments"]
                ),
                "episode_ids": [e["episode_id"] for e in rows],
            }
            for name, rows in splits.items()
        },
    }
    (output / "corpus_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=739)
    args = parser.parse_args()
    print(json.dumps(build(args.sources, args.output, args.seed), indent=2))

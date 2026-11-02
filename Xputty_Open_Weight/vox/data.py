"""Memory-mapped token storage. A complete original episode is never split between partitions."""

import argparse, json, random
from pathlib import Path
import numpy as np
import sentencepiece as spm
from .corpus import serialize_episode
from .tokenizer import sha256


def prepare(data_dir):
    root = Path(data_dir)
    report = json.loads((root / "corpus_report.json").read_text())
    sp = spm.SentencePieceProcessor(model_file=str(root / "vox.model"))
    out = {}
    for split in ("train", "val", "test"):
        index = []
        ofs = 0
        filename = root / f"{split}.u32"
        with (
            filename.open("wb") as f,
            (root / f"{split}.roles.u8").open("wb") as roles_file,
        ):
            for raw in (root / f"{split}.jsonl").open(encoding="utf8"):
                if not raw.strip():
                    continue
                e = json.loads(raw)
                raw_mode = (
                    report.get("representation") == "unlabelled-dialogue-timing-v1"
                )
                plain_mode = report.get("representation") == "plain-text-works-v1"
                if plain_mode:
                    toks = sp.encode(e["text"], out_type=int) + [
                        sp.piece_to_id("<|eod|>")
                    ]
                    positions = [0]
                    expected = 1
                elif raw_mode:
                    from .raw_baseline import serialize_raw

                    serialized = serialize_raw(e)
                    marker = "<|segment|>"
                    expected = len(e["segments"])
                else:
                    serialized = serialize_episode(e, report.get("timing_mode", "none"))
                    marker = "<|turn|>"
                    expected = len(e["turns"])
                if not plain_mode:
                    toks = sp.encode(serialized, out_type=int)
                    positions = [
                        i for i, t in enumerate(toks) if t == sp.piece_to_id(marker)
                    ]
                if len(positions) != expected:
                    raise ValueError(
                        f"failed to preserve source boundaries for {e['episode_id']}"
                    )
                np.array(toks, dtype="<u4").tofile(f)
                roles = []
                active = 2
                for tid in toks:
                    if plain_mode:
                        roles.append(0 if tid == sp.piece_to_id("<|eod|>") else 2)
                    elif raw_mode and tid in (
                        sp.piece_to_id("<|at_ms|>"),
                        sp.piece_to_id("<|delta_ms|>"),
                    ):
                        active = 1
                        roles.append(0)
                    elif raw_mode and tid == sp.piece_to_id("<|text|>"):
                        active = 2
                        roles.append(0)
                    elif raw_mode and tid in (
                        sp.piece_to_id("<|segment|>"),
                        sp.piece_to_id("<|eod|>"),
                    ):
                        active = 0
                        roles.append(0)
                    else:
                        roles.append(active)
                np.array(roles, dtype="u1").tofile(roles_file)
                index.append(
                    dict(
                        episode_id=e["episode_id"],
                        start=ofs,
                        length=len(toks),
                        turn_starts=positions,
                        series_id=e["series_id"],
                    )
                )
                ofs += len(toks)
        (root / f"{split}.index.json").write_text(json.dumps(index, indent=2) + "\n")
        out[split] = dict(episodes=len(index), tokens=ofs)
    config = dict(
        tokenizer_sha256=sha256(root / "vox.model"),
        corpus_digest=report["corpus_digest"],
        origin=report["origin"],
        release_eligible=bool(report["release_eligible"]),
        shapes=out,
        stage="prepared",
    )
    config["timing_mode"] = report.get("timing_mode", "none")
    config["representation"] = report.get("representation", "reviewed-speaker-turns")
    (root / "prepared_report.json").write_text(json.dumps(config, indent=2) + "\n")
    return config


class CorpusSamples:
    def __init__(self, data_dir, split, context=128, stage="base", context_turns=3):
        self.root = Path(data_dir)
        self.split = split
        self.context = context
        self.stage = stage
        self.context_turns = context_turns
        if stage not in ("base", "chat"):
            raise ValueError("stage must be base/chat")
        self.index = json.loads((self.root / f"{split}.index.json").read_text())
        self.mmap = np.memmap(self.root / f"{split}.u32", dtype="<u4", mode="r")
        if not self.index:
            raise ValueError("empty partition")
        self.pad = 3
        role_path = self.root / f"{split}.roles.u8"
        self.roles = (
            np.memmap(role_path, dtype="u1", mode="r") if role_path.exists() else None
        )
        report = json.loads((self.root / "prepared_report.json").read_text())
        if stage == "chat" and report.get("representation") in (
            "unlabelled-dialogue-timing-v1",
            "plain-text-works-v1",
        ):
            raise ValueError(
                "unlabelled segment boundaries cannot be used as verified speaker turns for chat specialization"
            )

    def sample(self, step=0, seed=739):
        rng = random.Random(seed * 1000003 + step)
        selected = self.index[rng.randrange(len(self.index))]
        raw = self.mmap[selected["start"] : selected["start"] + selected["length"]]
        n = len(raw)
        if self.stage == "chat":
            starts = selected["turn_starts"]
            if len(starts) < 2:
                raise ValueError("chat requires >= 2 turns")
            j = rng.randrange(1, len(starts))
            first = max(0, j - self.context_turns)
            start = starts[first]
            end = starts[j + 1] if j + 1 < len(starts) else n
            # Prefer the complete selected last turn, trim older context when necessary.
            start = max(start, end - (self.context + 1))
            chunk = raw[start:end].astype(np.int64).tolist()
            loss_start = max(0, starts[j] - start)
        else:
            start = rng.randint(0, max(0, n - (self.context + 1)))
            chunk = raw[start : start + self.context + 1].astype(np.int64).tolist()
            loss_start = 1
        # [ids 0..N-2] -> predict [ids 1..N-1]; target span begins at loss_start.
        tokens = chunk[:-1]
        targets = [
            tid if (i + 1) >= loss_start else -100 for i, tid in enumerate(chunk[1:])
        ]
        size = self.context
        if len(tokens) < size:
            deficit = size - len(tokens)
            tokens.extend([self.pad] * deficit)
            targets.extend([-100] * deficit)
        else:
            tokens = tokens[:size]
            targets = targets[:size]
        if not any(t >= 0 for t in targets):
            raise ValueError("all labels masked; bad example")
        info = dict(
            episode_id=selected["episode_id"], loss_tokens=sum(t >= 0 for t in targets)
        )
        if self.roles is not None:
            roles = (
                self.roles[
                    selected["start"] + start + 1 : selected["start"]
                    + start
                    + len(chunk)
                ]
                .astype(np.int64)
                .tolist()
            )
            info["target_roles"] = roles + [-1] * (size - len(roles))
        return np.array(tokens, dtype=np.int64), np.array(targets, dtype=np.int64), info


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    a = ap.parse_args()
    print(json.dumps(prepare(a.data), indent=2))

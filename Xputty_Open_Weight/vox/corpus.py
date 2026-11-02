"""Rights-gated episode corpus, provenance, episode-disjoint train/dev/test splitting.

Never treat examples as licensed merely because they are publicly available. Synthetic
fixture data cannot enter production train/eval even if it declares valid rights.
"""

from __future__ import annotations
import argparse, hashlib, json, random, re
from pathlib import Path
from collections import Counter

APPROVED_BASIS = {"owned-original", "written-permission", "cc0-1.0", "cc-by-4.0"}
REQUIRED_USES = {"model_training", "weight_distribution"}
SPEAKERS = tuple(f"<|sp{i}|>" for i in range(8))
TURN = "<|turn|>"
END = "<|eod|>"
CUSTOM_TOKENS = [TURN, END, *SPEAKERS]


def digest(obj):
    return hashlib.sha256(
        json.dumps(
            obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf8")
    ).hexdigest()


def require_episode(x, allow_smoke=False):
    if not isinstance(x, dict):
        raise ValueError("episode is not object")
    for k in (
        "episode_id",
        "series_id",
        "recorded_date",
        "title",
        "rights_holder",
        "permission_basis",
        "permission_reference",
        "source_uri",
        "origin",
        "turns",
    ):
        if k not in x:
            raise ValueError(f"episode missing {k}")
    if x["origin"] not in ("real_podcast", "synthetic_smoke"):
        raise ValueError("origin must be real_podcast or synthetic_smoke")
    if x["origin"] == "synthetic_smoke" and not allow_smoke:
        raise ValueError("synthetic fixture prohibited in production corpus")
    if x["origin"] == "real_podcast" and not x.get("is_podcast", False):
        raise ValueError("real_podcast requires is_podcast=true")
    for k in (
        "episode_id",
        "series_id",
        "title",
        "rights_holder",
        "permission_reference",
        "source_uri",
    ):
        if not isinstance(x[k], str) or not x[k].strip():
            raise ValueError(f"{k} must be nonempty")
    if x.get("permission_basis") not in APPROVED_BASIS:
        raise ValueError("no accepted explicit rights basis")
    if not REQUIRED_USES.issubset(set(x.get("allowed_uses", []))):
        raise ValueError("requires model_training AND weight_distribution clearance")
    if not re.fullmatch(r"20\d\d-\d\d-\d\d", str(x["recorded_date"])):
        raise ValueError("invalid recorded_date format")
    year = int(x["recorded_date"][:4])
    if not 2020 <= year <= 2026:
        raise ValueError("must be 2020s contemporary podcast")
    if x.get("language", "en") != "en":
        raise ValueError("R02 English-only tokenizer")
    if not isinstance(x["turns"], list) or len(x["turns"]) < 2:
        raise ValueError("episode needs >=2 turns")
    speakers = []
    last_ms = -1
    for i, t in enumerate(x["turns"]):
        if (
            not isinstance(t, dict)
            or not t.get("speaker_id")
            or not isinstance(t.get("text"), str)
            or not t["text"].strip()
        ):
            raise ValueError(f"bad speaker/text at turn {i}")
        txt = t["text"]
        if len(txt) > 10000:
            raise ValueError("turn over 10000 chars")
        if any(s in txt for s in CUSTOM_TOKENS):
            raise ValueError("transcript includes reserved control token")
        if t["speaker_id"] not in speakers:
            speakers.append(t["speaker_id"])
        if len(speakers) > 8:
            raise ValueError("max 8 speakers per episode")
        if "start_ms" in t:
            v = int(t["start_ms"])
            if v < 0 or v < last_ms:
                raise ValueError("timestamps must be nondecreasing")
            last_ms = v
        if "end_ms" in t:
            if "start_ms" not in t or int(t["end_ms"]) < int(t["start_ms"]):
                raise ValueError("segment end must follow its source start")
    return x


def load_corpus(path, allow_smoke=False):
    episodes = []
    seen = set()
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    for line_no, line in enumerate(path.read_text(encoding="utf8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            ep = require_episode(json.loads(line), allow_smoke=allow_smoke)
            if ep["episode_id"] in seen:
                raise ValueError("duplicate episode_id")
            seen.add(ep["episode_id"])
            episodes.append(ep)
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            raise ValueError(f"{path.name}:{line_no}: {e}") from e
    if len(episodes) < 3:
        raise ValueError("at least 3 episodes required for disjoint train/dev/test")
    modes = {e["origin"] for e in episodes}
    if len(modes) > 1:
        raise ValueError("never mix synthetic and real podcast records")
    return episodes


def split_episodes(episodes, seed=739, group_by="series"):
    if group_by not in ("series", "episode"):
        raise ValueError("group_by must be series or episode")
    key = "series_id" if group_by == "series" else "episode_id"
    groups = {}
    for e in episodes:
        groups.setdefault(e[key], []).append(e)
    if len(groups) < 3:
        raise ValueError(
            f"requires >=3 distinct {key} groups; explicitly choose episode grouping if necessary"
        )
    group_ids = sorted(groups)
    random.Random(seed).shuffle(group_ids)
    n = len(group_ids)
    n_test = max(1, round(n * 0.15))
    n_val = max(1, round(n * 0.15))
    n_train = n - n_val - n_test
    if n_train < 1:
        raise ValueError("no training groups")
    assign = {
        "train": group_ids[:n_train],
        "val": group_ids[n_train : n_train + n_val],
        "test": group_ids[n_train + n_val :],
    }
    return {s: [e for g in ids for e in groups[g]] for s, ids in assign.items()}


def serialize_episode(ep, timing_mode="none"):
    if timing_mode not in ("none", "segment-starts"):
        raise ValueError("unknown timing serialization mode")
    speakers = []
    out = []
    for t in ep["turns"]:
        who = t["speaker_id"]
        if who not in speakers:
            speakers.append(who)
        timing = ""
        if timing_mode == "segment-starts" and t.get("start_ms") is not None:
            timing = "[segment_start_ms=" + str(int(t["start_ms"])) + "]"
            if t.get("end_ms") is not None:
                timing += "[segment_end_ms=" + str(int(t["end_ms"])) + "]"
        out.append(TURN + SPEAKERS[speakers.index(who)] + timing + t["text"].strip())
    return "\n".join(out) + "\n" + END


def serialize_turn_prefix(ep, turn_index, context_turns):
    # Speaker indices must remain consistent throughout the full original episode.
    speakers = []
    serialized = []
    for t in ep["turns"]:
        if t["speaker_id"] not in speakers:
            speakers.append(t["speaker_id"])
        serialized.append(
            TURN + SPEAKERS[speakers.index(t["speaker_id"])] + t["text"].strip()
        )
    start = max(0, turn_index - context_turns)
    prefix = (
        "\n".join(serialized[start:turn_index]) + "\n" if turn_index > start else ""
    )
    target = serialized[turn_index] + "\n"
    return prefix, target


def corpus_report(episodes, splits):
    def each(eps):
        return dict(
            episodes=len(eps),
            turns=sum(len(x["turns"]) for x in eps),
            characters=sum(sum(len(t["text"]) for t in x["turns"]) for x in eps),
            series=sorted({x["series_id"] for x in eps}),
        )

    return dict(
        schema="vox-corpus-v1",
        origin=episodes[0]["origin"],
        release_eligible=episodes[0]["origin"] == "real_podcast",
        corpus_digest=digest(episodes),
        episode_ids={k: [x["episode_id"] for x in v] for k, v in splits.items()},
        splits={k: each(v) for k, v in splits.items()},
        rights_bases=dict(Counter(e["permission_basis"] for e in episodes)),
    )


def make_bundle(
    path, out_dir, allow_smoke=False, seed=739, group_by="series", timing_mode="none"
):
    if timing_mode not in ("none", "segment-starts"):
        raise ValueError("unknown timing mode")
    eps = load_corpus(path, allow_smoke=allow_smoke)
    splits = split_episodes(eps, seed, group_by)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = corpus_report(eps, splits)
    report["split_seed"] = seed
    report["split_group"] = group_by
    report["timing_mode"] = timing_mode
    report["timing_scope"] = (
        "Source segment boundaries, not measured speech pauses or word alignment"
    )
    for k, v in splits.items():
        (out / f"{k}.jsonl").write_text(
            "\n".join(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in v)
            + "\n",
            encoding="utf8",
        )
    (out / "corpus_report.json").write_text(json.dumps(report, indent=2) + "\n")
    (out / "tokenizer_train.txt").write_text(
        "\n".join(serialize_episode(x, timing_mode) for x in splits["train"]),
        encoding="utf8",
    )
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--allow-synthetic-smoke", action="store_true")
    p.add_argument("--seed", type=int, default=739)
    p.add_argument("--group-by", choices=["series", "episode"], default="series")
    p.add_argument("--timing-mode", choices=["none", "segment-starts"], default="none")
    a = p.parse_args()
    print(
        json.dumps(
            make_bundle(
                a.input,
                a.output,
                a.allow_synthetic_smoke,
                a.seed,
                a.group_by,
                a.timing_mode,
            ),
            indent=2,
        )
    )

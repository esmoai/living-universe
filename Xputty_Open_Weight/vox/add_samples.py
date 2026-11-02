"""Add a supplied batch to the current baseline without restarting its vocabulary."""

import argparse, hashlib, json, shutil
from pathlib import Path
import torch
from .raw_baseline import build
from .data import prepare
from .train import train
from .evaluate import evaluate
from .export import export
from .runtime_release import verify

ROOT = Path(__file__).resolve().parents[1]


def update(sources, run, steps=400):
    run = Path(run).resolve()
    if run.exists():
        raise FileExistsError("choose a new versioned run directory")
    current = json.loads((ROOT / "work/current-baseline.json").read_text())
    parent = Path(current["checkpoint"])
    old = Path(current["run"]) / "data"
    if hashlib.sha256(parent.read_bytes()).hexdigest() != current["checkpoint_sha256"]:
        raise ValueError("current checkpoint checksum mismatch")
    checkpoint = torch.load(parent, map_location="cpu", weights_only=True)
    cfg = checkpoint["config"]
    if cfg["experiment"] != "dense":
        raise ValueError("this export pipeline requires the dense baseline")
    prior = []
    # Use immutable copies with their original episode names. User downloads
    # can be moved or edited without changing the established training history.
    inputs = run / "prior-source-inputs"
    inputs.mkdir(parents=True)
    for split in ("train", "val", "test"):
        for line in (old / f"{split}.jsonl").read_text(encoding="utf-8").splitlines():
            episode = json.loads(line)
            source = (
                old
                / "sources"
                / (
                    episode["source_sha256"]
                    + Path(episode["source_path"]).suffix.lower()
                )
            )
            if (
                hashlib.sha256(source.read_bytes()).hexdigest()
                != episode["source_sha256"]
            ):
                raise ValueError("immutable prior-source checksum mismatch")
            destination = inputs / (episode["episode_id"] + source.suffix)
            shutil.copy2(source, destination)
            prior.append(destination)
    assignment_file = ROOT / "work/baselines/split-assignments.json"
    assignments = json.loads(assignment_file.read_text())
    previous = dict(assignments)
    report = build(
        prior + list(map(Path, sources)), run / "data", assignments=assignments
    )
    assert all(assignments[key] == value for key, value in previous.items())
    assignment_file.write_text(json.dumps(assignments, indent=2), encoding="utf-8")
    for name in ("vox.model", "vox.vocab", "tokenizer_report.json"):
        shutil.copy2(old / name, run / "data" / name)
    tokenizer = json.loads((run / "data/tokenizer_report.json").read_text())
    tokenizer.update(
        frozen_from=str(parent), current_corpus_digest=report["corpus_digest"]
    )
    (run / "data/tokenizer_report.json").write_text(
        json.dumps(tokenizer, indent=2), encoding="utf-8"
    )
    prepared = prepare(run / "data")
    intake = {
        "batch_files": [str(Path(p).resolve()) for p in sources],
        "batch_count": len(sources),
        "total_unique_episodes": report["episodes"],
        "duplicates_skipped": report["duplicates_skipped"],
        "words": sum(v["words"] for v in report["splits"].values()),
        "segments": sum(v["segments"] for v in report["splits"].values()),
        "splits": {name: value["episodes"] for name, value in report["splits"].items()},
        "prior_holdouts_preserved": True,
        "frozen_tokenizer_sha256": prepared["tokenizer_sha256"],
    }
    (run / "intake-summary.json").write_text(
        json.dumps(intake, indent=2), encoding="utf-8"
    )
    print("INTAKE", json.dumps(intake), flush=True)
    options = dict(
        seq_len=cfg["context"],
        dim=cfg["dim"],
        layers=cfg["layers"],
        heads=cfg["heads"],
        ffn_dim=cfg["ffn_dim"],
        batch=2,
        cores=2,
    )
    train(run / "data", run / "dense", steps=0, init_from=parent, **options)
    before = evaluate(
        run / "data", run / "dense/checkpoint.pt", split="val", samples=64, cores=2
    )
    (run / "before-training.json").write_text(
        json.dumps(before, indent=2), encoding="utf-8"
    )
    print("BEFORE", json.dumps(before), flush=True)
    trained = train(
        run / "data",
        run / "dense",
        steps=steps,
        resume=True,
        save_every=50,
        log_interval=25,
        **options,
    )
    for split in ("val", "test"):
        result = evaluate(
            run / "data", run / "dense/checkpoint.pt", split=split, samples=64, cores=2
        )
        (run / (split + "-final-evaluation.json")).write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        print(split, json.dumps(result), flush=True)
    export(run / "data", run / "dense/checkpoint.pt", run / "export", cores=2)
    return finalize(run)


def finalize(run):
    """Retry export verification after a service outage without training again."""
    run = Path(run).resolve()
    intake = json.loads((run / "intake-summary.json").read_text(encoding="utf-8"))
    before = json.loads((run / "before-training.json").read_text(encoding="utf-8"))
    trained = json.loads(
        (run / "dense/training_report.json").read_text(encoding="utf-8")
    )
    pointer = verify(run, "vox-dialogue-timing:" + run.name.replace("raw-", ""))
    after = json.loads((run / "val-final-evaluation.json").read_text())
    summary = {
        **intake,
        "model": pointer["ollama_model_name"],
        "parameters": trained["parameters"],
        "additional_updates": trained["step"],
        "total_lineage_updates": trained["total_lineage_updates"],
        "before_validation_loss": before["mean_token_loss"],
        "after_validation_loss": after["mean_token_loss"],
        "dialogue_loss_before": before["loss_by_target"]["dialogue"]["mean_loss"],
        "dialogue_loss_after": after["loss_by_target"]["dialogue"]["mean_loss"],
        "timing_loss_before": before["loss_by_target"]["timing"]["mean_loss"],
        "timing_loss_after": after["loss_by_target"]["timing"]["mean_loss"],
        "runtime_verified": True,
        "quality": "Early research weights; loss/runtime checks do not establish fluent conversation or valid speech delivery.",
        "published": False,
    }
    (run / "baseline-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print("SUMMARY", json.dumps(summary), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs="*", type=Path)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--steps", type=int, default=400)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Retry runtime verification for an already trained/exported run",
    )
    args = parser.parse_args()
    if args.verify_only:
        if args.sources:
            parser.error("--verify-only does not accept source files")
        finalize(args.run)
    else:
        if not args.sources:
            parser.error("supply at least one source file")
        update(args.sources, args.run, args.steps)

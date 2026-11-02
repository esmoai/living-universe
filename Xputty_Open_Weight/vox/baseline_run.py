"""Run the raw dialogue/timing baseline pipeline on a supplied capture folder."""

import argparse, json, shutil, hashlib
from datetime import datetime, timezone
from pathlib import Path
from .raw_baseline import build
from .tokenizer import train as train_tokenizer
from .data import prepare
from .train import train
from .evaluate import evaluate
from .export import export


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--output", type=Path, default=Path("work/baselines"))
    initialization = parser.add_mutually_exclusive_group()
    initialization.add_argument(
        "--init-from",
        type=Path,
        help="Continue learned weights with the parent tokenizer frozen",
    )
    initialization.add_argument(
        "--continue-latest",
        action="store_true",
        help="Use work/current-baseline.json as the parent",
    )
    args = parser.parse_args()
    if not args.folder.is_dir():
        raise ValueError("choose a folder of timestamped text captures")
    sources = sorted(
        [
            p
            for p in args.folder.iterdir()
            if p.is_file() and p.suffix.lower() in (".txt", ".md", ".text", ".log")
        ]
    )
    if len(sources) < 3:
        raise ValueError(
            "at least three episode captures are needed for whole-episode holdouts"
        )
    root = args.output / datetime.now(timezone.utc).strftime(
        "baseline-%Y%m%dT%H%M%S%fZ"
    )
    print("Snapshot: " + str(root.resolve()), flush=True)
    manifest = args.output / "split-assignments.json"
    assignments = json.loads(manifest.read_text()) if manifest.exists() else {}
    build(sources, root / "data", assignments=assignments)
    manifest.write_text(json.dumps(assignments, indent=2), encoding="utf-8")
    parent = args.init_from
    if args.continue_latest:
        pointer = Path("work/current-baseline.json")
        if not pointer.is_file():
            raise FileNotFoundError(
                "no current baseline pointer; choose --init-from or start a new base run"
            )
        current = json.loads(pointer.read_text())
        parent = Path(current["checkpoint"])
        if (
            hashlib.sha256(parent.read_bytes()).hexdigest()
            != current["checkpoint_sha256"]
        ):
            raise ValueError("current baseline checksum mismatch")
    if parent:
        parent_data = parent.resolve().parents[1] / "data"
        for name in ("vox.model", "vox.vocab", "tokenizer_report.json"):
            shutil.copy2(parent_data / name, root / "data" / name)
        metadata = json.loads((root / "data/tokenizer_report.json").read_text())
        metadata["frozen_from"] = str(parent.resolve())
        metadata["current_corpus_digest"] = json.loads(
            (root / "data/corpus_report.json").read_text()
        )["corpus_digest"]
        (root / "data/tokenizer_report.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
    else:
        train_tokenizer(root / "data", 4096)
    prepare(root / "data")
    train(
        root / "data",
        root / "dense",
        steps=0,
        seq_len=512,
        dim=128,
        layers=3,
        heads=4,
        ffn_dim=320,
        batch=2,
        cores=2,
        init_from=parent,
    )
    before = evaluate(
        root / "data", root / "dense/checkpoint.pt", split="val", samples=32, cores=2
    )
    (root / "before-training.json").write_text(
        json.dumps(before, indent=2), encoding="utf-8"
    )
    train(
        root / "data",
        root / "dense",
        steps=args.steps,
        seq_len=512,
        dim=128,
        layers=3,
        heads=4,
        ffn_dim=320,
        batch=2,
        cores=2,
        resume=True,
        save_every=25,
    )
    after = evaluate(
        root / "data", root / "dense/checkpoint.pt", split="val", samples=32, cores=2
    )
    (root / "after-training.json").write_text(
        json.dumps(after, indent=2), encoding="utf-8"
    )
    exported = export(
        root / "data", root / "dense/checkpoint.pt", root / "export", cores=2
    )
    from .runtime_release import verify

    pointer = verify(root, "vox-dialogue-timing:" + root.name.lower())
    print(
        json.dumps(
            {
                "run": str(root.resolve()),
                "before_val_loss": before["mean_token_loss"],
                "after_val_loss": after["mean_token_loss"],
                "export": exported,
                "local_model": pointer["ollama_model_name"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

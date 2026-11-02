"""Conservative public-model release checklist; never auto-uploads artifacts."""

from __future__ import annotations
import argparse
import json
from pathlib import Path


def report(root: str | Path) -> dict:
    root = Path(root)
    blockers = []
    notes = []

    def fetch(name):
        f = root / name
        if not f.is_file():
            blockers.append(f"missing {name}")
            return {}
        try:
            return json.loads(f.read_text(encoding="utf8"))
        except (OSError, json.JSONDecodeError):
            blockers.append(f"invalid JSON: {name}")
            return {}

    exported = fetch("export_report.json")
    corpus = fetch("corpus_report.json")
    if not exported.get("release_eligible") or not corpus.get("release_eligible"):
        blockers.append(
            "not eligible for distribution: synthetic, unapproved, or unverified corpus origin"
        )
    if corpus.get("origin") != "real_podcast":
        blockers.append(
            "base must be trained on actual approved podcasts, not synthetic fixtures"
        )
    group_counts = corpus.get("splits", {})
    for split in ("train", "val", "test"):
        if group_counts.get(split, {}).get("episodes", 0) <= 0:
            blockers.append(f"missing disjoint {split} episode set")
    if (
        not (root / "model.safetensors").is_file()
        or not (root / "vox-fibra-f16.gguf").is_file()
    ):
        blockers.append("missing Safetensors and/or GGUF model weights")
    if not (root / "tokenizer.model").is_file():
        blockers.append("missing tokenizer.model")
    for test_key, display in [
        ("verified_ollama", "Ollama"),
        ("verified_llama_cpp", "llama.cpp"),
        ("verified_hf_transformers", "Transformers"),
    ]:
        if not exported.get(test_key):
            blockers.append(
                f"{display} runtime execution not verified (file structure/parity is insufficient)"
            )
    quality = root / "human_evaluation.json"
    if not quality.is_file():
        blockers.append(
            "no independent human conversational quality and safety evaluation"
        )
    else:
        notes.append(
            "human_evaluation.json present: review methodology and threshold manually"
        )
    hardware = root / "hardware_benchmark.json"
    if not hardware.is_file():
        blockers.append("no real two-core / 4 GiB end-to-end CPU benchmark")
    else:
        notes.append(
            "hardware_benchmark.json present: independently validate machine and methodology"
        )
    if corpus.get("origin") == "real_podcast":
        notes.append(
            "A human must also verify actual permissions, provenance, transcripts, and model memorization risks; metadata is not legal proof."
        )
    return {
        "status": "BLOCKED" if blockers else "REQUIRES_MANUAL_SIGNOFF",
        "ready_to_publish": False,
        "blockers": blockers,
        "notes": notes,
        "manual_signoff_required": True,
    }


def main():
    p = argparse.ArgumentParser(
        description="Assess release prerequisites without uploading"
    )
    p.add_argument("--release", required=True)
    args = p.parse_args()
    result = report(args.release)
    print(json.dumps(result, indent=2))
    raise SystemExit(2 if result["blockers"] else 0)


if __name__ == "__main__":
    main()

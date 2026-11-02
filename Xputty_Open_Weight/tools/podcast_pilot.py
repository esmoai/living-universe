"""Collect, review, train and export the actual character-conditioned pilot."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vox.public_baseline import download, sha256, write_json

TEACHER_REV = "91cad51170dc346986eccefdc2dd33a9da36ead9"
TEACHER_SHA = "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e"
TEACHER_REPO = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
TEACHER_FILE = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
TEACHER_TAG = "xputty-podcast-teacher:1.5b-q4"


def teacher(cache, local=None):
    folder = Path(cache) / "teacher"
    folder.mkdir(parents=True, exist_ok=True)
    model = Path(local).resolve() if local else download(
        f"https://huggingface.co/{TEACHER_REPO}/resolve/{TEACHER_REV}/{TEACHER_FILE}", folder / TEACHER_FILE, TEACHER_SHA
    )
    if sha256(model) != TEACHER_SHA:
        raise ValueError("Teacher file does not match the pinned public reference")
    modelfile = folder / "Modelfile"
    modelfile.write_text(f'FROM "{model.as_posix()}"\nPARAMETER num_ctx 2048\n', encoding="utf-8")
    subprocess.run(["ollama", "create", TEACHER_TAG, "-f", str(modelfile)], check=True)
    source = {"model": TEACHER_REPO, "revision": TEACHER_REV, "sha256": TEACHER_SHA,
              "url": f"https://huggingface.co/{TEACHER_REPO}", "license": "Apache-2.0"}
    write_json(folder / "source.json", source)
    return source


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["collect", "review", "train", "convert"])
    p.add_argument("--project", type=Path, required=True)
    p.add_argument("--output", type=Path)
    p.add_argument("--cache", type=Path, default=Path("storage/public-source-cache"))
    p.add_argument("--teacher-gguf", type=Path)
    p.add_argument("--steps", type=int, default=160)
    p.add_argument("--precision", choices=["f16", "q8_0"], default="q8_0")
    a = p.parse_args()
    if a.action == "collect":
        from vox.podcast_distill import collect_distillation
        result = collect_distillation(a.project, TEACHER_TAG, teacher(a.cache, a.teacher_gguf))
        print(json.dumps({"counts": result["counts"], "corpus_sha256": result["corpus_sha256"]}))
    elif a.action == "review":
        if a.output is None:
            p.error("--output must name a fresh reviewed dataset directory")
        from vox.podcast_review import review_snapshot
        result = review_snapshot(a.project, a.output)
        print(json.dumps({"counts": result["counts"], "corpus_sha256": result["corpus_sha256"]}))
    elif a.action == "train":
        if a.output is None:
            p.error("--output must name a new training run directory")
        from vox.public_control import adapt_control
        result = adapt_control(a.project, a.cache, a.output, steps=a.steps, context=256,
                               reference="qwen05", blocks=2, eval_samples=8)
        print(json.dumps({"parameters": result["parameter_count"], "selected_update": result["selected_update"],
                          "before_validation": result["before_validation"], "after_validation": result["after_validation"], "test": result["final_test"]}))
    else:
        from tools.convert_public import convert
        print(json.dumps(convert(a.project, a.cache, a.precision), indent=2))

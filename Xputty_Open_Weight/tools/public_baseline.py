"""Reproduce the isolated public-data research baseline without private transcripts."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "scratch", "control", "evaluate"])
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=Path("storage/public-source-cache"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--count", type=int, default=2000)
    parser.add_argument("--steps", type=int)
    parser.add_argument("--reference", choices=["smollm135", "qwen05"], default="smollm135")
    parser.add_argument("--blocks", type=int, default=4)
    parser.add_argument("--context", type=int, default=256)
    parser.add_argument("--eval-samples", type=int, default=24)
    parser.add_argument("--retain-candidate", action="store_true", help="Also export the final, unselected full model (uses additional disk space)")
    args = parser.parse_args()
    if args.action == "prepare":
        from vox.public_baseline import prepare_public
        report = prepare_public(args.cache, args.project, args.count)
        print(json.dumps({"episodes": report["episodes"], "origin": report["origin"],
                          "splits": {k: {f: v[f] for f in ("episodes", "words")} for k, v in report["splits"].items()}}))
    elif args.action == "scratch":
        from worker import run
        run(args.project, args.steps or 200)
    elif args.action == "control":
        if not args.output:
            parser.error("--output must name a new comparison directory")
        from vox.public_control import adapt_control
        report = adapt_control(args.project, args.cache, args.output, args.steps or 60,
                               args.context, args.reference, args.blocks, args.eval_samples, args.retain_candidate)
        print(json.dumps({k: report[k] for k in ("parameter_count", "selected_update", "after_validation", "final_test")}))
    else:
        if not args.output:
            parser.error("--output must name a model export folder")
        from vox.public_benchmark import evaluate_export
        print(json.dumps(evaluate_export(args.output), indent=2))

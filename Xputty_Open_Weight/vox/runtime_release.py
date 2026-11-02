"""Verify and register local research weights. Never publishes to a remote hub."""

import argparse, hashlib, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify(run, model_name):
    run = Path(run).resolve()
    native_python = Path(
        os.environ.get(
            "XOW_NATIVE_PYTHON", os.environ.get("VOX_NATIVE_PYTHON", sys.executable)
        )
    )
    if not native_python.is_file():
        raise FileNotFoundError(
            "the configured local llama.cpp test environment is missing"
        )
    commands = [
        (
            [
                sys.executable,
                "-X",
                "utf8",
                str(ROOT / "tools/verify_hf_export.py"),
                "--run",
                str(run),
            ],
            "hf-verification.json",
        ),
        (
            [
                str(native_python),
                "-X",
                "utf8",
                str(ROOT / "tools/verify_native_export.py"),
                "--run",
                str(run),
            ],
            "native-verification.json",
        ),
    ]
    for command, report_name in commands:
        subprocess.run(command, cwd=ROOT, check=True)
        report = json.loads((run / report_name).read_text(encoding="utf-8"))
        if not report.get("all_tokenizer_probes_match") or not report.get(
            "logits_match", report.get("logits_match_f16", False)
        ):
            raise ValueError("runtime tokenization/logit parity failed: " + report_name)
    subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(ROOT / "tools/register_ollama_baseline.py"),
            "--run",
            str(run),
            "--name",
            model_name,
        ],
        cwd=ROOT,
        check=True,
    )
    exported = run / "export/export_report.json"
    report = json.loads(exported.read_text())
    report.update(
        verified_ollama=True,
        verified_llama_cpp=True,
        verified_hf_transformers=True,
        runtime_verification_scope="Local loading, tokenizer/logit parity and generation; not conversational quality acceptance.",
    )
    exported.write_text(json.dumps(report, indent=2), encoding="utf-8")
    card = run / "export/README.md"
    text = card.read_text(encoding="utf-8")
    text = text.replace(
        "Native Ollama/llama.cpp inference was not validated by this generator. Run the documented compatibility checks before publishing.",
        "Local Transformers, llama.cpp and Ollama loading/generation verified, with matching tokenizer probes and logits. Natural conversation and speech-delivery quality are not established.",
    )
    card.write_text(text, encoding="utf-8")
    checkpoint = run / "dense/checkpoint.pt"
    pointer = {
        "run": str(run),
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "ollama_model_name": model_name,
        "runtime_verified": True,
    }
    (ROOT / "work/current-baseline.json").write_text(
        json.dumps(pointer, indent=2), encoding="utf-8"
    )
    return pointer


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.run, args.name), indent=2))

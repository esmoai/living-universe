"""Isolated, resumable browser job. Never modifies the donor lab or its weights."""

import argparse, hashlib, json, os, subprocess, sys, time, zipfile
from pathlib import Path


def write(path, value):
    import tempfile

    path = Path(path)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=path.name + ".",
        suffix=".tmp",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        stream.write(json.dumps(value, indent=2))
    try:
        # Windows readers/virus scanners can briefly hold a destination without
        # delete sharing. Retain atomic replacement and retry that narrow case.
        for attempt in range(9):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 8:
                    raise
                time.sleep(min(0.01 * 2**attempt, 0.25))
    finally:
        temporary.unlink(missing_ok=True)


def run(root, steps=400):
    for name in ("DEVICE", "NATIVE_PYTHON", "OLLAMA_VERIFY"):
        if "XOW_" + name in os.environ:
            os.environ["VOX_" + name] = os.environ["XOW_" + name]
    from vox.intake import ingest_file
    from vox.raw_baseline import build
    from vox.tokenizer import train as tokenize
    from vox.data import prepare
    from vox.train import train
    from vox.evaluate import evaluate
    from vox.export import export

    root = Path(root)
    state = json.loads((root / "state.json").read_text())
    ledger = root / "events.jsonl"
    from vox.presets import resolve, policy_for

    try:
        settings = resolve(state)
        mixed = "preset" in state
        if mixed:
            saved = root / "build-settings.json"
            if saved.exists() and json.loads(saved.read_text()) != settings:
                raise ValueError("Build settings are locked to the original experiment")
            write(saved, settings)
    except Exception as error:
        state.update(status="failed", error=str(error))
        write(root / "state.json", state)
        raise

    def phase(label, **details):
        state.update(status="running", phase=label, **details)
        write(root / "state.json", state)
        previous = "0" * 64
        if ledger.exists():
            previous = json.loads(ledger.read_text().splitlines()[-1])["hash"]
        event = {
            "phase": label,
            "time_ns": time.time_ns(),
            "details": details,
            "previous": previous,
        }
        event["hash"] = hashlib.sha256(
            json.dumps(event, sort_keys=True).encode()
        ).hexdigest()
        with ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
        print(label, flush=True)

    try:
        sources = []
        warnings = []
        from materials import source_path

        plain_mode = state.get("mode") == "plain"
        for i, item in enumerate(state["files"]):
            source = source_path(root, item)
            phase("Reading material", file=source.name)
            if plain_mode:
                if source.suffix.lower() not in (".txt", ".md"):
                    raise ValueError(
                        "Plain prose mode requires UTF-8 TXT or Markdown working copies"
                    )
                sources.append(source)
                continue
            out = root / "intake" / str(i)
            out.parent.mkdir(exist_ok=True)
            if not (out / "candidate_turns.jsonl").exists():
                ingest_file(source, out)
            rows = [
                json.loads(line)
                for line in (out / "candidate_turns.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            ]
            # Captured dialogue has unknown speakers; retain source timing without inventing turns.
            if len(rows) < 2:
                warnings.append(
                    source.name
                    + ": fewer than two extracted segments; excluded from training"
                )
                continue
            folder = root / "normalized"
            folder.mkdir(exist_ok=True)
            target = folder / (source.stem + ".txt")
            lines = []
            for row in rows:
                if row.get("start_ms") is not None:
                    ms = int(row["start_ms"])
                    s, ms = divmod(ms, 1000)
                    m, s = divmod(s, 60)
                    h, m = divmod(m, 60)
                    lines.append(f"{h:02}:{m:02}:{s:02}.{ms:03}")
                lines.append(row["text"])
            target.write_text("\n".join(lines), encoding="utf-8")
            sources.append(target)
        phase("Preparing episodes", warnings=warnings)
        if not (root / "data/prepared_report.json").exists():
            if (root / "data").exists():
                import shutil

                shutil.rmtree(root / "data")  # owned derived directory only
            if plain_mode:
                from vox.plain_text import build as build_plain

                provenance_path = root / "historical-sources.json"
                if (root / "public-sources.json").exists():
                    provenance_path = root / "public-sources.json"
                provenance = (
                    json.loads(provenance_path.read_text(encoding="utf-8"))
                    if provenance_path.exists()
                    else {}
                )
                report = build_plain(sources, root / "data", provenance=provenance)
            else:
                report = build(sources, root / "data")
            tokenizer_report = tokenize(root / "data", settings["vocab_size"])
            if (
                settings["preset"] == "research-48m-v1"
                and tokenizer_report["vocab_size"] != 8192
            ):
                raise ValueError(
                    "This material cannot support the 8,192-token vocabulary. Add more varied text in a new project, or choose the quick pipeline preset."
                )
            prepare(root / "data")
        report = json.loads((root / "data/corpus_report.json").read_text())
        phase("Training", episodes=report["episodes"], steps=steps)
        options = dict(
            seq_len=settings["max_context"],
            dim=settings["dim"],
            layers=settings["layers"],
            heads=settings["heads"],
            ffn_dim=settings["ffn_dim"],
            batch=settings["micro_batch"],
            cores=2,
            lr=settings["lr"],
            max_context=settings["max_context"],
            training_policy=policy_for(settings) if mixed else None,
        )
        eval_windows = settings["windows"] if mixed else [512]

        def assess(split):
            by_context = {
                str(n): evaluate(
                    root / "data",
                    checkpoint,
                    split=split,
                    samples=settings["eval_samples"] if mixed else 32,
                    cores=2,
                    context=n,
                )
                for n in eval_windows
            }
            summary = dict(by_context[str(max(eval_windows))])
            summary["by_context"] = by_context
            return summary

        checkpoint = root / "dense/checkpoint.pt"
        if not checkpoint.exists():
            train(root / "data", root / "dense", steps=0, **options)
            write(
                root / "before.json",
                assess("val"),
            )
        trained = train(
            root / "data",
            root / "dense",
            steps=steps,
            resume=True,
            save_every=settings["save_every"],
            log_interval=5 if mixed else 25,
            **options,
        )
        if (root / "stop-request").exists():
            state.update(
                status="stopped", phase=f"Stopped; saved update {trained['step']}"
            )
            write(root / "state.json", state)
            (root / "stop-request").unlink(missing_ok=True)
            return
        phase("Evaluating")
        metrics = {s: assess(s) for s in ["val", "test"]}
        write(root / "metrics.json", metrics)
        phase("Exporting")
        export(root / "data", checkpoint, root / "export", cores=2)
        if (root / "build-settings.json").exists():
            import shutil

            shutil.copy2(
                root / "build-settings.json", root / "export/build-settings.json"
            )
        # Exported weights can be opened independently, without the training checkpoint.
        import shutil

        shutil.copy2("export_chat.py", root / "export/chat.py")
        shutil.copy2("LICENSE", root / "export/LICENSE")
        if (root / "historical-sources.json").exists():
            shutil.copy2(
                root / "historical-sources.json",
                root / "export/historical-sources.json",
            )
        if (root / "public-sources.json").exists():
            shutil.copy2(root / "public-sources.json", root / "export/public-sources.json")
            shutil.copy2(root / "UPSTREAM-DATASET-CARD.md", root / "export/UPSTREAM-DATASET-CARD.md")
        phase("Checking Transformers")
        subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                "tools/verify_hf_export.py",
                "--run",
                str(root),
            ],
            check=True,
        )
        hf = json.loads((root / "hf-verification.json").read_text())
        if not hf["logits_match"] or not hf["all_tokenizer_probes_match"]:
            raise ValueError("Export parity check failed")
        checks = {
            "transformers": "passed",
            "llama_cpp": "not installed",
            "ollama": "not checked",
        }
        import importlib.util

        native_python = os.environ.get("VOX_NATIVE_PYTHON")
        if native_python or importlib.util.find_spec("llama_cpp"):
            subprocess.run(
                [
                    native_python or sys.executable,
                    "-X",
                    "utf8",
                    "tools/verify_native_export.py",
                    "--run",
                    str(root),
                ],
                check=True,
            )
            native = json.loads((root / "native-verification.json").read_text())
            if (
                not native["all_tokenizer_probes_match"]
                or not native["logits_match_f16"]
            ):
                raise ValueError("Native export parity check failed")
            checks["llama_cpp"] = "passed"
        if os.environ.get("VOX_OLLAMA_VERIFY", "auto") != "0":
            import urllib.request

            try:
                with urllib.request.urlopen(
                    "http://127.0.0.1:11434/api/version", timeout=2
                ):
                    pass
            except OSError:
                checks["ollama"] = "service unavailable"
            else:
                subprocess.run(
                    [
                        sys.executable,
                        "-X",
                        "utf8",
                        "tools/register_ollama_baseline.py",
                        "--run",
                        str(root),
                        "--name",
                        "vox-browser:" + root.name,
                    ],
                    check=True,
                )
                ollama = json.loads((root / "ollama-verification.json").read_text())
                if not ollama.get("done"):
                    raise ValueError("Ollama generation did not complete")
                checks["ollama"] = "passed"
        phase("Packaging", checks=checks)
        export_report = json.loads((root / "export/export_report.json").read_text())
        export_report.update(
            verified_hf_transformers=True,
            verified_llama_cpp=checks["llama_cpp"] == "passed",
            verified_ollama=checks["ollama"] == "passed",
        )
        write(root / "export/export_report.json", export_report)
        card = root / "export/README.md"
        text = card.read_text(encoding="utf-8")
        text += (
            "\nBrowser build verification: Transformers tokenizer/logit parity passed. Native llama.cpp: "
            + checks["llama_cpp"]
            + ". Ollama: "
            + checks["ollama"]
            + ". See export_report.json.\n"
        )
        card.write_text(text, encoding="utf-8")
        training = json.loads((root / "dense/training_report.json").read_text())
        card.write_text(
            card.read_text(encoding="utf-8")
            + "\nActual context updates: "
            + json.dumps(training.get("context_updates", {}))
            + ". Maximum configured context is not proof of long-context quality. See reports/training_report.json.\n",
            encoding="utf-8",
        )
        with zipfile.ZipFile(root / "model.zip", "w", zipfile.ZIP_DEFLATED) as z:
            for file in (root / "export").iterdir():
                if file.is_file():
                    z.write(file, "model/" + file.name)
            for name in [
                "metrics.json",
                "before.json",
                "hf-verification.json",
                "events.jsonl",
            ]:
                z.write(root / name, "reports/" + name)
            for name in ["native-verification.json", "ollama-verification.json"]:
                if (root / name).exists():
                    z.write(root / name, "reports/" + name)
            z.write(root / "dense/training_report.json", "reports/training_report.json")
        phase("Ready", metrics=metrics, checks=checks)
        state.update(status="complete", file=None)
        write(root / "state.json", state)
    except Exception as error:
        state.update(status="failed", error=str(error))
        write(root / "state.json", state)
        raise


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("--steps", type=int, default=400)
    a = p.parse_args()
    run(a.root.resolve(), a.steps)

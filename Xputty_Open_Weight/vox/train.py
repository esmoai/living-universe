"""Reproducible 2-CPU, 4 GB budget from-scratch train / continued chat training.

Never loads external pretrained weights. Resume only from own checkpoint with matching
corpus/tokenizer digest. A training run is NOT a production-quality model claim.
"""

import argparse, hashlib, json, os, random, time, signal
from dataclasses import asdict
from pathlib import Path
import numpy as np
from .limits import limit_cpu, memory_guard, environment
from .model import ModelConfig, TinyLlama
from .data import CorpusSamples


def atomic_torch_save(obj, path, torch):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    torch.save(obj, tmp)
    os.replace(tmp, p)


def progress_json(path, value):
    import tempfile

    path = Path(path)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(json.dumps(value))
    try:
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


def train(
    data_dir,
    run_dir,
    stage="base",
    experiment="dense",
    steps=50,
    seq_len=128,
    dim=128,
    layers=3,
    heads=4,
    ffn_dim=320,
    batch=2,
    lr=0.0005,
    seed=739,
    cores=2,
    limit_gb=4,
    resume=False,
    log_interval=10,
    context_turns=3,
    save_every=200,
    init_from=None,
    max_context=None,
    training_policy=None,
):
    # Limit before heavy initialization.
    torch = limit_cpu(cores)
    memory_guard(limit_gb)
    d = Path(data_dir)
    r = Path(run_dir)
    r.mkdir(parents=True, exist_ok=True)
    report = json.loads((d / "prepared_report.json").read_text())
    if report["origin"] == "public_conversation_text":
        run_kind = "public_conversation_scratch_experiment"
    elif report.get("representation") == "plain-text-works-v1":
        run_kind = "historical_plain_text_experiment"
    elif report["origin"] == "user_supplied_raw_dialogue":
        run_kind = "raw_dialogue_timing_experiment"
    elif not report["release_eligible"]:
        run_kind = "synthetic_smoke"
    else:
        run_kind = "approved_podcast_experiment"
    if stage not in ("base", "chat"):
        raise ValueError("unknown stage")
    if stage == "base" and resume and not (r / "checkpoint.pt").exists():
        raise ValueError("no checkpoint to resume")
    if stage == "chat" and not (r / "checkpoint.pt").exists():
        raise ValueError("chat specialization requires an existing base checkpoint")
    config = ModelConfig(
        vocab_size=int(
            __import__("sentencepiece")
            .SentencePieceProcessor(model_file=str(d / "vox.model"))
            .get_piece_size()
        ),
        dim=dim,
        layers=layers,
        heads=heads,
        ffn_dim=ffn_dim,
        context=max_context or seq_len,
        experiment=experiment,
    )
    import torch.nn.utils as nn_utils

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    device = os.environ.get("VOX_DEVICE", "auto")
    device = (
        "cuda"
        if device == "auto" and torch.cuda.is_available()
        else "cpu"
        if device == "auto"
        else device
    )
    if device not in ("cpu", "cuda"):
        raise ValueError("VOX_DEVICE must be auto, cpu or cuda")
    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA requested but unavailable")
    model = TinyLlama(config).to(device)
    model.gradient_checkpointing = bool(
        training_policy and training_policy.get("activation_checkpointing")
    )
    if training_policy:
        from .presets import window_for_step, learning_rate, digest

        if any(n > config.context for n in training_policy["windows"]):
            raise ValueError("Training window exceeds architectural context")
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.05)
    start_step = 0
    prior = []
    ckpt = r / "checkpoint.pt"
    parent_lineage = {}
    if init_from is not None:
        if resume or ckpt.exists() or stage != "base":
            raise ValueError(
                "weights-only initialization requires a new base run, not resume or chat"
            )
        parent = torch.load(init_from, map_location="cpu", weights_only=True)
        if (
            parent["tokenizer_sha256"] != report["tokenizer_sha256"]
            or asdict(config) != parent["config"]
        ):
            raise ValueError(
                "parent checkpoint tokenizer/architecture mismatch; keep its frozen tokenizer"
            )
        if parent.get("timing_mode", "none") != report.get(
            "timing_mode", "none"
        ) or parent.get("representation", "reviewed-speaker-turns") != report.get(
            "representation", "reviewed-speaker-turns"
        ):
            raise ValueError(
                "parent checkpoint dialogue/timing representation mismatch"
            )
        model.load_state_dict(parent["weights"], strict=True)
        parent_lineage = {
            "parent_checkpoint_sha256": hashlib.sha256(
                Path(init_from).read_bytes()
            ).hexdigest(),
            "parent_corpus_digest": parent["report_digest"],
            "parent_lineage_updates": parent.get(
                "total_lineage_updates", parent["step"]
            ),
            "initialization": "weights-only-new-corpus; optimizer reset",
        }
    if ckpt.exists():
        if not resume and stage == "base":
            raise FileExistsError(
                f"{ckpt} exists; use --resume or a new --run directory"
            )
        prev = torch.load(ckpt, map_location="cpu", weights_only=True)
        if (
            prev["report_digest"] != report["corpus_digest"]
            or prev["tokenizer_sha256"] != report["tokenizer_sha256"]
        ):
            raise ValueError("checkpoint corpus/tokenizer mismatch")
        if prev.get("timing_mode", "none") != report.get("timing_mode", "none"):
            raise ValueError("checkpoint timing serialization mismatch")
        if asdict(config) != prev["config"]:
            raise ValueError("checkpoint model architecture mismatch")
        if prev.get("training_policy") != training_policy:
            raise ValueError(
                "Training policy differs from the saved checkpoint; keep its windows, budget and learning-rate schedule"
            )
        model.load_state_dict(prev["weights"])
        if stage == prev["stage"]:
            optimizer.load_state_dict(prev["optimizer"])
            start_step = prev["step"]
        elif stage == "chat" and prev["stage"] == "base":
            # New curriculum stage: reset optimizer but inherit trained weights.
            pass
        else:
            raise ValueError("invalid stage transition")
        prior = prev.get("history", [])
        parent_lineage = prev.get("parent_lineage", {})
    lengths = training_policy["windows"] if training_policy else [seq_len]
    train_sets = {
        n: CorpusSamples(d, "train", n, stage, context_turns) for n in lengths
    }
    val_sets = {n: CorpusSamples(d, "val", n, stage, context_turns) for n in lengths}
    context_counts = dict(prev.get("context_updates", {})) if ckpt.exists() else {}
    processed_tokens = (
        int(prev.get("cumulative_tokens_processed", prev.get("tokens_processed", 0)))
        if ckpt.exists()
        else 0
    )
    actual_targets = (
        int(prev.get("cumulative_target_tokens", 0)) if ckpt.exists() else 0
    )
    original_processed = processed_tokens
    model.train()
    maxrss = 0
    start = time.perf_counter()
    history = []
    stop_requested = [False]
    previous_handler = None
    try:
        previous_handler = signal.getsignal(signal.SIGINT)
        signal.signal(
            signal.SIGINT, lambda signum, frame: stop_requested.__setitem__(0, True)
        )
    except ValueError:
        pass  # Signals are only available from the main thread.

    def checkpoint(done):
        total = time.perf_counter() - start
        result = dict(
            config=asdict(config),
            weights={
                k: v.detach().cpu().clone() for k, v in model.state_dict().items()
            },
            optimizer=optimizer.state_dict(),
            tokenizer_sha256=report["tokenizer_sha256"],
            report_digest=report["corpus_digest"],
            stage=stage,
            step=int(done),
            run_kind=run_kind,
            release_eligible=report["release_eligible"],
            seed=seed,
            history=(prior + history)[-300:],
            elapsed_seconds=total,
            peak_rss_bytes=maxrss,
            timing_mode=report.get("timing_mode", "none"),
            representation=report.get("representation", "reviewed-speaker-turns"),
            parent_lineage=parent_lineage,
            total_lineage_updates=parent_lineage.get("parent_lineage_updates", 0)
            + int(done),
            tokens_processed=processed_tokens - original_processed,
            cumulative_tokens_processed=processed_tokens,
            cumulative_target_tokens=actual_targets,
            context_updates=context_counts,
            training_policy=training_policy,
            training_policy_sha256=digest(training_policy) if training_policy else None,
            framework="pytorch-weights-only-new-corpus"
            if init_from
            else "pytorch-from-random-init"
            if not resume and stage == "base"
            else "pytorch-resume",
            environment=environment(),
        )
        atomic_torch_save(result, ckpt, torch)
        summary = {k: v for k, v in result.items() if k not in ("weights", "optimizer")}
        summary["parameters"] = model.n_parameters()
        (r / "training_report.json").write_text(json.dumps(summary, indent=2) + "\n")
        return summary

    done = start_step
    for step in range(start_step, int(steps)):
        if (r.parent / "stop-request").exists():
            stop_requested[0] = True
            break
        window = (
            window_for_step(training_policy, step, seed) if training_policy else seq_len
        )
        accumulation = (
            max(
                1,
                (training_policy["tokens_per_update"] + batch * window - 1)
                // (batch * window),
            )
            if training_policy
            else 1
        )
        if training_policy:
            for group in optimizer.param_groups:
                group["lr"] = learning_rate(training_policy, step, lr)
        optimizer.zero_grad(set_to_none=True)
        accumulated_loss = 0.0
        step_started = time.perf_counter()
        for micro in range(accumulation):
            xs, ys = [], []
            for j in range(batch):
                # A stable seed per update/microbatch makes resume independent of earlier window lengths.
                sample_step = (
                    step * batch + j
                    if not training_policy
                    else step * 100000 + micro * batch + j
                )
                x, y, info = train_sets[window].sample(sample_step, seed)
                xs.append(x)
                ys.append(y)
                actual_targets += info["loss_tokens"]
            x = torch.tensor(np.stack(xs), dtype=torch.long, device=device)
            y = torch.tensor(np.stack(ys), dtype=torch.long, device=device)
            _, loss = model(x, y)
            if not torch.isfinite(loss):
                raise ValueError("non-finite training loss")
            (loss / accumulation).backward()
            accumulated_loss += float(loss.detach()) / accumulation
            processed_tokens += batch * window
        nn_utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        if (r.parent / "stop-request").exists():
            stop_requested[0] = True
        peak = memory_guard(limit_gb)
        maxrss = max(maxrss, peak)
        done = step + 1
        context_counts[str(window)] = context_counts.get(str(window), 0) + 1
        elapsed = time.perf_counter() - start
        rec = {
            "step": done,
            "train_loss": round(accumulated_loss, 6),
            "elapsed_seconds": round(elapsed, 3),
            "rss_bytes": peak,
            "context_tokens": window,
            "microbatches": accumulation,
            "learning_rate": optimizer.param_groups[0]["lr"],
            "tokens_per_second": round(
                batch
                * window
                * accumulation
                / max(0.001, time.perf_counter() - step_started),
                2,
            ),
        }
        if done % log_interval == 0 or step == start_step or done == steps:
            model.eval()
            with torch.inference_mode():
                vx, vy, _ = val_sets[window].sample(step + 100000, seed)
                _, vl = model(
                    torch.tensor(vx[None, :], device=device),
                    torch.tensor(vy[None, :], device=device),
                )
            rec["val_loss"] = round(float(vl), 6)
            model.train()
            print(json.dumps(rec), flush=True)
            history.append(rec)
            progress_json(
                r / "progress.json",
                {
                    **rec,
                    "target_updates": int(steps),
                    "cumulative_tokens_processed": processed_tokens,
                    "context_updates": context_counts,
                },
            )
        if done % save_every == 0 or stop_requested[0]:
            checkpoint(done)
            if stop_requested[0]:
                print(
                    "Graceful stop requested; checkpoint saved at step",
                    done,
                    flush=True,
                )
                break
    summary = checkpoint(done)
    if previous_handler is not None:
        try:
            signal.signal(signal.SIGINT, previous_handler)
        except ValueError:
            pass
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Vox FIBRA R02 from scratch CPU training")
    p.add_argument("--data", required=True)
    p.add_argument("--run", required=True)
    p.add_argument("--stage", choices=["base", "chat"], default="base")
    p.add_argument(
        "--experiment",
        choices=["dense", "fibra", "fibra-golden", "phi-pos"],
        default="dense",
    )
    p.add_argument("--steps", type=int, default=50)
    p.add_argument(
        "--preset",
        choices=["research-48m-v1", "tiny-1m-v1"],
        help="Preset controls architecture and mixed-context schedule",
    )
    p.add_argument("--seq-len", type=int, default=128)
    p.add_argument("--dim", type=int, default=128)
    p.add_argument("--layers", type=int, default=3)
    p.add_argument("--heads", type=int, default=4)
    p.add_argument("--ffn-dim", type=int, default=320)
    p.add_argument("--batch", type=int, default=2)
    p.add_argument("--lr", type=float, default=0.0005)
    p.add_argument("--seed", type=int, default=739)
    p.add_argument("--cores", type=int, default=2)
    p.add_argument("--limit-gb", type=float, default=4)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--log-interval", type=int, default=10)
    p.add_argument("--save-every", type=int, default=200)
    p.add_argument(
        "--init-from",
        help="Explicit weights-only initialization with a frozen matching tokenizer; permits a new corpus",
    )
    a = p.parse_args()
    extra = {}
    if a.preset:
        from .presets import resolve, policy_for

        chosen = resolve({"preset": a.preset})
        a.seq_len = chosen["max_context"]
        a.dim, a.layers, a.heads, a.ffn_dim = (
            chosen["dim"],
            chosen["layers"],
            chosen["heads"],
            chosen["ffn_dim"],
        )
        a.batch, a.lr = chosen["micro_batch"], chosen["lr"]
        extra = {
            "max_context": chosen["max_context"],
            "training_policy": policy_for(chosen),
        }
    s = train(
        a.data,
        a.run,
        a.stage,
        a.experiment,
        a.steps,
        a.seq_len,
        a.dim,
        a.layers,
        a.heads,
        a.ffn_dim,
        a.batch,
        a.lr,
        a.seed,
        a.cores,
        a.limit_gb,
        a.resume,
        a.log_interval,
        save_every=a.save_every,
        init_from=a.init_from,
        **extra,
    )
    print(
        json.dumps(
            {
                k: s[k]
                for k in (
                    "run_kind",
                    "step",
                    "parameters",
                    "elapsed_seconds",
                    "peak_rss_bytes",
                    "release_eligible",
                )
            },
            indent=2,
        )
    )

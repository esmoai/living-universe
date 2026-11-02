"""Held-out episode token evaluation; no memorized prompt-output showcase claims."""

import argparse, json, math, time
from pathlib import Path
import numpy as np
from .limits import limit_cpu, rss_bytes
from .data import CorpusSamples
from .model import ModelConfig, TinyLlama
from .tokenizer import sha256


def evaluate(data, ckpt, split="test", samples=60, cores=2, context=None):
    torch = limit_cpu(cores)
    ckp = torch.load(ckpt, map_location="cpu", weights_only=True)
    prepared = json.loads((Path(data) / "prepared_report.json").read_text())
    if (
        ckp["tokenizer_sha256"] != sha256(Path(data) / "vox.model")
        or ckp["report_digest"] != prepared["corpus_digest"]
    ):
        raise ValueError("evaluation checkpoint/tokenizer/corpus mismatch")
    if ckp.get("timing_mode", "none") != prepared.get("timing_mode", "none"):
        raise ValueError("evaluation timing serialization mismatch")
    if samples < 1:
        raise ValueError("samples must be positive")
    c = ModelConfig(**ckp["config"])
    model = TinyLlama(c)
    model.load_state_dict(ckp["weights"])
    model.eval()
    window = context or c.context
    if not 16 <= window <= c.context:
        raise ValueError("Evaluation window is outside the model context")
    ds = CorpusSamples(data, split, window, stage=ckp["stage"])
    results = []
    t0 = time.perf_counter()
    role_totals = {
        name: {"tokens": 0, "loss_sum": 0.0}
        for name in ("structure", "timing", "dialogue")
    }
    with torch.inference_mode():
        for j in range(samples):
            x, y, info = ds.sample(j, ckp["seed"] + 17)
            logits, loss = model(torch.tensor(x[None, :]), torch.tensor(y[None, :]))
            results.append((float(loss), info))
            if "target_roles" in info:
                per_token = torch.nn.functional.cross_entropy(
                    logits[0].float(),
                    torch.tensor(y),
                    ignore_index=-100,
                    reduction="none",
                )
                roles = np.array(info["target_roles"])
                for role, name in enumerate(("structure", "timing", "dialogue")):
                    mask = (roles == role) & (y >= 0)
                    role_totals[name]["tokens"] += int(mask.sum())
                    role_totals[name]["loss_sum"] += float(
                        per_token[torch.tensor(mask)].sum()
                    )
    mean = sum(loss * info["loss_tokens"] for loss, info in results) / sum(
        info["loss_tokens"] for _, info in results
    )
    out = dict(
        split=split,
        episode_disjoint=True,
        origin=ckp["run_kind"],
        samples=samples,
        context_tokens=window,
        mean_token_loss=round(mean, 5),
        approx_perplexity=round(math.exp(min(mean, 40)), 3),
        duration_seconds=round(time.perf_counter() - t0, 3),
        final_rss_bytes=rss_bytes(),
        loss_aggregation="weighted_by_unmasked_target_tokens",
        sample_episode_ids=sorted(set(r[1]["episode_id"] for r in results)),
        warning="Conversation-disjoint public synthetic dialogue holdout. Token loss does not establish relevance, factual accuracy or natural speech."
        if ckp["run_kind"] == "public_conversation_scratch_experiment"
        else "Whole-work historical prose holdout. Prediction loss does not establish chat quality or historical accuracy."
        if ckp["run_kind"] == "historical_plain_text_experiment"
        else "Raw supplied-dialogue experiment: loss does not establish useful conversation or speech timing"
        if ckp["run_kind"] == "raw_dialogue_timing_experiment"
        else "TECHNICAL DIAGNOSTIC only: short synthetic fixture results do not establish natural dialogue quality"
        if not ckp["release_eligible"]
        else "Model must also pass held-out human evaluation",
    )
    out["loss_by_target"] = {
        name: {
            "tokens": value["tokens"],
            "mean_loss": round(value["loss_sum"] / value["tokens"], 6),
        }
        for name, value in role_totals.items()
        if value["tokens"]
    }
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--split", choices=["val", "test"], default="test")
    p.add_argument("--samples", type=int, default=60)
    p.add_argument("--cores", type=int, default=2)
    a = p.parse_args()
    print(
        json.dumps(
            evaluate(a.data, a.checkpoint, a.split, a.samples, a.cores), indent=2
        )
    )

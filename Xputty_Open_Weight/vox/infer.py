"""Local CPU inferencing, warm vs cold timing. This is TEXT ONLY."""

import argparse, json, time
from pathlib import Path
from .model import ModelConfig, TinyLlama, generate
from .limits import limit_cpu, rss_bytes
import sentencepiece as spm


def load_model(data_dir, checkpoint, cores=2):
    torch = limit_cpu(cores)
    x = torch.load(checkpoint, map_location="cpu", weights_only=True)
    c = ModelConfig(**x["config"])
    model = TinyLlama(c)
    model.load_state_dict(x["weights"], strict=True)
    model.eval()
    sp = spm.SentencePieceProcessor(model_file=str(Path(data_dir) / "vox.model"))
    if sp.get_piece_size() != c.vocab_size:
        raise ValueError("tokenizer vocab mismatch")
    from .tokenizer import sha256

    if x["tokenizer_sha256"] != sha256(Path(data_dir) / "vox.model"):
        raise ValueError("tokenizer SHA mismatch")
    return model, sp, x


def complete(data, ckpt, prompt, history=None, max_new_tokens=40, cores=2, seed=739):
    start = time.perf_counter()
    model, sp, meta = load_model(data, ckpt, cores)
    load_ms = (time.perf_counter() - start) * 1000
    raw_mode = meta.get("representation") == "unlabelled-dialogue-timing-v1"
    if raw_mode:
        from .dialogue_format import raw_prompt

        ctx = raw_prompt(prompt, history or "")
    else:
        ctx = (history or "") + "<|turn|><|sp0|>" + prompt.strip() + "\n<|turn|><|sp1|>"
    ids = sp.encode(ctx, out_type=int)[-model.config.context + max_new_tokens :]
    token_start = time.perf_counter()
    metrics = {}
    stop = {sp.piece_to_id("<|eod|>")}
    if not raw_mode:
        stop.add(sp.piece_to_id("<|turn|>"))
    out = generate(
        model,
        ids,
        max_new_tokens=max_new_tokens,
        stop_id=stop,
        seed=seed,
        metrics=metrics,
    )
    gen_s = time.perf_counter() - token_start
    text = sp.decode(out)
    if "<|turn|>" in text:
        text = text.split("<|turn|>")[0]
    result = dict(
        response=text.strip(),
        model_kind=meta["run_kind"],
        prompt_tokens=len(ids),
        response_tokens=len(out),
        cold_load_ms=round(load_ms, 3),
        generation_ms=round(gen_s * 1000, 3),
        tokens_per_second=round(len(out) / max(0.001, gen_s), 2),
        peak_observed_rss_bytes=rss_bytes(),
    )
    if raw_mode:
        from .dialogue_format import parse_raw_generation

        result["dialogue_timing"] = parse_raw_generation(text)
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--prompt", required=True)
    p.add_argument("--tokens", type=int, default=32)
    p.add_argument("--cores", type=int, default=2)
    a = p.parse_args()
    print(
        json.dumps(
            complete(
                a.data, a.checkpoint, a.prompt, max_new_tokens=a.tokens, cores=a.cores
            ),
            indent=2,
        )
    )

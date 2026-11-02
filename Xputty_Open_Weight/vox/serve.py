"""Persistent warm CPU process. Accepts one JSON request per line on stdin.

No network, internet, account, or voice engine. Designed to receive R01 packet data.
"""

import argparse, json, sys, time
from .infer import load_model
from .model import generate
from .limits import rss_bytes


def serve(data, checkpoint, cores=2):
    start = time.perf_counter()
    model, sp, meta = load_model(data, checkpoint, cores)
    load_ms = (time.perf_counter() - start) * 1000
    print(
        json.dumps(
            {
                "event": "READY",
                "parameters": model.n_parameters(),
                "cold_load_ms": round(load_ms, 3),
                "run_kind": meta["run_kind"],
            }
        ),
        flush=True,
    )
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            if req.get("command") == "quit":
                print(json.dumps({"event": "BYE"}), flush=True)
                break
            raw = str(req.get("text", "")).strip()
            if not raw:
                raise ValueError("text is required")
            memory = str(req.get("context", ""))[:3000].strip()
            n = max(1, min(80, int(req.get("max_new_tokens", 32))))
            # Memory is only dialogue-like source text; no giant system prompt.
            prefix = "<|turn|><|sp0|>" + memory + "\n" if memory else ""
            text = prefix + "<|turn|><|sp0|>" + raw + "\n<|turn|><|sp1|>"
            ids = sp.encode(text, out_type=int)[-max(1, model.config.context - n) :]
            t0 = time.perf_counter()
            metrics = {}
            tok = generate(
                model,
                ids,
                max_new_tokens=n,
                stop_id={sp.piece_to_id("<|eod|>"), sp.piece_to_id("<|turn|>")},
                seed=req.get("seed"),
                metrics=metrics,
            )
            elapsed = time.perf_counter() - t0
            out = sp.decode(tok)
            if "<|turn|>" in out:
                out = out.split("<|turn|>")[0]
            print(
                json.dumps(
                    {
                        "event": "RESPONSE",
                        "id": req.get("id"),
                        "text": out.strip(),
                        "prompt_tokens": len(ids),
                        "output_tokens": len(tok),
                        "generation_ms": round(elapsed * 1000, 3),
                        "time_to_first_token_ms": round(
                            metrics.get("first_token_ms", 0), 3
                        ),
                        "tokens_per_second": round(len(tok) / max(elapsed, 0.001), 3),
                        "rss_bytes": rss_bytes(),
                        "is_smoke": meta["run_kind"] == "synthetic_smoke",
                    }
                ),
                flush=True,
            )
        except Exception as e:
            print(json.dumps({"event": "ERROR", "message": str(e)}), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--cores", type=int, default=2)
    a = p.parse_args()
    serve(a.data, a.checkpoint, a.cores)

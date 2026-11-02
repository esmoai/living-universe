"""Actual CPU-native file size, generation and behavioral probes; no quality proxy claims."""
import argparse
import json
import statistics
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vox.public_baseline import sha256, write_json
from vox.public_benchmark import PROBES, indicators
from export_chat import framed_messages


def request(route, body, timeout=180):
    req = urllib.request.Request("http://127.0.0.1:11434/api/" + route,
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def benchmark(folder, model, precision):
    folder = Path(folder)
    conversion = json.loads((folder / ("conversion-" + precision + ".json")).read_text())
    gguf = folder / ("model-" + precision + ".gguf")
    checksum = sha256(gguf)
    if checksum != conversion["output_sha256"] or checksum not in request("show", {"model": model})["modelfile"]:
        raise ValueError("The registered model does not match the exported quantized weights")
    metadata = json.loads((folder / "export_report.json").read_text(encoding="utf-8"))
    request("generate", {"model": model, "keep_alive": 0})
    rows = []
    for index, probe in enumerate(PROBES):
        messages, persona = framed_messages({"messages": probe["messages"]}, metadata.get("persona_profiles", {}), metadata.get("persona_rules", ""))
        payload = {"model": model, "messages": messages, "stream": False, "keep_alive": "5m",
                   "options": {"num_ctx": 1024, "num_predict": 96, "num_thread": 2, "num_gpu": 0,
                               "temperature": 0, "seed": 739}}
        started = time.perf_counter()
        result = request("chat", payload)
        text = result["message"]["content"]
        row = {**probe, "response": text, "wall_seconds": time.perf_counter() - started,
               "load_seconds": result.get("load_duration", 0) / 1e9,
               "prefill_seconds": result.get("prompt_eval_duration", 0) / 1e9,
               "decode_seconds": result.get("eval_duration", 0) / 1e9,
               "prompt_tokens": result.get("prompt_eval_count"), "output_tokens": result.get("eval_count"),
               "done_reason": result.get("done_reason"), **indicators(text, probe)}
        row["decode_tokens_per_second"] = row["output_tokens"] / max(row["decode_seconds"], 1e-9)
        rows.append(row)
        print(json.dumps({"probe": probe["id"], "response": text, "seconds": round(row["wall_seconds"], 3)}), flush=True)
    warm = [r["wall_seconds"] for r in rows[1:]]
    report = {"schema": "xow-native-benchmark/1", "model": model, "precision": precision,
              "gguf_sha256": checksum, "file_bytes": gguf.stat().st_size,
              "source_weights_sha256": conversion["input_weights_sha256"], "probes": rows,
              "cold_request_seconds": rows[0]["wall_seconds"], "warm_median_seconds": statistics.median(warm),
              "median_decode_tokens_per_second": statistics.median(r["decode_tokens_per_second"] for r in rows),
              "conditions": "CPU only, two threads, 1024 context, greedy, 96 response-token maximum, sequential independent requests",
              "limitations": ["Eight probes do not establish broad factual accuracy or podcast quality",
                              "Keyword indicators are diagnostics, not correctness scores",
                              "Prefill/load phases are not measured first-audio or end-to-end podcast latency",
                              "Full responses require human review; quantization is not knowledge distillation"]}
    write_json(folder / ("native-evaluation-" + precision + ".json"), report)
    return {k: report[k] for k in ("precision", "file_bytes", "cold_request_seconds", "warm_median_seconds", "median_decode_tokens_per_second")}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--tag", required=True)
    p.add_argument("--precision", choices=["f16", "q8_0"], required=True)
    a = p.parse_args()
    print(json.dumps(benchmark(a.model, a.tag, a.precision), indent=2))

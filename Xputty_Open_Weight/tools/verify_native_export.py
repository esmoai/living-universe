"""Run with the existing local llama-cpp-python environment; no installations."""

import argparse, json
from pathlib import Path
import numpy as np
from llama_cpp import Llama

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--run", required=True, type=Path)
args = parser.parse_args()
request = json.loads((args.run / "native-request.json").read_text(encoding="utf-8"))
model = Llama(
    model_path=request["gguf"],
    n_ctx=request.get("context", 512),
    n_threads=2,
    n_threads_batch=2,
    n_gpu_layers=0,
    logits_all=True,
    verbose=False,
)
probes = []
for probe in request["probes"]:
    ids = model.tokenize(probe["text"].encode("utf-8"), add_bos=False, special=True)
    probes.append(
        {
            "text": probe["text"],
            "matches": ids == probe["ids"],
            "native_ids": ids,
            "reference_ids": probe["ids"],
        }
    )
model.reset()
model.eval(request["eval_ids"])
actual = np.array(model._scores[len(request["eval_ids"]) - 1], dtype=np.float32)
reference = np.array(request["reference_logits"], dtype=np.float32)
difference = float(np.max(np.abs(actual - reference)))
generated = model.create_completion(
    prompt=request["eval_ids"], max_tokens=24, temperature=0, seed=739
)
report = {
    "model_loaded": True,
    "tokenizer_probes": probes,
    "all_tokenizer_probes_match": all(p["matches"] for p in probes),
    "max_logit_difference": difference,
    "logits_match_f16": difference < 0.02,
    "top_token_matches": int(actual.argmax()) == int(reference.argmax()),
    "generation": generated["choices"][0]["text"],
}
(args.run / "native-verification.json").write_text(
    json.dumps(report, indent=2), encoding="utf-8"
)
print(json.dumps({key: report[key] for key in report if key != "tokenizer_probes"}))

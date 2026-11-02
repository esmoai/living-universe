"""Local-only tokenizer/logit/generation verification for an exported baseline."""

import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import torch
import sentencepiece as spm
from transformers import AutoTokenizer, LlamaForCausalLM
from vox.model import TinyLlama, ModelConfig

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--run", required=True, type=Path)
args = parser.parse_args()
root = args.run
export = root / "export"
torch.set_num_threads(2)
checkpoint = torch.load(
    root / "dense/checkpoint.pt", map_location="cpu", weights_only=True
)
reference = TinyLlama(ModelConfig(**checkpoint["config"])).eval()
reference.load_state_dict(checkpoint["weights"])
sp = spm.SentencePieceProcessor(model_file=str(root / "data/vox.model"))
probes = [
    "Hello, how are you?",
    "Two  spaces\nA new line. Café — surprise!",
    "<|segment|><|at_ms|>0<|delta_ms|>0<|text|>That story caught me off guard.\n<|segment|>",
]
if checkpoint.get("representation") == "plain-text-works-v1":
    probes = [
        "Dear friend, I write to you this evening",
        "Two  spaces\nA new line. Café — surprise!",
        "The traveller entered the room and said,",
    ]
model = LlamaForCausalLM.from_pretrained(export, local_files_only=True).eval()
report = {
    "model_loaded": True,
    "tokenizers": {},
    "representation": checkpoint["representation"],
}
for fast in (False, True):
    tokenizer = AutoTokenizer.from_pretrained(
        export, use_fast=fast, local_files_only=True
    )
    report["tokenizers"]["fast" if fast else "slow"] = [
        {
            "prompt": prompt,
            "matches": tokenizer.encode(prompt, add_special_tokens=False)
            == sp.encode(prompt, out_type=int),
            "reference_ids": sp.encode(prompt, out_type=int),
            "hf_ids": tokenizer.encode(prompt, add_special_tokens=False),
        }
        for prompt in probes
    ]
ids = sp.encode(probes[-1], out_type=int)
tensor = torch.tensor([ids])
with torch.inference_mode():
    expected, _ = reference(tensor)
    actual = model(tensor).logits
    difference = float((expected - actual).abs().max())
    generated = model.generate(
        tensor,
        attention_mask=torch.ones_like(tensor),
        max_new_tokens=24,
        do_sample=False,
        pad_token_id=3,
    )
report["max_logit_difference"] = difference
report["logits_match"] = difference < 1e-4
context_checks = {}
if checkpoint.get("training_policy"):
    base_ids = sp.encode(
        "A conversation connects earlier ideas with the current question. ",
        out_type=int,
    )
    with torch.inference_mode():
        for length in checkpoint["training_policy"]["windows"]:
            context_ids = (base_ids * (length // len(base_ids) + 1))[:length]
            batch = torch.tensor([context_ids])
            reference_last = reference(batch)[0][0, -1].float()
            exported_last = model(batch).logits[0, -1].float()
            maximum = float((reference_last - exported_last).abs().max())
            context_checks[str(length)] = {
                "max_logit_difference": maximum,
                "passed": maximum < 1e-4,
            }
    report["context_checks"] = context_checks
    report["logits_match"] = report["logits_match"] and all(
        row["passed"] for row in context_checks.values()
    )
report["generation"] = sp.decode(generated[0, len(ids) :].tolist())
report["all_tokenizer_probes_match"] = all(
    p["matches"] for probes in report["tokenizers"].values() for p in probes
)
(root / "hf-verification.json").write_text(
    json.dumps(report, indent=2), encoding="utf-8"
)
(root / "native-request.json").write_text(
    json.dumps(
        {
            "gguf": str((export / "vox-fibra-f16.gguf").resolve()),
            "context": checkpoint["config"]["context"],
            "probes": [{"text": p, "ids": sp.encode(p, out_type=int)} for p in probes],
            "eval_ids": ids,
            "reference_logits": expected[0, -1].tolist(),
        }
    ),
    encoding="utf-8",
)
print(
    json.dumps(
        {
            key: report[key]
            for key in [
                "model_loaded",
                "all_tokenizer_probes_match",
                "max_logit_difference",
                "logits_match",
                "generation",
            ]
        }
    )
)

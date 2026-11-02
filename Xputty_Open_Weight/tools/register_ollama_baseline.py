"""Register and test this research checkpoint on local Ollama only."""

import argparse, hashlib, json, urllib.request
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--run", required=True, type=Path)
parser.add_argument("--name", default="vox-dialogue-timing:baseline-002")
args = parser.parse_args()
root = args.run
model = root / "export/vox-fibra-f16.gguf"
context = json.loads((root / "export/config.json").read_text())[
    "max_position_embeddings"
]
blob = model.read_bytes()
digest = "sha256:" + hashlib.sha256(blob).hexdigest()
base = "http://127.0.0.1:11434"


def post(endpoint, value=None, raw=None):
    body = raw if raw is not None else json.dumps(value).encode()
    request = urllib.request.Request(
        base + endpoint,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/octet-stream"
            if raw is not None
            else "application/json"
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
        return json.loads(data) if data else {}


post("/api/blobs/" + digest, raw=blob)
created = post(
    "/api/create",
    {
        "model": args.name,
        "files": {model.name: digest},
        "template": "{{ .Prompt }}",
        "parameters": {"num_ctx": context, "temperature": 0.8, "stop": ["<|eod|>"]},
        "stream": False,
    },
)
if created.get("status") != "success":
    raise RuntimeError(created)
request = json.loads((root / "native-request.json").read_text(encoding="utf-8"))
generated = post(
    "/api/generate",
    {
        "model": args.name,
        "prompt": request["probes"][-1]["text"],
        "raw": True,
        "stream": False,
        "keep_alive": 0,
        "options": {
            "num_predict": 24,
            "temperature": 0,
            "num_ctx": context,
            "num_thread": 2,
            "repeat_penalty": 1.0,
        },
    },
)
report = {
    "local_model_name": args.name,
    "created": created,
    "done": generated.get("done"),
    "generation": generated.get("response"),
    "eval_count": generated.get("eval_count"),
    "prompt_eval_count": generated.get("prompt_eval_count"),
    "total_duration_ns": generated.get("total_duration"),
    "gguf_sha256": digest,
    "published": False,
    "scope": "Local runtime verification, not conversation-quality acceptance",
}
(root / "ollama-verification.json").write_text(
    json.dumps(report, indent=2), encoding="utf-8"
)
print(json.dumps(report))

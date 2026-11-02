import json, sys
from pathlib import Path
from vox.limits import limit_cpu
from vox.model import TinyLlama, ModelConfig, generate
from vox.dialogue_format import raw_prompt, parse_raw_generation
import sentencepiece as spm

torch = limit_cpu(2)
root = Path(sys.argv[1])
checkpoint = torch.load(
    root / "dense/checkpoint.pt", map_location="cpu", weights_only=True
)
model = TinyLlama(ModelConfig(**checkpoint["config"]))
model.load_state_dict(checkpoint["weights"])
sp = spm.SentencePieceProcessor(model_file=str(root / "data/vox.model"))
text_input = sys.stdin.read()
plain_mode = checkpoint.get("representation") == "plain-text-works-v1"
prompt = sp.encode(text_input if plain_mode else raw_prompt(text_input), out_type=int)
ids = generate(
    model, prompt, max_new_tokens=96, temperature=0.8, stop_id=sp.piece_to_id("<|eod|>")
)
text = sp.decode(ids)
print(
    json.dumps(
        {
            "raw": text,
            "speech_text": text,
            "representation": checkpoint.get("representation"),
        }
        if plain_mode
        else {"raw": text, **parse_raw_generation(text)}
    )
)

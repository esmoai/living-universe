"""Try the installed local research model; display speech and timing separately."""

import json
import urllib.request
from pathlib import Path
from .dialogue_format import raw_prompt, parse_raw_generation


def main():
    pointer = Path(__file__).resolve().parents[1] / "work/current-baseline.json"
    model = (
        json.loads(pointer.read_text()).get("ollama_model_name")
        if pointer.is_file()
        else "vox-dialogue-timing:baseline-002"
    )
    if not model:
        raise ValueError(
            "current checkpoint is not registered in Ollama; run local runtime verification first"
        )
    print(model + " — early research weights, not a fluent chatbot.")
    print("Enter a dialogue fragment. Type /quit to exit.")
    while True:
        try:
            text = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text == "/quit":
            break
        if not text:
            continue
        payload = {
            "model": model,
            "raw": True,
            "stream": False,
            "prompt": raw_prompt(text),
            "keep_alive": 0,
            "options": {
                "num_predict": 96,
                "num_ctx": 512,
                "temperature": 0.8,
                "num_thread": 2,
            },
        }
        try:
            request = urllib.request.Request(
                "http://127.0.0.1:11434/api/generate",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.load(response)
            parsed = parse_raw_generation(result.get("response", ""))
            print("Generated:", result.get("response", ""))
            print("Parsed dialogue/timing:", json.dumps(parsed, ensure_ascii=False))
        except Exception as error:
            print("Local runtime error:", error)


if __name__ == "__main__":
    main()

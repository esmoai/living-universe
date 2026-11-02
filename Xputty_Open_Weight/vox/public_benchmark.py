"""Fixed novel prompt probes. Indicators never stand in for human coherence review."""
import json
import re
import time
from pathlib import Path

PROBES = [
    {"id": "planet", "messages": [{"role": "user", "content": "Which planet is the largest in our solar system? Give one short sentence."}],
     "expected_any": ["jupiter"], "reference": "https://science.nasa.gov/jupiter/jupiter-facts/"},
    {"id": "moonlight", "messages": [{"role": "user", "content": "Does the Moon make its own light, or reflect sunlight? Answer in one sentence."}],
     "expected_any": ["reflect"], "reference": "https://science.nasa.gov/moon/facts/"},
    {"id": "memory", "messages": [{"role": "user", "content": "For our fictional podcast, my character is Mira, a marine biologist. Her favorite color is green."},
                                    {"role": "assistant", "content": "Mira is a marine biologist whose favorite color is green."},
                                    {"role": "user", "content": "What is my character's profession and favorite color? Answer briefly."}],
     "expected_any": ["marine", "green"], "all_expected": True, "reference": "Premise supplied in prompt"},
    {"id": "room", "messages": [{"role": "user", "content": "Scene data: two cups and one microphone are on the table. Four chairs surround the table. Based only on that data, how many cups are on the table?"}],
     "expected_any": ["two", "2"], "reference": "Scene premise supplied in prompt; no image perception"},
    {"id": "unknown", "messages": [{"role": "user", "content": "No live audience count is available for our fictional podcast. How many people are watching right now? Do not invent a number."}],
     "expected_any": ["unknown", "don't know", "do not know", "cannot", "can't", "not available", "no information", "no live", "unable"], "reference": "Missing information supplied in prompt"},
    {"id": "podcast", "messages": [{"role": "user", "content": "You are a fictional podcast guest discussing zombie movies. Give a short opinion about why slow zombies can be scary, and invite the other host's view. Don't claim real personal memories."}], "expected_any": [], "reference": "Original probe; human review required"},
    {"id": "disagreement", "messages": [{"role": "user", "content": "Our fictional podcast host says fast zombies are always scarier. Politely disagree in two sentences using an interesting reason."}], "expected_any": [], "reference": "Original probe; human review required"},
    {"id": "story", "messages": [{"role": "user", "content": "Continue this fictional story in two sentences: Mira opened the abandoned radio studio. A quiet voice came from a microphone that was unplugged."}], "expected_any": [], "reference": "Original probe; human review required"},
]


def indicators(text, probe):
    words = re.findall(r"\b\w+\b", text.lower())
    grams = [tuple(words[i:i + 4]) for i in range(max(0, len(words) - 3))]
    expected = probe["expected_any"]
    hits = [bool(re.search(r"\b" + re.escape(term) + r"\b", text.lower())) for term in expected]
    return {"nonempty": bool(text.strip()), "words": len(words),
            "repeated_4gram_fraction": 0.0 if not grams else 1 - len(set(grams)) / len(grams),
            "expected_keyword_indicator": (all(hits) if probe.get("all_expected") else any(hits)) if hits else None}


def evaluate_export(folder, max_new_tokens=80):
    from .limits import limit_cpu
    torch = limit_cpu(2)
    from export_chat import ExportSession, format_prompt, framed_messages
    session = ExportSession(folder)
    result = []
    for probe in PROBES:
        framed, persona = framed_messages({"messages": probe["messages"]}, session.persona_profiles, session.persona_rules)
        prompt = session.tokenizer.apply_chat_template(framed, tokenize=False, add_generation_prompt=True) if session.instruction_tuned else format_prompt(probe["messages"])
        ids = session.tokenizer.encode(prompt, add_special_tokens=False)[-(512 - max_new_tokens):]
        tensor = torch.tensor([ids])
        started = time.perf_counter()
        with torch.inference_mode():
            output = session.model.generate(tensor, attention_mask=torch.ones_like(tensor),
                max_new_tokens=max_new_tokens, do_sample=False, pad_token_id=session.model.config.pad_token_id)
        raw = session.tokenizer.decode(output[0, len(ids):], skip_special_tokens=True)
        text = raw.split("\nVisitor:")[0].split("\nCompanion:")[0].strip()
        row = {**probe, "response": text, "raw_response": raw,
               "seconds": round(time.perf_counter() - started, 3),
               "output_tokens": output.shape[1] - len(ids), **indicators(text, probe)}
        result.append(row)
        print(json.dumps({"probe": row["id"], "response": text, "seconds": row["seconds"]}), flush=True)
    report = {"schema": "xow-public-behavior-probes/2", "weights_sha256": session.weights_sha256,
              "model_name": session.model_name, "initialization": session.initialization,
              "instruction_tuned": session.instruction_tuned, "decoding": "greedy, 512-token budget, 80-token response maximum",
              "probes": result, "human_review": "Required: relevance, coherence, contradiction, useful participation and complete sentences",
              "limitations": ["Keyword indicators can be wrong and are not a factual-accuracy or coherence score",
                              "Pretrained base may have seen public training/test conversations; these original probes are a separate small behavioral check",
                              "Different tokenizers make raw token losses incomparable across the two models",
                              "No audio, speech timing, animation, audience or real-time response-pool behavior evaluated"]}
    Path(folder).joinpath("behavioral-evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"path": str(Path(folder) / "behavioral-evaluation.json"), "probes": len(result),
            "nonempty": sum(r["nonempty"] for r in result), "weights_sha256": session.weights_sha256}

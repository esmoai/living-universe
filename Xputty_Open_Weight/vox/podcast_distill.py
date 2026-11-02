"""Character-conditioned sequence distillation from a named, local open teacher.

The curriculum is original. Factual cards cite public primary references; imagined
scenes are explicitly fictional. All raw teacher responses and transformations are
preserved. No scraped podcast text or invented speech timestamps are used.
"""
import hashlib
import json
import re
import time
import urllib.request
from pathlib import Path

from .public_baseline import write_json

PERSONAS = {
    "lyra": {"name": "Lyra", "traits": "curious, warm, asks sharp follow-up questions", "assertiveness": 0.55},
    "orion": {"name": "Orion", "traits": "skeptical, precise, challenges assumptions with reasons", "assertiveness": 0.8},
    "nova": {"name": "Nova", "traits": "playful, imaginative, finds surprising comparisons", "assertiveness": 0.7},
    "kai": {"name": "Kai", "traits": "grounded, empathetic, connects ideas to practical choices", "assertiveness": 0.35},
}
RULES = ("Portray an original fictional podcast host. Reply directly to the last speaker, in character. "
         "Add a specific idea, not a generic greeting. No assistant disclaimers, invented personal memories, "
         "or unsupported live facts. Give only one or two complete conversational sentences.")

TOPICS = [
    ("slow-zombies", "train", "Slow zombies in horror fiction are relentless but slow-moving.", "Fast zombies are obviously scarier; you can just walk away from slow ones.", "Original fictional genre discussion"),
    ("group-trust", "train", "In a fictional zombie outbreak, a group must decide whether to share limited supplies.", "Locking the doors and trusting nobody seems like the safest plan.", "Original fictional dilemma"),
    ("jupiter", "train", "Jupiter is the largest planet in our solar system and has a long-lived storm called the Great Red Spot.", "Jupiter makes our everyday weather seem almost boring.", "https://science.nasa.gov/jupiter/jupiter-facts/"),
    ("moonlight", "train", "The Moon reflects sunlight; it does not generate its own visible light.", "Knowing moonlight is reflected sunlight makes a night scene feel different.", "https://science.nasa.gov/moon/facts/"),
    ("vr-set", "train", "This fictional VR studio has four seats, a red lamp, a table and two cups. No audience count is available.", "If viewers can walk around, the room should reward their curiosity.", "Original fictional scene description; no image perception claimed"),
    ("game-team", "train", "An imaginary team is designing a cooperative game where players have different abilities.", "Giving everyone the same tools would make balancing the game easier.", "Original design discussion"),
    ("music-silence", "train", "The hosts are discussing dramatic silence in a fictional soundtrack.", "A soundtrack should keep playing so the energy never drops.", "Original opinion prompt"),
    ("radio-ghost", "train", "In a fictional story, a voice comes from a microphone that is unplugged.", "I'd check the equipment before deciding that the studio is haunted.", "Original fiction prompt"),
    ("film-sound", "val", "The hosts are comparing what a horror scene gains from silence versus a loud musical cue.", "A loud jump scare is always more effective than a quiet scene.", "Original held-out discussion topic"),
    ("mars-rover", "val", "Mars is a rocky planet. Robotic rovers explore its surface and send observations back to Earth.", "A rover feels like a pair of borrowed eyes on another world.", "https://science.nasa.gov/mars/"),
    ("future-library", "test", "In an original fictional library, books change their endings when different readers open them.", "That would make comparing notes about a book wonderfully confusing.", "Original held-out fiction topic"),
    ("island-choice", "test", "In an original story, a group on an island must choose between repairing a radio and exploring a cave before dark.", "Exploring the cave sounds exciting, but fixing the radio feels more responsible.", "Original held-out decision topic"),
]


def select_reply(text, limit=70):
    text = re.sub(r"^\s*(?:[A-Za-z]+:\s*)", "", text.strip()).strip('"')
    if re.search(r"\b(as an ai|language model|i cannot roleplay|i can't roleplay)\b", text, re.I):
        return None
    sentences = re.findall(r"[^.!?]+[.!?](?:[\"']?)(?:\s|$)", text)
    chosen = []
    for sentence in sentences[:2]:
        if len((" ".join(chosen) + sentence).split()) > limit:
            break
        chosen.append(sentence.strip())
    reply = " ".join(chosen).strip()
    words = reply.split()
    if not 12 <= len(words) <= limit:
        return None
    if len(set(w.lower() for w in words)) < len(words) * 0.45:
        return None
    return reply


def collect_distillation(output, teacher="xputty-podcast-teacher:1.5b-q4", teacher_source=None):
    output = Path(output)
    if output.exists():
        raise FileExistsError("Use a fresh distillation snapshot")
    output.mkdir(parents=True)
    (output / "uploads").mkdir()
    (output / "data").mkdir()
    with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=15) as response:
        tags = json.load(response)["models"]
    source = next((m for m in tags if m["name"] == teacher), None)
    if source is None or source["details"].get("format") != "gguf":
        raise ValueError("Choose an installed local GGUF teacher, never a cloud alias")
    records = []
    partitions = {s: [] for s in ("train", "val", "test")}
    raw_file = output / "teacher-responses.jsonl"
    for topic, split, facts, previous, reference in TOPICS:
        # Training has two phrasing/length conditions; complete topics stay held out.
        for variant in range(2 if split == "train" else 1):
            for persona_id, profile in PERSONAS.items():
                system = RULES + f" Your name is {profile['name']}; you are {profile['traits']}."
                prompt = f"Topic: {topic}.\nContext: {facts}\nLast speaker: {previous}\n"
                prompt += "Make one compact contribution." if variant == 0 else "Offer a distinct angle and a brief follow-up question."
                accepted = None
                for attempt in range(3):
                    seed = 739 + len(records) * 7 + attempt
                    payload = {"model": teacher, "stream": False,
                               "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                               "options": {"num_ctx": 2048, "num_predict": 144, "temperature": 0.65,
                                           "seed": seed, "num_thread": 2}, "keep_alive": "10m"}
                    started = time.perf_counter()
                    request = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(request, timeout=180) as response:
                        generated = json.load(response)
                    raw = {"topic": topic, "split": split, "persona": persona_id, "variant": variant,
                           "request": payload, "response": generated, "elapsed_seconds": time.perf_counter() - started}
                    with raw_file.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(raw, ensure_ascii=False) + "\n")
                    accepted = select_reply(generated["message"]["content"])
                    if accepted:
                        break
                if not accepted:
                    raise ValueError(f"No acceptable complete teacher reply for {topic}/{persona_id}")
                messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}, {"role": "assistant", "content": accepted}]
                identity = hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest()
                row = {"id": identity, "messages": messages, "topic": topic, "persona": persona_id,
                       "variant": variant, "source_reference": reference, "teacher_digest": source["digest"],
                       "transform": "First one or two complete sentences, <=70 words; raw response preserved",
                       "upstream_split": split, "synthetic": True}
                records.append(row)
                text = f"System: {system}\nVisitor: {prompt}\nCompanion: {accepted}"
                (output / "uploads" / (identity + ".txt")).write_text(text, encoding="utf-8")
                partitions[split].append({"episode_id": identity, "series_id": topic, "text": text})
                write_json(output / "progress.json", {"accepted": len(records), "topic": topic, "split": split})
                print(f"Accepted {len(records)} {split}: {topic}/{persona_id}", flush=True)
    (output / "conversations.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8")
    for split, rows in partitions.items():
        (output / "data" / (split + ".jsonl")).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    manifest = {"kind": "public-conversations", "method": "Sequence-level knowledge distillation",
                "teacher": teacher, "teacher_digest": source["digest"], "teacher_source": teacher_source,
                "characters": PERSONAS, "sources": [{"topic": t[0], "reference": t[4]} for t in TOPICS],
                "authorship": "Original fictional curriculum and open local teacher generations; public science facts cited",
                "timing": "No audio or speech timestamps. Generation duration is a runtime diagnostic, not a speech cue",
                "split_group": "entire topic", "counts": {s: len(v) for s, v in partitions.items()},
                "corpus_sha256": hashlib.sha256((output / "conversations.jsonl").read_bytes()).hexdigest()}
    write_json(output / "public-sources.json", manifest)
    write_json(output / "data/corpus_report.json", manifest)
    (output / "UPSTREAM-DATASET-CARD.md").write_text("# Original Xputty podcast distillation pilot\n\n" + json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest

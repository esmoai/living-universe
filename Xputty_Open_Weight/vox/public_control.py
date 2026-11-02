"""Explicit pretrained comparison: optional, independent of the 48M scratch model.

Adapt only the final four decoder blocks. Retain a fixed validation set and export
the best validation checkpoint, including step zero if adaptation makes it worse.
No remote inference, fabricated timings, or silent substitution of this control.
"""

import json
import hashlib
import random
import shutil
import time
from pathlib import Path

from .public_baseline import (
    REFERENCES, conversation_splits, fetch_control, sha256, write_json,
)


def assistant_example(tokenizer, messages, context=256):
    """One first-response target; user/template tokens never contribute to loss."""
    import torch

    offset = 1 if messages[0]["role"] == "system" else 0
    if messages[offset]["role"] != "user" or messages[offset + 1]["role"] != "assistant":
        raise ValueError("Expected a known user/assistant pair")
    prefix = tokenizer.apply_chat_template(messages[:offset + 1], tokenize=True, add_generation_prompt=True)
    full = tokenizer.apply_chat_template(messages[:offset + 2], tokenize=True, add_generation_prompt=False)
    if full[:len(prefix)] != prefix:
        raise ValueError("Chat template is not prefix-stable")
    if len(prefix) > context - 16:
        return None
    ids = full[:context]
    labels = [-100] * len(prefix) + ids[len(prefix):]
    return torch.tensor([ids]), torch.tensor([labels])


def loss_on(model, examples):
    import torch

    model.eval()
    total = tokens = 0
    with torch.inference_mode():
        for inputs, labels in examples:
            n = int((labels[:, 1:] != -100).sum())
            total += float(model(input_ids=inputs, labels=labels, use_cache=False).loss) * n
            tokens += n
    if not tokens:
        raise ValueError("No assistant targets in evaluation")
    return {"assistant_token_loss": total / tokens, "target_tokens": tokens,
            "conversations": len(examples)}


def check_example_separation(training, validation, testing):
    def identities(examples):
        return {hashlib.sha256(x.numpy().tobytes() + y.numpy().tobytes()).hexdigest() for x, y in examples}
    groups = [identities(e) for e in (training, validation, testing)]
    if any(a & b for i, a in enumerate(groups) for b in groups[i + 1:]):
        raise ValueError("Identical control response targets cross adaptation partitions")
    return {"train_unique": len(groups[0]), "val_unique": len(groups[1]), "test_unique": len(groups[2]), "overlap": 0}


def adapt_control(project, cache, output, steps=60, context=256, reference="smollm135", blocks=4, eval_samples=24, retain_candidate=False):
    from .limits import limit_cpu, memory_guard
    torch = limit_cpu(2)
    from transformers import AutoTokenizer, AutoModelForCausalLM

    project, output = Path(project), Path(output)
    if output.exists():
        raise FileExistsError("Use a new control run directory")
    output.mkdir(parents=True)
    if not 1 <= blocks <= 4 or context not in (128, 256, 384, 512) or not 8 <= eval_samples <= 64 or not 1 <= steps <= 10000:
        raise ValueError("Use 1–4 adapted blocks, 128/256/384/512 context, 8–64 eval samples and 1–10,000 updates")
    info = REFERENCES[reference]
    base = fetch_control(cache, reference)
    tokenizer = AutoTokenizer.from_pretrained(base, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(base, local_files_only=True, torch_dtype=torch.float32, trust_remote_code=False, use_safetensors=True)
    model.config.use_cache = False
    torch.manual_seed(739)
    splits = conversation_splits(project)

    def examples(rows, limit):
        result = []
        for row in rows:
            item = assistant_example(tokenizer, row["messages"], context)
            if item is not None:
                result.append(item)
            if len(result) == limit:
                break
        return result

    training = examples(splits["train"], 1000)
    validation = examples(splits["val"], eval_samples)
    testing = examples(splits["test"], eval_samples)
    separation = check_example_separation(training, validation, testing)
    if min(len(training), len(validation), len(testing)) < 8:
        raise ValueError("Not enough usable independent conversations")
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    for layer in model.model.layers[-blocks:]:
        layer.requires_grad_(True)
    model.model.norm.requires_grad_(True)
    trainable = {k: p for k, p in model.named_parameters() if p.requires_grad}
    optimizer = torch.optim.AdamW(trainable.values(), lr=0.00002, weight_decay=0.01)
    base_hash = sha256(base / "model.safetensors")
    dataset_hash = sha256(project / "data/corpus_report.json")
    before = loss_on(model, validation)
    write_json(output / "before-validation.json", before)
    best_loss, best_step = before["assistant_token_loss"], 0
    best_weights = {k: p.detach().clone() for k, p in trainable.items()}
    history = [{"step": 0, "validation": before}]
    started = time.perf_counter()
    processed = targets = 0
    for step in range(steps):
        if (output / "stop-request").exists():
            break
        model.train()
        x, y = training[random.Random(739 * 1000003 + step).randrange(len(training))]
        optimizer.zero_grad(set_to_none=True)
        loss = model(input_ids=x, labels=y, use_cache=False).loss
        loss.backward()
        torch.nn.utils.clip_grad_norm_(trainable.values(), 1.0)
        optimizer.step()
        processed += int(x.numel())
        targets += int((y[:, 1:] != -100).sum())
        if (step + 1) % 10 == 0 or step == 0 or step + 1 == steps:
            metrics = loss_on(model, validation)
            if metrics["assistant_token_loss"] < best_loss:
                best_loss, best_step = metrics["assistant_token_loss"], step + 1
                best_weights = {k: p.detach().clone() for k, p in trainable.items()}
            row = {"step": step + 1, "train_loss": float(loss.detach()), "validation": metrics,
                   "elapsed_seconds": round(time.perf_counter() - started, 3), "rss_bytes": memory_guard(4)}
            history.append(row)
            write_json(output / "progress.json", row)
            print(json.dumps(row), flush=True)
            torch.save({"step": step + 1, "weights": {k: p.detach().clone() for k, p in trainable.items()},
                        "optimizer": optimizer.state_dict(), "dataset_sha256": dataset_hash,
                        "base_sha256": base_hash}, output / "adaptation-checkpoint.pt")
    with torch.no_grad():
        for key, parameter in trainable.items():
            parameter.copy_(best_weights[key])
    torch.save({"weights": best_weights, "selected_update": best_step,
                "base_sha256": base_hash, "dataset_sha256": dataset_hash}, output / "selected-adapter.pt")
    model.eval()
    final_validation = loss_on(model, validation)
    final_test = loss_on(model, testing)  # Used only after validation selection.
    exported = output / "export"
    model.config.use_cache = True
    model.save_pretrained(exported, safe_serialization=True)
    tokenizer.save_pretrained(exported)
    for name in ("vocab.json", "merges.txt"):
        if (base / name).exists():
            shutil.copy2(base / name, exported / name)
    report = {
        "name": "Xputty Public Conversation Control · " + info["folder"], "initialization": "pretrained, not the 48M scratch model",
        "reference": reference, "base_model": info["model"], "base_revision": info["revision"], "base_weights_sha256": base_hash,
        "weights_sha256": sha256(exported / "model.safetensors"), "license": "Apache-2.0",
        "parameter_count": sum(p.numel() for p in model.parameters()),
        "trainable_parameters": sum(p.numel() for p in trainable.values()), "adapted_blocks": blocks,
        "representation": "hf-instruction-control-v1", "instruction_tuned": True,
        "requested_updates": steps, "completed_updates": history[-1]["step"], "selected_update": best_step,
        "selection_rule": "Lowest fixed validation assistant-token loss, including the original model at update zero",
        "dataset_sha256": dataset_hash, "source_manifest": "public-sources.json",
        "training_conversations": len(training), "input_tokens_processed": processed, "assistant_targets_processed": targets,
        "context_tokens": context, "before_validation": before, "after_validation": final_validation,
        "example_separation": separation,
        "final_test": final_test, "history": history, "timing": "No speech audio or timing learned",
        "heldout_scope": "Held out of this adaptation. Pretraining contamination is not ruled out; SmolLM2 was already tuned on this upstream dataset.",
        "verified_hf_transformers": True, "verified_ollama": False,
    }
    corpus = json.loads((project / "public-sources.json").read_text(encoding="utf-8"))
    if corpus.get("characters"):
        from .podcast_distill import RULES
        report.update(name="Xputty Podcast Pilot · " + info["folder"], persona_profiles=corpus["characters"],
                      persona_rules=RULES, method=corpus.get("method"),
                      heldout_scope="Entire original curriculum topics are held out of this distillation adaptation. Base pretraining may cover related topics.")
    write_json(output / "training_report.json", report)
    write_json(exported / "export_report.json", report)
    for name in ("public-sources.json", "UPSTREAM-DATASET-CARD.md"):
        shutil.copy2(project / name, exported / name)
    shutil.copy2(base / "README.md", exported / "UPSTREAM-MODEL-CARD.md")
    shutil.copy2(base / "LICENSE", exported / "LICENSE")
    shutil.copy2(Path(__file__).resolve().parents[1] / "export_chat.py", exported / "chat.py")
    (exported / "Modelfile").write_text('FROM .\nPARAMETER num_ctx 2048\nPARAMETER temperature 0.6\n', encoding="utf-8")
    (exported / "README.md").write_text(
        f"# {report['name']}\n\nA distinct {report['parameter_count']:,}-parameter pretrained comparison model.\n"
        f"Base: {info['model']}@{info['revision']}. Final {blocks} blocks adapted on the public conversation training split.\n"
        f"Selected update: {best_step}/{steps}; selection used validation only.\n"
        "This is NOT a scratch-trained 48M model and is never substituted for it.\n"
        "Upstream model/data are declared Apache-2.0; original cards and provenance are included.\n"
        "Pretraining may already have seen these public conversations. This evaluation measures adaptation retention, not novel generalization.\n"
        "Run `python chat.py` for local browser chat using only these exported weights.\n"
        "No voice, audio timing, animation or real-time podcast participation is trained here.\n",
        encoding="utf-8",
    )
    if retain_candidate:
        export_candidate(output, cache)
    return report


def export_candidate(output, cache):
    """Retain the actual last adapted weights even when validation selects update 0."""
    from .limits import limit_cpu
    torch = limit_cpu(2)
    from transformers import AutoModelForCausalLM

    output = Path(output)
    report = json.loads((output / "training_report.json").read_text(encoding="utf-8"))
    state = torch.load(output / "adaptation-checkpoint.pt", map_location="cpu", weights_only=True)
    base = fetch_control(cache, report.get("reference", "smollm135"))
    if state["base_sha256"] != sha256(base / "model.safetensors") or state["dataset_sha256"] != report["dataset_sha256"]:
        raise ValueError("Candidate source weights/corpus do not match the comparison run")
    model = AutoModelForCausalLM.from_pretrained(base, local_files_only=True, torch_dtype=torch.float32, trust_remote_code=False, use_safetensors=True)
    parameters = dict(model.named_parameters())
    with torch.no_grad():
        for name, value in state["weights"].items():
            if name not in parameters or parameters[name].shape != value.shape:
                raise ValueError("Candidate parameter mismatch: " + name)
            parameters[name].copy_(value)
    candidate = output / "candidate"
    model.save_pretrained(candidate, safe_serialization=True)
    for source in (output / "export").iterdir():
        if source.is_file() and source.name not in ("model.safetensors", "config.json", "export_report.json", "README.md"):
            shutil.copy2(source, candidate / source.name)
    report.update(name=f"Xputty Public Conversation · {report['parameter_count'] / 1e6:.1f}M adapted candidate",
                  reference_selected_update=report["selected_update"],
                  after_validation=report["history"][-1]["validation"], final_test=None,
                  selection_rule="Final adaptation checkpoint, retained separately from validation selection",
                  selected_update=state["step"], selection_status="Unselected final adaptation candidate; compare with the validation-selected reference",
                  weights_sha256=sha256(candidate / "model.safetensors"))
    write_json(candidate / "export_report.json", report)
    (candidate / "README.md").write_text(
        f"# {report['name']}\n\nPretrained {report['base_model']}@{report['base_revision']}, with {state['step']} actual public-data adaptation updates.\n"
        "This candidate did not beat the validation-selected reference; preserve that distinction when comparing it.\n"
        "It is not the scratch-trained 48M model. Upstream weights/data are declared Apache-2.0; cards, license and provenance accompany this export.\n"
        "Run `python chat.py` for local chat using these actual adapted weights. No remote fallback.\n",
        encoding="utf-8",
    )
    return candidate

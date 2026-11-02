"""Local, resumable CPU adapter experiment over an immutable Qwen2 GGUF base."""
import argparse
import json
import random
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vox.public_baseline import conversation_splits, sha256, write_json
from vox.public_control import assistant_example, check_example_separation


def train(dataset, base, config, output, steps=80, context=256, layers=4, resume=False):
    from vox.limits import limit_cpu, memory_guard
    torch = limit_cpu(2)
    from transformers import AutoTokenizer
    from vox.gguf_lora import load_quantized_qwen, adapter_weights, merged_gguf, PackedLinear, unpack, cache_active_layers, cache_output_head
    from vox.podcast_distill import PERSONAS, RULES
    if context not in (256, 384, 512) or not 1 <= steps <= 10000:
        raise ValueError("Choose 256/384/512 context and 1–10,000 updates")
    output, dataset, base, config = map(Path, (output, dataset, base, config))
    if output.exists() and not resume:
        raise FileExistsError("Use a fresh run or explicitly resume")
    output.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(739)
    tokenizer = AutoTokenizer.from_pretrained(config, local_files_only=True)
    splits = conversation_splits(dataset)
    examples = {k: [assistant_example(tokenizer, r['messages'], context) for r in rows] for k, rows in splits.items()}
    if any(e is None for rows in examples.values() for e in rows):
        raise ValueError("A prompt exceeds the selected context; do not silently omit it")
    separation = check_example_separation(*[examples[k] for k in ('train', 'val', 'test')])
    base_hash, data_hash = sha256(base), sha256(dataset / 'conversations.jsonl')
    identity = dict(base_sha256=base_hash, dataset_sha256=data_hash, context=context, layers=layers, rank=8, alpha=16)
    model = load_quantized_qwen(base, config, adapted_layers=layers).eval()
    all_layers, original_norm = model.model.layers, model.model.norm
    # Compute the immutable prefix without its final norm. Cache contextual states,
    # never gradients or test-derived labels, and keep all partition identities.
    cache_file = output / 'prefix-cache.pt'
    if cache_file.exists():
        cached = torch.load(cache_file, map_location='cpu', weights_only=True)
        if cached['identity'] != identity:
            raise ValueError("Cached activations belong to another base, corpus or configuration")
        encoded = cached['encoded']
    else:
        encoded = {}
        with torch.no_grad():
            for split, rows in examples.items():
                encoded[split] = [(model.model.embed_tokens(x), y) for x, y in rows]
            for index, layer in enumerate(all_layers[:-layers]):
                # Expand each frozen layer once, across every independent sample.
                # Only one decoder layer is dense at any time; no vocabulary head.
                dense = [m for m in layer.modules() if isinstance(m, PackedLinear)]
                for module in dense: module._prefix_weight = unpack(module.tensor)
                for split, rows in encoded.items():
                    for i, (h, y) in enumerate(rows):
                        positions = torch.arange(h.shape[1]).unsqueeze(0)
                        rotary = model.model.rotary_emb(h, positions)
                        h = layer(h, position_ids=positions, position_embeddings=rotary, use_cache=False)
                        encoded[split][i] = (h, y)
                for module in dense: del module._prefix_weight
                print(json.dumps({'phase': 'cache frozen layer', 'done': index + 1, 'total': len(all_layers) - layers,
                                  'rss_bytes': memory_guard(4)}), flush=True)
        torch.save({'identity': identity, 'encoded': encoded}, cache_file)
    model.model.layers = torch.nn.ModuleList(all_layers[-layers:])
    model.model.norm = original_norm
    active_cache = cache_active_layers(model)
    head_cache = cache_output_head(model)
    print(json.dumps({'phase': 'active layer cache', **active_cache, 'head': head_cache, 'rss_bytes': memory_guard(4)}), flush=True)
    params = adapter_weights(model)
    optimizer = torch.optim.AdamW(params.values(), lr=0.0002, weight_decay=0.01)

    def loss_for(pair):
        h, labels = pair
        # Cached inference tensors must become ordinary tensors for autograd.
        hidden = model.model(inputs_embeds=h.clone(), use_cache=False).last_hidden_state
        mask = labels[:, 1:] != -100
        logits = model.lm_head(hidden[:, :-1][mask])
        return torch.nn.functional.cross_entropy(logits, labels[:, 1:][mask]), int(mask.sum())

    def evaluate(rows):
        model.eval()
        total = tokens = 0
        with torch.no_grad():
            for pair in rows:
                loss, n = loss_for(pair)
                total += float(loss) * n
                tokens += n
        return {'assistant_token_loss': total / tokens, 'target_tokens': tokens, 'conversations': len(rows)}

    start = 0
    checkpoint = output / 'adapter-checkpoint.pt'
    if resume and checkpoint.exists():
        state = torch.load(checkpoint, map_location='cpu', weights_only=True)
        if state['identity'] != identity:
            raise ValueError("Resume identity differs from the saved run")
        with torch.no_grad():
            for name, p in params.items(): p.copy_(state['weights'][name])
        optimizer.load_state_dict(state['optimizer'])
        start, best_step, best_loss, best, history = [state[k] for k in ('step', 'best_step', 'best_loss', 'best', 'history')]
    else:
        if resume:
            print(json.dumps({'phase': 'resume prefix cache', 'note': 'No optimizer checkpoint yet; starting adapter updates at zero'}), flush=True)
        before = evaluate(encoded['val'])
        best_loss, best_step = before['assistant_token_loss'], 0
        best = {k: p.detach().clone() for k, p in params.items()}
        history = [{'step': 0, 'validation': before}]
        write_json(output / 'before-validation.json', before)
    began = time.perf_counter()
    for step in range(start, steps):
        if (output / 'stop-request').exists(): break
        model.train()
        optimizer.zero_grad(set_to_none=True)
        loss, n = loss_for(encoded['train'][random.Random(739 * 1000003 + step).randrange(len(encoded['train']))])
        if not torch.isfinite(loss): raise ValueError("Nonfinite loss; checkpoint preserved")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(params.values(), 1.0)
        optimizer.step()
        if (step + 1) % 10 == 0 or step == 0 or step + 1 == steps:
            validation = evaluate(encoded['val'])
            if validation['assistant_token_loss'] < best_loss:
                best_step, best_loss = step + 1, validation['assistant_token_loss']
                best = {k: p.detach().clone() for k, p in params.items()}
            row = {'step': step + 1, 'train_loss': float(loss.detach()), 'validation': validation,
                   'elapsed_seconds': round(time.perf_counter() - began, 3), 'rss_bytes': memory_guard(4)}
            history.append(row)
            print(json.dumps(row), flush=True)
            write_json(output / 'progress.json', row)
            state = dict(identity=identity, step=step + 1, best_step=best_step, best_loss=best_loss, best=best, history=history,
                         weights={k: p.detach().clone() for k, p in params.items()}, optimizer=optimizer.state_dict())
            temporary = checkpoint.with_suffix('.tmp')
            torch.save(state, temporary)
            temporary.replace(checkpoint)
    with torch.no_grad():
        for name, p in params.items(): p.copy_(best[name])
    final_test = evaluate(encoded['test'])
    model.model.layers = all_layers
    exported = output / 'export'
    exported.mkdir(exist_ok=True)
    full_names = {}
    for key, value in best.items():
        parts = key.split('.')
        parts[2] = str(int(parts[2]) + len(all_layers) - layers)
        full_names['.'.join(parts)] = value
    torch.save({'identity': identity, 'selected_update': best_step, 'key_scheme': 'full-hf-layer-indices',
                'weights': full_names}, exported / 'adapter.pt')
    merged = merged_gguf(model, exported / 'model-mixed.gguf', 'q8_0')
    for name in ('config.json', 'tokenizer.json', 'tokenizer_config.json', 'vocab.json', 'merges.txt', 'README.md', 'LICENSE'):
        if (config / name).exists(): shutil.copy2(config / name, exported / ('UPSTREAM-MODEL-CARD.md' if name == 'README.md' else name))
    shutil.copy2(dataset / 'public-sources.json', exported / 'public-sources.json')
    shutil.copy2(Path(__file__).resolve().parents[1] / 'export_chat.py', exported / 'chat.py')
    report = dict(name='Xputty Podcast · 1.5B quantized adapter pilot', initialization='Pretrained Qwen2.5-1.5B, quantized-base LoRA adaptation',
                  instruction_tuned=True, persona_profiles=PERSONAS, persona_rules=RULES,
                  base_model='Qwen/Qwen2.5-1.5B-Instruct-GGUF', base_revision='91cad51170dc346986eccefdc2dd33a9da36ead9',
                  **identity, trainable_parameters=sum(p.numel() for p in params.values()),
                  method='Rank-8 LoRA over frozen Q4_K/Q6_K weights; cached frozen prefix; original editorial curriculum',
                  completed_updates=history[-1]['step'], selected_update=best_step, requested_updates=steps,
                  context_tokens=context, model_max_context=32768, history=history, final_test=final_test,
                  example_separation=separation, selection_rule='Lowest fixed validation assistant-token loss including update zero',
                  active_layer_cache=active_cache,
                  vocabulary_cache=head_cache,
                  native_weights={'file': 'model-mixed.gguf', 'sha256': sha256(exported / 'model-mixed.gguf'), **merged},
                  license='Apache-2.0', limitations=['80 examples are a small pilot, not a complete podcast curriculum',
                  'Test topics are held out of adaptation, not necessarily original pretraining',
                  'No speech timing, audio, animation or full-duplex participation is learned',
                  'This retains a 1.5B base; it is not a distilled 48M model'], verified_ollama=False)
    write_json(output / 'training_report.json', report)
    write_json(exported / 'export_report.json', report)
    (exported / 'Modelfile').write_text('FROM ./model-mixed.gguf\nPARAMETER num_ctx 2048\nPARAMETER num_thread 2\nPARAMETER temperature 0.6\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('dataset', 'base', 'config', 'output'): p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--steps', type=int, default=80)
    p.add_argument('--context', type=int, default=256)
    p.add_argument('--layers', type=int, default=4)
    p.add_argument('--resume', action='store_true')
    print(json.dumps(train(**vars(p.parse_args())), indent=2))

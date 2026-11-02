"""Read every response: fixed factual probes, four original characters, and continuity."""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vox.public_baseline import sha256, write_json
from vox.podcast_distill import PERSONAS, RULES
from vox.public_benchmark import PROBES, indicators
from export_chat import framed_messages


def request(route, data):
    r = urllib.request.Request('http://127.0.0.1:11434/api/' + route, data=json.dumps(data).encode(),
                               headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(r, timeout=240) as s: return json.load(s)


def run(tag, weights, output, disable_thinking=False, policy='original', temperature=0.0, sampling='legacy'):
    from vox.dialogue_policy import DIRECT_DIALOGUE
    rules = DIRECT_DIALOGUE if policy == 'direct-v2' else RULES
    digest = sha256(weights)
    if digest not in request('show', {'model': tag})['modelfile']:
        raise ValueError('The named model does not match the requested weights')
    rows = []
    for probe in PROBES:
        messages, _ = framed_messages({'messages': probe['messages'], 'persona_id': 'lyra'}, PERSONAS, rules)
        began = time.perf_counter()
        payload = {'model': tag, 'messages': messages, 'stream': False, 'keep_alive': '10m',
                         'options': {'num_ctx': 2048, 'num_predict': 112, 'temperature': temperature, 'seed': 739, 'num_thread': 2, 'num_gpu': 0}}
        if disable_thinking: payload['think'] = False
        if sampling == 'qwen35-instruct': payload['options'].update(top_p=0.8, top_k=20, min_p=0.0, presence_penalty=1.5, repeat_penalty=1.0)
        result = request('chat', payload)
        text = result['message']['content']
        row = {**probe, 'response': text, 'wall_seconds': time.perf_counter() - began,
               'done_reason': result.get('done_reason'), **indicators(text, probe)}
        rows.append(row); print(json.dumps({'probe': probe['id'], 'response': text}), flush=True)
        write_json(output, {'weights_sha256': digest, 'model': tag, 'probes': rows, 'status': 'in_progress'})
    conversation = []
    previous = 'Fast zombies are obviously scarier; slow ones are easy to escape.'
    for i, persona in enumerate(list(PERSONAS) * 2):
        prompt = ('We are discussing zombie fiction in a podcast. Previous contributions:\n' +
                  '\n'.join(p['name'] + ': ' + p['text'] for p in conversation[-4:]) +
                  '\nLast speaker: ' + previous + '\nRespond to that idea with one new, specific angle. Keep it to two sentences.')
        messages, profile = framed_messages({'messages': [{'role': 'user', 'content': prompt}], 'persona_id': persona}, PERSONAS, rules)
        payload = {'model': tag, 'messages': messages, 'stream': False, 'keep_alive': '10m',
                         'options': {'num_ctx': 2048, 'num_predict': 112, 'temperature': temperature, 'seed': 739 + i, 'num_thread': 2, 'num_gpu': 0}}
        if disable_thinking: payload['think'] = False
        if sampling == 'qwen35-instruct': payload['options'].update(top_p=0.8, top_k=20, min_p=0.0, presence_penalty=1.5, repeat_penalty=1.0)
        result = request('chat', payload)
        previous = result['message']['content']
        contribution = {'name': profile['name'], 'text': previous, 'done_reason': result.get('done_reason')}
        conversation.append(contribution)
        print(json.dumps({'contribution': i + 1, **contribution}), flush=True)
    report = {'schema': 'xow-podcast-behavior/1', 'model': tag, 'weights_sha256': digest,
              'probes': rows, 'conversation': conversation, 'decoding': '2048 context, 112 maximum output tokens, two CPU threads',
              'policy': policy, 'temperature': temperature, 'rules': rules,
              'sampling': sampling,
              'thinking_explicitly_disabled': disable_thinking,
              'limitations': ['Small behavioral sample, requires reading complete responses; indicators are not quality scores',
              'Sequential order is a controlled test only, not the AzuCast response-pool scheduler',
              'No audio, delivery timing, VR, or audience participation tested',
              'Wall time can include other local workloads; this is not a latency benchmark'], 'status': 'complete'}
    write_json(output, report)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tag', required=True); p.add_argument('--weights', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    p.add_argument('--disable-thinking', action='store_true')
    p.add_argument('--policy', choices=['original', 'direct-v2'], default='original')
    p.add_argument('--temperature', type=float, default=0.0)
    p.add_argument('--sampling', choices=['legacy', 'qwen35-instruct'], default='legacy')
    run(**vars(p.parse_args()))

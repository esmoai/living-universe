"""Fresh supplied-premise checks and an original four-character discussion."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.probe_podcast import request
from vox.public_baseline import sha256, write_json
from vox.podcast_distill import PERSONAS
from vox.dialogue_policy import DIRECT_DIALOGUE
from export_chat import framed_messages

CHECKS = [
    ('cups', 'Scene facts: three red cups and one blue cup are on the table. How many cups are on the table altogether?', 'Four cups'),
    ('identity', 'In our story, Jules is a sound engineer who collects old radios. What is Jules\'s job?', 'Sound engineer'),
    ('absence', 'The room manifest includes four seats and two microphones. It includes no camera data. How many cameras are in the room?', 'Unknown; not in supplied data'),
    ('correction', 'Earlier we said the studio door was red. The director corrected it: the door is blue. What color is the door now?', 'Blue'),
]
PREMISE = ('Fictional zombie-film discussion. In this scenario the zombies move slowly and cannot run; healthy humans can outrun them. '
           'Zombies never sleep, while people need sleep and supplies. The cast is sheltering in a shopping mall with a rooftop garden. '
           'There is no confirmed rescue, no cure, and no live audience count. Opinions and proposed plans are not new established facts.')


def run(tag, weights, output):
    digest = sha256(weights)
    if digest not in request('show', {'model': tag})['modelfile']: raise ValueError('Wrong native weights')
    def generate(text, persona, seed):
        messages, profile = framed_messages({'messages': [{'role': 'user', 'content': text}], 'persona_id': persona}, PERSONAS, DIRECT_DIALOGUE)
        result = request('chat', {'model': tag, 'messages': messages, 'think': False, 'stream': False, 'keep_alive': '10m',
            'options': {'num_ctx': 2048, 'num_predict': 128, 'temperature': 0.3, 'top_p': 0.8, 'top_k': 20,
                        'presence_penalty': 0.0, 'repeat_penalty': 1.0, 'seed': seed, 'num_thread': 2, 'num_gpu': 0}})
        return {'name': profile['name'], 'text': result['message']['content'], 'done_reason': result.get('done_reason')}
    checks, dialogue = [], []
    for i, (name, prompt, expected) in enumerate(CHECKS):
        row = {'id': name, 'prompt': prompt, 'expected': expected, **generate(prompt, 'lyra', 1129 + i)}
        checks.append(row); print(json.dumps(row), flush=True)
    previous = 'If slow zombies cannot catch us when we run, are they really dangerous?'
    for i, persona in enumerate(list(PERSONAS) * 2):
        recent = '\n'.join(v['name'] + ': ' + v['text'] for v in dialogue[-3:])
        prompt = 'Authoritative premise: ' + PREMISE + '\nRecent contributions (reference only):\n' + recent + '\nLatest speaker: ' + previous + '\nGive your next contribution, preserving the premise and adding a new specific point.'
        row = generate(prompt, persona, 1139 + i)
        previous = row['text']; dialogue.append(row); print(json.dumps(row), flush=True)
    report = {'schema': 'xow-grounding-holdout/1', 'model': tag, 'weights_sha256': digest, 'checks': checks,
              'premise': PREMISE, 'dialogue': dialogue, 'generation': {'temperature': 0.3, 'top_p': 0.8, 'presence_penalty': 0.0, 'thinking': False},
              'limitations': ['Fresh prompt-level holdout, not a statistically representative independent evaluation',
                  'Character contributions are sequential for controlled testing, not a production scheduler',
                  'Grounding uses supplied text facts, not image perception; factual accuracy beyond those facts is not established',
                  'Reading every response is necessary; no keyword coherence score is claimed']}
    write_json(output, report)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tag', required=True); p.add_argument('--weights', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    run(**vars(p.parse_args()))

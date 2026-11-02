import hashlib
import io
import json

import pytest

from export_chat import budget_messages, framed_messages, OllamaSession, render_page
from vox.podcast_distill import select_reply, PERSONAS
from vox.podcast_review import REPLIES
from types import SimpleNamespace


def test_reviewed_targets_are_complete_and_personas_are_distinct():
    assert len(PERSONAS) == 4
    assert len({p["traits"] for p in PERSONAS.values()}) == 4
    assert sum(map(len, REPLIES.values())) == 80
    assert all(select_reply(reply) == reply for rows in REPLIES.values() for reply in rows)
    assert select_reply("As an AI language model, I cannot roleplay.") is None
    assert select_reply("An unfinished thought without punctuation") is None


def test_rolling_context_preserves_character_and_current_user():
    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            return list(range(sum(len(m["content"]) + 1 for m in messages)))
        def encode(self, text, **kwargs):
            return list(map(ord, text))
        def decode(self, ids):
            return "".join(map(chr, ids))
    body = {"messages": [{"role": "user", "content": "old " * 40},
                         {"role": "assistant", "content": "reply " * 40},
                         {"role": "user", "content": "new " * 40}], "persona_id": "orion"}
    messages, persona = framed_messages(body, PERSONAS, "Fictional host.")
    kept, ids, original = budget_messages(Tokenizer(), messages, 120)
    assert kept[0]["role"] == "system" and "Orion" in kept[0]["content"]
    assert kept[-1]["role"] == "user" and "new" in kept[-1]["content"]
    assert len(ids) <= 120 < original
    assert body["messages"][-1]["content"] == "new " * 40
    with pytest.raises(ValueError, match="character"):
        framed_messages({**body, "persona_id": "unregistered"}, PERSONAS, "")


def test_native_chat_rejects_wrong_model_weights(tmp_path, monkeypatch):
    import urllib.request
    import transformers
    blob = b"GGUFtest"
    (tmp_path / "model-q8_0.gguf").write_bytes(blob)
    (tmp_path / "export_report.json").write_text("{}")
    (tmp_path / "conversion-q8_0.json").write_text(json.dumps({"output_sha256": hashlib.sha256(blob).hexdigest()}))
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: io.BytesIO(json.dumps({"modelfile": "FROM some-other-weights"}).encode()))
    monkeypatch.setattr(transformers.AutoTokenizer, "from_pretrained", lambda *a, **k: None)
    with pytest.raises(ValueError, match="does not use this exported GGUF"):
        OllamaSession(tmp_path, "wrong-model")


def test_character_choices_escape_names():
    session = SimpleNamespace(context=32768, instruction_tuned=True, model_name="Pilot", persona_profiles=PERSONAS)
    page = render_page(session)
    assert page.count('<option value="lyra">') == 1
    assert "__PERSONA_CONTROL__" not in page
    assert 'persona_id:' in page


def test_native_reference_uses_explicit_sampling_and_disables_thinking(tmp_path, monkeypatch):
    import urllib.request
    import transformers
    blob = b'GGUF-reference'
    checksum = hashlib.sha256(blob).hexdigest()
    (tmp_path / 'reference.gguf').write_bytes(blob)
    (tmp_path / 'config.json').write_text(json.dumps({'text_config': {'max_position_embeddings': 32768}}))
    (tmp_path / 'export_report.json').write_text(json.dumps({
        'native_weights': {'file': 'reference.gguf', 'sha256': checksum},
        'instruction_tuned': True, 'disable_thinking': True,
        'generation_options': {'top_p': 0.8, 'presence_penalty': 0.2, 'num_thread': 99},
        'persona_profiles': PERSONAS, 'persona_rules': 'Reply directly.'}))
    requests, template_options = [], []
    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            template_options.append(kwargs)
            return list(range(20))
    monkeypatch.setattr(transformers.AutoTokenizer, 'from_pretrained', lambda *a, **k: Tokenizer())
    def open_url(request, **kwargs):
        data = json.loads(request.data)
        requests.append(data)
        result = {'modelfile': 'FROM sha256-' + checksum} if request.full_url.endswith('/show') else {'message': {'content': 'One fresh idea.'}, 'eval_count': 5}
        return io.BytesIO(json.dumps(result).encode())
    monkeypatch.setattr(urllib.request, 'urlopen', open_url)
    session = OllamaSession(tmp_path, 'reference')
    reply = session.respond({'messages': [{'role': 'user', 'content': 'Hello'}], 'persona_id': 'nova', 'context_tokens': 512})
    assert reply['character'] == 'Nova' and reply['text'] == 'One fresh idea.'
    assert requests[-1]['think'] is False
    assert requests[-1]['options']['top_p'] == 0.8
    assert requests[-1]['options']['num_thread'] == 2
    assert all(v['enable_thinking'] is False for v in template_options)

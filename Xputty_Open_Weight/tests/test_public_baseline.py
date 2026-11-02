from types import SimpleNamespace

import pytest

from vox.public_baseline import canonical_messages, select_rows
from vox.public_control import assistant_example, check_example_separation
from vox.plain_text import build
from export_chat import render_page


def messages():
    return [{"role": "user", "content": "Why does conversation matter? " * 15},
            {"role": "assistant", "content": "Listening helps us understand another perspective. " * 20}]


def test_public_sources_deduplicate_without_invented_timing():
    original = messages()
    row = {"source": "everyday-conversations", "messages": original}
    seen = set()
    result = select_rows([row, row], 1, "train", seen)
    assert result[0]["messages"] == [{**m, "content": m["content"].strip()} for m in original]
    assert "start_ms" not in result[0]
    with pytest.raises(ValueError, match="Only 0"):
        select_rows([row], 1, "test", seen)
    assert canonical_messages(original[::-1]) is None
    assert canonical_messages([original[0]]) is None
    assert canonical_messages([original[0], {"role": "assistant", "content": "```" * 100}]) is None


def test_modern_public_corpus_has_correct_origin_and_no_split_leakage(tmp_path):
    files = []
    for i in range(6):
        file = tmp_path / f"conversation-{i}.txt"
        file.write_text(f"Visitor: Question number {i}.\nCompanion: " + "An answer with some detail. " * 25, encoding="utf-8")
        files.append(file)
    report = build(files, tmp_path / "data", provenance={"kind": "public-conversations"})
    assert report["origin"] == "public_conversation_text"
    assert report["timing_mode"] == "none"
    groups = [set(v["episode_ids"]) for v in report["splits"].values()]
    assert all(not a & b for i, a in enumerate(groups) for b in groups[i + 1:])
    assert "<|at_ms|>" not in (tmp_path / "data/tokenizer_train.txt").read_text(encoding="utf-8")


def test_assistant_only_targets_and_control_page_label():
    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            return [1, 2, 3] if len(messages) == 1 else [1, 2, 3, 4, 5, 6]
    inputs, labels = assistant_example(Tokenizer(), messages(), context=64)
    assert inputs.tolist() == [[1, 2, 3, 4, 5, 6]]
    assert labels.tolist() == [[-100, -100, -100, 4, 5, 6]]
    with pytest.raises(ValueError, match="cross adaptation"):
        check_example_separation([(inputs, labels)], [(inputs, labels)], [])
    page = render_page(SimpleNamespace(context=8192, instruction_tuned=True, model_name="135M <control>"))
    assert "135M &lt;control&gt;" in page
    assert "separate from the 48M scratch experiment" in page
    assert "__MAX_CONTEXT__" not in page and "__MODEL_DESCRIPTION__" not in page

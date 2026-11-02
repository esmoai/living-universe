"""Train SentencePiece only from train-partition podcast text; never from holdouts."""

import argparse, hashlib, json
from pathlib import Path
import sentencepiece as spm
from .corpus import CUSTOM_TOKENS


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def train(data_dir, vocab_size=4096):
    p = Path(data_dir)
    if not (p / "corpus_report.json").is_file():
        raise ValueError("run corpus validation/splitting first")
    corpus_report = json.loads((p / "corpus_report.json").read_text())
    input_file = p / "tokenizer_train.txt"
    if not input_file.exists():
        raise FileNotFoundError(input_file)
    symbols = list(CUSTOM_TOKENS)
    if corpus_report.get("representation") == "unlabelled-dialogue-timing-v1":
        from .raw_baseline import RAW_TOKENS

        symbols += RAW_TOKENS
    raw_mode = corpus_report.get("representation") in (
        "unlabelled-dialogue-timing-v1",
        "plain-text-works-v1",
    )
    if corpus_report.get("representation") == "plain-text-works-v1":
        symbols = ["<|eod|>"]
    normalizer_options = (
        dict(
            normalization_rule_name="identity",
            add_dummy_prefix=False,
            remove_extra_whitespaces=False,
        )
        if raw_mode
        else {}
    )
    spm.SentencePieceTrainer.Train(
        input=str(input_file),
        model_prefix=str(p / "vox"),
        vocab_size=int(vocab_size),
        model_type="bpe",
        character_coverage=1.0,
        byte_fallback=True,
        hard_vocab_limit=False,
        pad_id=3,
        unk_id=0,
        bos_id=1,
        eos_id=2,
        user_defined_symbols=symbols,
        num_threads=2,
        max_sentence_length=20000,
        shuffle_input_sentence=False,
        input_sentence_size=0,
        minloglevel=2,
        **normalizer_options,
    )
    sp = spm.SentencePieceProcessor(model_file=str(p / "vox.model"))
    record = {
        "vocab_size": sp.get_piece_size(),
        "vocab_requested": int(vocab_size),
        "sha256": sha256(p / "vox.model"),
        "training_partition": "train only",
        "corpus_digest": corpus_report["corpus_digest"],
    }
    record["normalizer_profile"] = (
        "identity-preserve-whitespace" if raw_mode else "sentencepiece-default"
    )
    (p / "tokenizer_report.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--data", required=True)
    a.add_argument("--vocab-size", type=int, default=4096)
    r = a.parse_args()
    print(json.dumps(train(r.data, r.vocab_size), indent=2))

"""Export standard LLaMA weights in safetensors + v3 GGUF (F16).

Interoperability: exact tensor/metadata checks are automated here. Runtime support
requires a separate Ollama/llama.cpp smoke test on the user's machine.
"""

import argparse, json, shutil, struct
from pathlib import Path
import numpy as np
import sentencepiece as spm
from safetensors.torch import save_file
from .model import ModelConfig, TinyLlama
from .tokenizer import sha256
from .limits import limit_cpu

TYPE_UINT8 = 0
TYPE_UINT32 = 4
TYPE_INT32 = 5
TYPE_FLOAT32 = 6
TYPE_BOOL = 7
TYPE_STRING = 8
TYPE_ARRAY = 9
TYPE_UINT64 = 10
GGML_F32 = 0
GGML_F16 = 1


def put_u32(f, x):
    f.write(struct.pack("<I", int(x)))


def put_u64(f, x):
    f.write(struct.pack("<Q", int(x)))


def put_str(f, x):
    b = str(x).encode("utf8")
    put_u64(f, len(b))
    f.write(b)


def write_val(f, kind, v):
    if kind == TYPE_STRING:
        put_str(f, v)
    elif kind == TYPE_UINT32:
        put_u32(f, v)
    elif kind == TYPE_INT32:
        f.write(struct.pack("<i", int(v)))
    elif kind == TYPE_UINT64:
        put_u64(f, v)
    elif kind == TYPE_FLOAT32:
        f.write(struct.pack("<f", float(v)))
    elif kind == TYPE_BOOL:
        f.write(struct.pack("<?", bool(v)))
    elif isinstance(kind, tuple) and kind[0] == TYPE_ARRAY:
        put_u32(f, kind[1])
        put_u64(f, len(v))
        for item in v:
            write_val(f, kind[1], item)
    else:
        raise ValueError(f"bad GGUF type {kind}")


def write_meta(f, k, kind, v):
    put_str(f, k)
    put_u32(f, kind[0] if isinstance(kind, tuple) else kind)
    write_val(f, kind, v)


def create_gguf(model, sp, out_path, model_name):
    c = model.config
    if c.experiment != "dense":
        raise ValueError(
            "GGUF export prohibited for experimental attention: no llama.cpp kernel"
        )
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    words = [sp.id_to_piece(i) for i in range(sp.get_piece_size())]
    # GGML token type: 1 NORMAL, 2 UNKNOWN, 3 CONTROL, 4 USER_DEFINED, 5 UNUSED, 6 BYTE
    from .corpus import CUSTOM_TOKENS
    from .raw_baseline import RAW_TOKENS
    from sentencepiece import sentencepiece_model_pb2

    proto = sentencepiece_model_pb2.ModelProto()
    proto.ParseFromString(sp.serialized_model_proto())
    custom = set(CUSTOM_TOKENS + RAW_TOKENS)
    types = []
    for i in range(sp.get_piece_size()):
        typ = (
            2
            if sp.is_unknown(i)
            else 3
            if sp.is_control(i)
            else 4
            if sp.id_to_piece(i) in custom
            else 6
            if sp.is_byte(i)
            else 5
            if sp.is_unused(i)
            else 1
        )
        types.append(typ)
    items = [
        ("general.architecture", TYPE_STRING, "llama"),
        ("general.name", TYPE_STRING, model_name),
        (
            "general.description",
            TYPE_STRING,
            "Experimental original tiny LLaMA decoder trained from random initialization; see model card for rights and suitability.",
        ),
        ("general.alignment", TYPE_UINT32, 32),
        ("general.file_type", TYPE_UINT32, 1),
        ("llama.context_length", TYPE_UINT32, c.context),
        ("llama.embedding_length", TYPE_UINT32, c.dim),
        ("llama.block_count", TYPE_UINT32, c.layers),
        ("llama.feed_forward_length", TYPE_UINT32, c.ffn_dim),
        ("llama.rope.dimension_count", TYPE_UINT32, c.dim // c.heads),
        ("llama.attention.head_count", TYPE_UINT32, c.heads),
        ("llama.attention.head_count_kv", TYPE_UINT32, c.heads),
        ("llama.attention.layer_norm_rms_epsilon", TYPE_FLOAT32, c.norm_eps),
        ("llama.rope.freq_base", TYPE_FLOAT32, c.rope_theta),
        ("tokenizer.ggml.model", TYPE_STRING, "llama"),
        ("tokenizer.ggml.tokens", (TYPE_ARRAY, TYPE_STRING), words),
        (
            "tokenizer.ggml.scores",
            (TYPE_ARRAY, TYPE_FLOAT32),
            [float(sp.get_score(i)) for i in range(sp.get_piece_size())],
        ),
        ("tokenizer.ggml.token_type", (TYPE_ARRAY, TYPE_INT32), types),
        ("tokenizer.ggml.bos_token_id", TYPE_UINT32, sp.bos_id()),
        ("tokenizer.ggml.eos_token_id", TYPE_UINT32, sp.eos_id()),
        ("tokenizer.ggml.unknown_token_id", TYPE_UINT32, sp.unk_id()),
        ("tokenizer.ggml.padding_token_id", TYPE_UINT32, sp.pad_id()),
        ("tokenizer.ggml.add_bos_token", TYPE_BOOL, False),
        ("tokenizer.ggml.add_eos_token", TYPE_BOOL, False),
        (
            "tokenizer.ggml.add_space_prefix",
            TYPE_BOOL,
            proto.normalizer_spec.add_dummy_prefix,
        ),
        (
            "tokenizer.ggml.remove_extra_whitespaces",
            TYPE_BOOL,
            proto.normalizer_spec.remove_extra_whitespaces,
        ),
    ]
    sd = model.state_dict()
    tensors = [("token_embd.weight", sd["embed_tokens.weight"])]
    for i in range(c.layers):
        bp = f"layers.{i}."
        tensors += [
            (f"blk.{i}.attn_norm.weight", sd[bp + "input_layernorm.weight"]),
            (f"blk.{i}.attn_q.weight", sd[bp + "self_attn.q_proj.weight"]),
            (f"blk.{i}.attn_k.weight", sd[bp + "self_attn.k_proj.weight"]),
            (f"blk.{i}.attn_v.weight", sd[bp + "self_attn.v_proj.weight"]),
            (f"blk.{i}.attn_output.weight", sd[bp + "self_attn.o_proj.weight"]),
            (f"blk.{i}.ffn_norm.weight", sd[bp + "post_attention_layernorm.weight"]),
            (f"blk.{i}.ffn_gate.weight", sd[bp + "mlp.gate_proj.weight"]),
            (f"blk.{i}.ffn_up.weight", sd[bp + "mlp.up_proj.weight"]),
            (f"blk.{i}.ffn_down.weight", sd[bp + "mlp.down_proj.weight"]),
        ]
    tensors.extend(
        [
            ("output_norm.weight", sd["norm.weight"]),
            ("output.weight", sd["lm_head.weight"]),
        ]
    )
    chunks = []
    for name, t in tensors:
        arr = t.detach().numpy()
        if name.endswith(("attn_q.weight", "attn_k.weight")):
            # HuggingFace half-rotary -> GGUF interleaved rotation ordering.
            arr = (
                arr.reshape(c.heads, 2, c.dim // c.heads // 2, arr.shape[1])
                .transpose(0, 2, 1, 3)
                .reshape(arr.shape)
            )
        ggtyp = GGML_F32 if name.endswith(("norm.weight",)) else GGML_F16
        dtype = "<f4" if ggtyp == GGML_F32 else "<f2"
        arr = np.asarray(arr, dtype=dtype, order="C")
        chunks.append((name, ggtyp, arr))

    def aligned(offset):
        return (offset + 31) & ~31

    offsets = []
    offset = 0
    for name, typ, arr in chunks:
        offset = aligned(offset)
        offsets.append(offset)
        offset += arr.nbytes
    with p.open("wb") as f:
        f.write(b"GGUF")
        put_u32(f, 3)
        put_u64(f, len(chunks))
        put_u64(f, len(items))
        for k, t, v in items:
            write_meta(f, k, t, v)
        for (name, typ, arr), ofs in zip(chunks, offsets):
            put_str(f, name)
            put_u32(f, arr.ndim)
            for d in reversed(arr.shape):
                put_u64(f, d)
            put_u32(f, typ)
            put_u64(f, ofs)
        pos = aligned(f.tell())
        f.write(b"\x00" * (pos - f.tell()))
        start = f.tell()
        for (_, _, arr), ofs in zip(chunks, offsets):
            current = f.tell() - start
            f.write(b"\x00" * (ofs - current))
            f.write(arr.tobytes(order="C"))
    return dict(
        path=str(p),
        bytes=p.stat().st_size,
        sha256=sha256(p),
        n_tensors=len(chunks),
        n_meta=len(items),
    )


def export(data, checkpoint, output, cores=2):
    torch = limit_cpu(cores)
    root = Path(data)
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    meta = torch.load(checkpoint, map_location="cpu", weights_only=True)
    c = ModelConfig(**meta["config"])
    if c.experiment != "dense":
        raise ValueError(
            "Standard GGUF/HF release requires a dense Llama-compatible model"
        )
    if meta["tokenizer_sha256"] != sha256(root / "vox.model"):
        raise ValueError("tokenizer SHA mismatch")
    if (
        meta["report_digest"]
        != json.loads((root / "corpus_report.json").read_text())["corpus_digest"]
    ):
        raise ValueError("corpus SHA mismatch")
    model = TinyLlama(c)
    model.load_state_dict(meta["weights"], strict=True)
    model.eval()
    shutil.copy2(root / "vox.model", out / "tokenizer.model")
    shutil.copy2(root / "vox.vocab", out / "tokenizer.vocab")
    config = {
        "architectures": ["LlamaForCausalLM"],
        "model_type": "llama",
        "vocab_size": c.vocab_size,
        "hidden_size": c.dim,
        "intermediate_size": c.ffn_dim,
        "num_hidden_layers": c.layers,
        "num_attention_heads": c.heads,
        "num_key_value_heads": c.heads,
        "max_position_embeddings": c.context,
        "rms_norm_eps": c.norm_eps,
        "rope_theta": c.rope_theta,
        "hidden_act": "silu",
        "attention_bias": False,
        "mlp_bias": False,
        "tie_word_embeddings": False,
        "bos_token_id": c.bos_token_id,
        "eos_token_id": c.eos_token_id,
        "pad_token_id": c.pad_token_id,
        "torch_dtype": "float32",
        "initializer_range": 0.02,
        "use_cache": True,
    }
    (out / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    (out / "tokenizer_config.json").write_text(
        json.dumps(
            {
                "tokenizer_class": "LlamaTokenizer",
                "legacy": True,
                "model_max_length": c.context,
                "add_bos_token": False,
                "add_eos_token": False,
                "bos_token": "<s>",
                "eos_token": "</s>",
                "pad_token": "<pad>",
                "unk_token": "<unk>",
                "clean_up_tokenization_spaces": False,
            },
            indent=2,
        )
        + "\n"
    )
    (out / "special_tokens_map.json").write_text(
        json.dumps(
            {
                "bos_token": "<s>",
                "eos_token": "</s>",
                "pad_token": "<pad>",
                "unk_token": "<unk>",
            },
            indent=2,
        )
        + "\n"
    )
    # Transformers LlamaForCausalLM expects model.* names for decoder weights.
    # The in-house TinyLlama omits that outer `model` submodule. Preserve lm_head.
    hf_weights = {
        ("lm_head.weight" if k == "lm_head.weight" else "model." + k): v.detach()
        .cpu()
        .contiguous()
        for k, v in model.state_dict().items()
    }
    save_file(hf_weights, str(out / "model.safetensors"), metadata={"format": "pt"})
    sp = spm.SentencePieceProcessor(model_file=str(root / "vox.model"))
    raw_mode = meta.get("representation") == "unlabelled-dialogue-timing-v1"
    plain_mode = meta.get("representation") == "plain-text-works-v1"
    if raw_mode or plain_mode:
        # User-defined SentencePiece symbols are ordinary atomic tokens, not
        # pre-normalization special-token splits. Preserve the full normalizer.
        from transformers import LlamaTokenizer
        from transformers.convert_slow_tokenizer import LlamaConverter
        from tokenizers import normalizers, Regex, AddedToken
        from sentencepiece import sentencepiece_model_pb2

        proto = sentencepiece_model_pb2.ModelProto()
        proto.ParseFromString((root / "vox.model").read_bytes())
        slow = LlamaTokenizer(
            vocab_file=str(root / "vox.model"),
            legacy=True,
            add_bos_token=False,
            add_eos_token=False,
        )
        fast = LlamaConverter(slow).converted()
        normal = []
        if proto.normalizer_spec.precompiled_charsmap:
            normal.append(
                normalizers.Precompiled(proto.normalizer_spec.precompiled_charsmap)
            )
        if proto.normalizer_spec.remove_extra_whitespaces:
            normal.extend([normalizers.Replace(Regex(" +"), " "), normalizers.Strip()])
        if proto.normalizer_spec.add_dummy_prefix:
            normal.append(normalizers.Prepend(" "))
        if proto.normalizer_spec.escape_whitespaces:
            normal.append(normalizers.Replace(" ", "▁"))
        fast.normalizer = normalizers.Sequence(normal)
        fast.add_tokens(
            [
                AddedToken(piece.piece, normalized=False, special=False)
                for piece in proto.pieces
                if piece.type == 4
            ]
        )
        fast.save(str(out / "tokenizer.json"))
        settings = json.loads((out / "tokenizer_config.json").read_text())
        settings["add_prefix_space"] = proto.normalizer_spec.add_dummy_prefix
        (out / "tokenizer_config.json").write_text(
            json.dumps(settings, indent=2) + "\n"
        )
    gg = create_gguf(
        model,
        sp,
        out / "vox-fibra-f16.gguf",
        "Xputty Historical Prose"
        if plain_mode
        else "Vox Dialogue Timing Raw Baseline"
        if raw_mode
        else "Vox FIBRA R02 Technical Smoke"
        if not meta["release_eligible"]
        else "Vox FIBRA R02 Research Checkpoint",
    )
    (out / "Modelfile").write_text(
        'FROM ./vox-fibra-f16.gguf\nTEMPLATE """{{ .Prompt }}"""\nPARAMETER num_ctx '
        + str(c.context)
        + '\nPARAMETER temperature 0.8\nPARAMETER stop "'
        + ("<|eod|>" if raw_mode or plain_mode else "<|turn|>")
        + '"\n'
    )
    card = """---\nlanguage:\n- en\ntags:\n- from-scratch\n- tiny-language-model\n- research\n---\n# Vox FIBRA R02 — UNVERIFIED RESEARCH CHECKPOINT\n\nThis artifact is an original randomly initialized LLaMA-style decoder trained with Vox FIBRA tools.\n\n**Do not advertise it as podcast-trained or production-ready unless the corpus rights, training, held-out natural conversation quality, GGUF runtime compatibility, and hardware benchmarks have all been verified.**\n\nTraining origin: **{origin}**. Permission basis and source records are in `corpus_report.json` (only aggregate lineage is exported; raw transcripts are not redistributed).\n\nModel parameters: **{params:,}**. Context: **{ctx} tokens**. Training steps: **{steps}** ({stage}).\n\nThis is a technical smoke run on entirely synthetic phrases, NOT a completed modern conversational model.\n\nNative Ollama/llama.cpp inference was not validated by this generator. Run the documented compatibility checks before publishing.\n\nSafety, bias, age suitability, paraphrase memorization, naturalness, and full reproducibility on third-party hardware have not been established.\n""".format(
        origin=meta["run_kind"],
        params=model.n_parameters(),
        ctx=c.context,
        steps=meta["step"],
        stage=meta["stage"],
    )
    if meta["release_eligible"]:
        card = card.replace(
            "This is a technical smoke run on entirely synthetic phrases, NOT a completed modern conversational model.",
            "This is a research checkpoint trained from a rights-gated podcast corpus. Quality, licensing, and compatibility require independent review.",
        )
    if raw_mode:
        card = card.replace(
            "This is a technical smoke run on entirely synthetic phrases, NOT a completed modern conversational model.",
            "This local research checkpoint was trained on user-supplied, unlabelled timestamped dialogue. It is not a synthetic fixture. Source segments are not verified speaker turns. Source-start deltas are not measured speech pauses. Public distribution is not authorized by this export.",
        )
        card += "\nSerialization: `<|segment|><|at_ms|>1000<|delta_ms|>0<|text|>Dialogue...`. Timing markers are machine-readable source positions, not text to speak. Natural dialogue and timing quality have not been established.\n"
    if plain_mode:
        card = f"""# Xputty Historical Prose — experimental weights

Randomly initialized LLaMA-style model; {model.n_parameters():,} parameters,
{meta["step"]} updates, {c.context}-token training windows. No pretrained weights.
Trained on prose with whole-work train/validation/test splits and a train-only tokenizer.
See corpus_report.json and historical-sources.json for dates, editions and checksums.
Modern digital transcription dates are not original publication dates.
This is next-token pretraining, not instruction tuning: conversational responsiveness,
accuracy, period purity and fluency are not established. Historical texts contain period biases.

## Chat with these exported weights

Install Python 3.11, then `python -m pip install 'transformers>=4.57,<4.58' torch sentencepiece safetensors`.
Run `python chat.py` inside this model folder. It prints a private localhost browser link.
Alternatively: `ollama create xputty-1800s -f Modelfile` then `ollama run xputty-1800s`.
The scratch model has no trained chat template. The browser exposes both experimental
chat framing and direct prose continuation. Nothing is forwarded to a larger model.
Runtime parity checks are reported separately in export_report.json.
"""
    if meta["run_kind"] == "public_conversation_scratch_experiment":
        card = f"""# Xputty Public Conversation — 48M scratch research baseline

{model.n_parameters():,} parameters, {meta['step']} updates; randomly initialized.
Maximum context: {c.context}. See reports for actual window exposure.
Public synthetic conversation text from HuggingFaceTB/smol-smoltalk, pinned revision,
checksums and Apache-2.0 attribution in public-sources.json and UPSTREAM-DATASET-CARD.md.
Whole conversations are held out; the tokenizer is fitted only to training text.
Visitor/Companion labels retain known source roles. No audio or speech timing is invented.
This is next-token language training, not a completed instruction-tuned podcast host.
Coherence and factual grounding must be evaluated separately from prediction loss.

Run `python chat.py` to use these exported weights locally, or import Modelfile in Ollama.
No pretrained model or remote fallback is used by this scratch checkpoint.
The 135M pretrained control, when supplied, is a separate model and is never substituted.
"""
    (out / "README.md").write_text(card, encoding="utf-8")
    shutil.copy2(root / "corpus_report.json", out / "corpus_report.json")
    report = dict(
        parameter_count=model.n_parameters(),
        run_kind=meta["run_kind"],
        release_eligible=meta["release_eligible"],
        weights_sha256=sha256(out / "model.safetensors"),
        gguf=gg,
        source_checkpoint_sha256=sha256(checkpoint),
        verified_ollama=False,
        verified_llama_cpp=False,
        verified_hf_transformers=False,
    )
    report["representation"] = meta.get("representation", "reviewed-speaker-turns")
    (out / "export_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--cores", type=int, default=2)
    a = p.parse_args()
    print(json.dumps(export(a.data, a.checkpoint, a.output, a.cores), indent=2))

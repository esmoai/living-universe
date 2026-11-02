"""Small independent GGUF v3 metadata reader and weight parity checker."""

import struct, numpy as np


def inspect_gguf(path):
    f = open(path, "rb")

    def rd(fmt):
        return struct.unpack("<" + fmt, f.read(struct.calcsize("<" + fmt)))[0]

    def s():
        return f.read(rd("Q")).decode("utf8")

    def value(t):
        if t == 8:
            return s()
        if t == 9:
            item = rd("I")
            n = rd("Q")
            return [value(item) for _ in range(n)]
        return rd(
            {
                0: "B",
                1: "b",
                2: "H",
                3: "h",
                4: "I",
                5: "i",
                6: "f",
                7: "?",
                10: "Q",
                11: "q",
                12: "d",
            }[t]
        )

    if f.read(4) != b"GGUF":
        raise ValueError("not GGUF")
    version = rd("I")
    n_t = rd("Q")
    n_kv = rd("Q")
    if version != 3:
        raise ValueError("GGUF version !=3")
    metadata = {}
    for _ in range(n_kv):
        k = s()
        t = rd("I")
        metadata[k] = value(t)
    tensors = {}
    for _ in range(n_t):
        name = s()
        nd = rd("I")
        dims = [rd("Q") for _ in range(nd)]
        typ = rd("I")
        offset = rd("Q")
        tensors[name] = (dims, typ, offset)
    a = metadata.get("general.alignment", 32)
    start = (f.tell() + a - 1) // a * a
    return metadata, tensors, start


def check_parity(file, model):
    meta, tensors, start = inspect_gguf(file)
    c = model.config
    state = model.state_dict()
    names = {
        "token_embd.weight": "embed_tokens.weight",
        "output.weight": "lm_head.weight",
        "output_norm.weight": "norm.weight",
    }
    expected = []
    worst = 0
    with open(file, "rb") as f:
        for name, (dims, typ, offset) in tensors.items():
            if name.startswith("blk."):
                _, i, k = name.split(".", 2)
                mp = {
                    "attn_norm.weight": "input_layernorm.weight",
                    "attn_q.weight": "self_attn.q_proj.weight",
                    "attn_k.weight": "self_attn.k_proj.weight",
                    "attn_v.weight": "self_attn.v_proj.weight",
                    "attn_output.weight": "self_attn.o_proj.weight",
                    "ffn_norm.weight": "post_attention_layernorm.weight",
                    "ffn_gate.weight": "mlp.gate_proj.weight",
                    "ffn_up.weight": "mlp.up_proj.weight",
                    "ffn_down.weight": "mlp.down_proj.weight",
                }
                src = state[f"layers.{i}." + mp[k]].numpy()
            else:
                src = state[names[name]].numpy()
            if name.endswith(("attn_q.weight", "attn_k.weight")):
                src = (
                    src.reshape(c.heads, 2, c.dim // c.heads // 2, src.shape[1])
                    .transpose(0, 2, 1, 3)
                    .reshape(src.shape)
                )
            f.seek(start + offset)
            raw = f.read(int(np.prod(dims)) * (2 if typ == 1 else 4))
            arr = (
                np.frombuffer(raw, dtype="<f2" if typ == 1 else "<f4")
                .copy()
                .reshape(tuple(dims[::-1]))
            )
            diff = float(np.max(np.abs(arr.astype(np.float32) - src)))
            worst = max(worst, diff)
            if diff > 1e-3:
                expected.append((name, diff))
    return dict(
        tensors=len(tensors),
        maximum_f16_difference=worst,
        errors=expected,
        pass_all=not bool(expected),
        llama_architecture=meta.get("general.architecture"),
        vocab_count=len(meta.get("tokenizer.ggml.tokens", [])),
    )

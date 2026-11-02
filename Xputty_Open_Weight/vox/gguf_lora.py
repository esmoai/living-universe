"""CPU-only Qwen2 GGUF adapter research.

Frozen quantized tensors stay memory-mapped. Linear weights are dequantized on
demand, including again for input gradients, so autograd need not retain a dense
copy of every frozen weight. The vocabulary projection is processed in chunks.
This is an engineering prototype, not a claim of a new distillation algorithm.
"""
import math
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn


def unpack(tensor, first=None, last=None):
    import gguf
    data = tensor.data if first is None else tensor.data[first:last]
    values = gguf.quants.dequantize(data, tensor.tensor_type).astype(np.float32, copy=False)
    return torch.from_numpy(values if values.flags.writeable else values.copy())


def project(x, tensor, bias=None, transpose=False):
    rows = int(tensor.shape[1])
    if rows <= 16384:
        weight = unpack(tensor)
        return x.matmul(weight) if transpose else F.linear(x, weight, bias)
    if transpose:
        result = torch.zeros((*x.shape[:-1], int(tensor.shape[0])), dtype=x.dtype)
        for start in range(0, rows, 4096):
            end = min(rows, start + 4096)
            result.add_(x[..., start:end].matmul(unpack(tensor, start, end)))
        return result
    parts = []
    for start in range(0, rows, 4096):
        end = min(rows, start + 4096)
        parts.append(F.linear(x, unpack(tensor, start, end), None if bias is None else bias[start:end]))
    return torch.cat(parts, dim=-1)


class FrozenProjection(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x, tensor, bias):
        if x.device.type != "cpu":
            raise ValueError("This GGUF adapter prototype is CPU-only")
        ctx.tensor = tensor
        return project(x, tensor, bias)

    @staticmethod
    def backward(ctx, gradient):
        return project(gradient, ctx.tensor, transpose=True), None, None


class PackedLinear(nn.Module):
    def __init__(self, tensor, bias=None, rank=0, alpha=16):
        super().__init__()
        self.tensor = tensor
        self.in_features, self.out_features = map(int, tensor.shape)
        self.register_buffer("bias", unpack(bias) if bias is not None else None)
        self.rank, self.scale = rank, alpha / max(1, rank)
        if rank:
            self.lora_A = nn.Parameter(torch.empty(rank, self.in_features))
            self.lora_B = nn.Parameter(torch.zeros(self.out_features, rank))
            nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))

    def forward(self, x):
        if hasattr(self, '_active_weight'):
            output = F.linear(x, self._active_weight, self.bias)
        elif hasattr(self, '_prefix_weight'):
            if torch.is_grad_enabled():
                raise ValueError("Prefix weight caching is inference-only")
            output = F.linear(x, self._prefix_weight, self.bias)
        else:
            output = FrozenProjection.apply(x, self.tensor, self.bias)
        if self.rank:
            output = output + F.linear(F.linear(x, self.lora_A), self.lora_B) * self.scale
        return output


class PackedEmbedding(nn.Module):
    def __init__(self, tensor):
        super().__init__()
        self.tensor = tensor
        self.embedding_dim, self.num_embeddings = map(int, tensor.shape)

    def forward(self, ids):
        unique, inverse = torch.unique(ids.reshape(-1), return_inverse=True)
        import gguf
        packed = self.tensor.data[unique.numpy()]
        values = torch.from_numpy(gguf.quants.dequantize(packed, self.tensor.tensor_type).astype(np.float32, copy=False))
        return values.index_select(0, inverse).reshape(*ids.shape, self.embedding_dim)


def tensor_name(path, suffix="weight"):
    if path == "lm_head":
        return "output." + suffix
    parts = path.split(".")
    if len(parts) < 5 or parts[:2] != ["model", "layers"]:
        raise ValueError("Unsupported GGUF linear module: " + path)
    mapping = {"q_proj": "attn_q", "k_proj": "attn_k", "v_proj": "attn_v", "o_proj": "attn_output",
               "gate_proj": "ffn_gate", "up_proj": "ffn_up", "down_proj": "ffn_down"}
    return f"blk.{parts[2]}.{mapping[parts[-1]]}.{suffix}"


def load_quantized_qwen(base, config_folder, adapted_layers=4, rank=8, alpha=16):
    import gguf
    from transformers import AutoConfig, AutoModelForCausalLM
    from transformers.models.qwen2.modeling_qwen2 import Qwen2RotaryEmbedding

    if not 1 <= adapted_layers <= 8 or rank not in (4, 8, 16):
        raise ValueError("Choose 1–8 adapted layers and rank 4/8/16")
    reader = gguf.GGUFReader(str(base))
    config = AutoConfig.from_pretrained(config_folder, local_files_only=True, trust_remote_code=False)
    if config.model_type != "qwen2" or reader.fields["general.architecture"].contents() != "qwen2":
        raise ValueError("Only the verified Qwen2 architecture is supported")
    config.use_cache = False
    config.tie_word_embeddings = False  # GGUF embeds/output may have different quantization.
    tensors = {t.name: t for t in reader.tensors}
    if int(reader.fields["qwen2.embedding_length"].contents()) != config.hidden_size:
        raise ValueError("GGUF/config dimensions disagree")
    with torch.device("meta"):
        model = AutoModelForCausalLM.from_config(config, attn_implementation="sdpa", trust_remote_code=False)
    for path, module in list(model.named_modules()):
        if isinstance(module, nn.Linear):
            name = tensor_name(path)
            selected = path != "lm_head" and int(path.split(".")[2]) >= config.num_hidden_layers - adapted_layers
            replacement = PackedLinear(tensors[name], tensors.get(tensor_name(path, "bias")), rank if selected else 0, alpha)
        elif isinstance(module, nn.Embedding):
            replacement = PackedEmbedding(tensors["token_embd.weight"])
        else:
            continue
        parent, leaf = path.rsplit(".", 1) if "." in path else ("", path)
        setattr(model.get_submodule(parent) if parent else model, leaf, replacement)
    for i, layer in enumerate(model.model.layers):
        layer.input_layernorm.weight = nn.Parameter(unpack(tensors[f"blk.{i}.attn_norm.weight"]), requires_grad=False)
        layer.post_attention_layernorm.weight = nn.Parameter(unpack(tensors[f"blk.{i}.ffn_norm.weight"]), requires_grad=False)
    model.model.norm.weight = nn.Parameter(unpack(tensors["output_norm.weight"]), requires_grad=False)
    model.model.rotary_emb = Qwen2RotaryEmbedding(config, device="cpu")
    model._gguf_reader = reader
    model._gguf_path = Path(base).resolve()
    if any(p.is_meta for p in model.parameters()) or any(b.is_meta for b in model.buffers()):
        raise ValueError("Uninitialized model tensor remains")
    return model


def adapter_weights(model):
    return {name: parameter for name, parameter in model.named_parameters() if parameter.requires_grad}


def cache_active_layers(model, max_bytes=800 * 1024**2):
    """Expand only adapted layers inside a fixed budget, never the full backbone."""
    modules = [m for m in model.modules() if isinstance(m, PackedLinear) and m.rank]
    required = sum(m.in_features * m.out_features * 4 for m in modules)
    if required > max_bytes:
        return {'cached_bytes': 0, 'reason': 'Active layers exceed the cache budget; using on-demand dequantization'}
    for module in modules:
        module._active_weight = unpack(module.tensor)
    return {'cached_bytes': required, 'matrices': len(modules)}


def cache_output_head(model, max_bytes=1024**3):
    """Optionally cache the frozen vocabulary head, building it in bounded chunks."""
    head = model.lm_head
    required = head.in_features * head.out_features * 4
    if required > max_bytes:
        return {'cached_bytes': 0, 'reason': 'Output head exceeds the cache budget'}
    weight = torch.empty(head.out_features, head.in_features)
    for start in range(0, head.out_features, 4096):
        end = min(start + 4096, head.out_features)
        weight[start:end].copy_(unpack(head.tensor, start, end))
    head._active_weight = weight
    return {'cached_bytes': required}


def load_saved_adapter(base, config, adapter):
    """Restore the portable adapter only against its exact immutable base."""
    from .public_baseline import sha256
    state = torch.load(adapter, map_location='cpu', weights_only=True)
    info = state['identity']
    if state.get('key_scheme') != 'full-hf-layer-indices' or sha256(base) != info['base_sha256']:
        raise ValueError('Adapter key scheme or base hash mismatch')
    model = load_quantized_qwen(base, config, info['layers'], info['rank'], info['alpha'])
    parameters = adapter_weights(model)
    if set(parameters) != set(state['weights']):
        raise ValueError('Adapter parameter names differ')
    with torch.no_grad():
        for name, parameter in parameters.items():
            if parameter.shape != state['weights'][name].shape:
                raise ValueError('Adapter shape mismatch: ' + name)
            parameter.copy_(state['weights'][name])
    return model.eval(), state


def merged_gguf(model, output, precision="f16"):
    import gguf
    output = Path(output)
    reader = model._gguf_reader
    if precision not in ("f16", "q8_0"):
        raise ValueError("Choose f16 or q8_0 adapted tensor precision")
    if output.resolve() == model._gguf_path:
        raise ValueError("Never overwrite the frozen base GGUF")
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = gguf.GGUFWriter(str(output), "qwen2", use_temp_file=True)
    for key, field in reader.fields.items():
        if key.startswith("GGUF.") or key == "general.architecture":
            continue
        writer.add_key_value(key, field.contents(), field.types[0], sub_type=field.types[-1] if len(field.types) > 1 else None)
    writer.add_string("xputty.adaptation", "CPU GGUF LoRA, frozen quantized base, merged adapted tensors")
    changed = {module.tensor.name: module for module in model.modules() if isinstance(module, PackedLinear) and module.rank}
    for tensor in reader.tensors:
        if tensor.name not in changed:
            writer.add_tensor(tensor.name, tensor.data, raw_dtype=tensor.tensor_type)
            continue
        module = changed[tensor.name]
        with torch.no_grad():
            weight = unpack(tensor) + (module.lora_B @ module.lora_A) * module.scale
        if precision == "f16":
            writer.add_tensor(tensor.name, weight.numpy().astype(np.float16))
        elif precision == "q8_0":
            packed = gguf.quants.quantize(weight.numpy(), gguf.GGMLQuantizationType.Q8_0)
            writer.add_tensor(tensor.name, packed, raw_dtype=gguf.GGMLQuantizationType.Q8_0)
        else:
            raise ValueError("Choose f16 or q8_0 adapted tensor precision")
    writer.write_header_to_file()
    writer.write_kv_data_to_file()
    writer.write_tensors_to_file(progress=True)
    writer.close()
    return {"changed_tensors": len(changed), "adapted_tensor_precision": precision,
            "note": "Unchanged tensors retain their original Q4_K/Q6_K/F32 types; this is a mixed-precision GGUF"}

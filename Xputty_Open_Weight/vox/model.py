"""Small, randomly initialized LLaMA-compatible decoder.

For experiment='dense', the weights and layer definitions match an ordinary
LLaMA-style decoder (pre RMSNorm, RoPE, SwiGLU, independent untied LM head).
Phi modes are deliberately research-only; they cannot be exported as if
standard llama.cpp's attention kernel implemented their behavior.
"""

from dataclasses import dataclass
from math import log, pi
import time
import torch
import torch.nn as nn
import torch.nn.functional as F
from .topology import PHI_CUSTOM, torch_mask


@dataclass
class ModelConfig:
    vocab_size: int = 4096
    dim: int = 256
    layers: int = 6
    heads: int = 4
    ffn_dim: int = 704
    context: int = 256
    norm_eps: float = 1e-5
    rope_theta: float = 10000.0
    experiment: str = "dense"  # dense, fibra, phi-pos, fibra-golden
    bos_token_id: int = 1
    eos_token_id: int = 2
    pad_token_id: int = 3

    def validate(self):
        if self.dim % self.heads or (self.dim // self.heads) % 2:
            raise ValueError("invalid rotary head size")
        if self.context > 2048 or self.context < 16:
            raise ValueError("context must be 16..2048")
        if self.layers < 1 or self.layers > 12 or self.dim > 512 or self.dim < 32:
            raise ValueError("R02 size limit")
        if self.vocab_size < 256 or self.vocab_size > 32000:
            raise ValueError("vocab out of range")
        if self.experiment not in ("dense", "fibra", "phi-pos", "fibra-golden"):
            raise ValueError("invalid experiment type")
        return self


class RMSNorm(nn.Module):
    def __init__(self, dim, eps):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(dim))
        self.eps = eps

    def forward(self, x):
        return (
            x
            * torch.rsqrt(x.float().pow(2).mean(-1, keepdim=True) + self.eps).type_as(x)
            * self.weight
        )


def rotate_half(x):
    n = x.shape[-1] // 2
    return torch.cat((-x[..., n:], x[..., :n]), dim=-1)


def apply_rope(q, k, offset=0, theta=10000.0):
    d = q.shape[-1]
    freqs = 1.0 / (
        theta ** (torch.arange(0, d, 2, device=q.device, dtype=torch.float32) / d)
    )
    ts = torch.arange(offset, offset + q.size(-2), device=q.device, dtype=torch.float32)
    angles = torch.outer(ts, freqs)
    emb = torch.cat((angles, angles), dim=-1)
    c = emb.cos()[None, None, :, :].to(q.dtype)
    s = emb.sin()[None, None, :, :].to(q.dtype)
    return q * c + rotate_half(q) * s, k * c + rotate_half(k) * s


class Attention(nn.Module):
    def __init__(self, c):
        super().__init__()
        d = c.dim
        self.q_proj = nn.Linear(d, d, bias=False)
        self.k_proj = nn.Linear(d, d, bias=False)
        self.v_proj = nn.Linear(d, d, bias=False)
        self.o_proj = nn.Linear(d, d, bias=False)
        self.c = c

    def forward(self, x, past=None):
        B, T, D = x.shape
        H = self.c.heads
        HD = D // H
        q = self.q_proj(x).view(B, T, H, HD).transpose(1, 2)
        k = self.k_proj(x).view(B, T, H, HD).transpose(1, 2)
        v = self.v_proj(x).view(B, T, H, HD).transpose(1, 2)
        offset = 0 if past is None else past[0].size(-2)
        q, k = apply_rope(q, k, offset, self.c.rope_theta)
        if past is not None:
            k = torch.cat((past[0], k), dim=-2)
            v = torch.cat((past[1], v), dim=-2)
        if self.c.experiment in ("fibra", "fibra-golden") and T > 1:
            if past is not None:
                raise ValueError(
                    "research FIBRA mask only supports full-sequence inference"
                )
            mask = torch_mask(
                T,
                x.device,
                angle=("golden" if self.c.experiment == "fibra-golden" else "custom"),
            )
            y = F.scaled_dot_product_attention(
                q, k, v, attn_mask=mask, is_causal=False, dropout_p=0.0
            )
        else:
            y = F.scaled_dot_product_attention(
                q, k, v, is_causal=(past is None and T > 1), dropout_p=0.0
            )
        y = y.transpose(1, 2).contiguous().view(B, T, D)
        return self.o_proj(y), (k, v)


class MLP(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.gate_proj = nn.Linear(c.dim, c.ffn_dim, bias=False)
        self.up_proj = nn.Linear(c.dim, c.ffn_dim, bias=False)
        self.down_proj = nn.Linear(c.ffn_dim, c.dim, bias=False)

    def forward(self, x):
        return self.down_proj(F.silu(self.gate_proj(x)) * self.up_proj(x))


class Block(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.input_layernorm = RMSNorm(c.dim, c.norm_eps)
        self.self_attn = Attention(c)
        self.post_attention_layernorm = RMSNorm(c.dim, c.norm_eps)
        self.mlp = MLP(c)

    def forward(self, x, past=None):
        y, kv = self.self_attn(self.input_layernorm(x), past)
        x = x + y
        x = x + self.mlp(self.post_attention_layernorm(x))
        return x, kv


class TinyLlama(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.config = config.validate()
        c = config
        self.embed_tokens = nn.Embedding(c.vocab_size, c.dim)
        self.layers = nn.ModuleList([Block(c) for _ in range(c.layers)])
        self.norm = RMSNorm(c.dim, c.norm_eps)
        self.lm_head = nn.Linear(c.dim, c.vocab_size, bias=False)
        if c.experiment == "phi-pos":
            self.phi_projection = nn.Linear(3, c.dim, bias=False)
        self.apply(self._init)

    @staticmethod
    def _init(m):
        if isinstance(m, (nn.Linear, nn.Embedding)):
            nn.init.normal_(m.weight, mean=0, std=0.02)

    def forward(self, ids, targets=None, past=None, return_cache=False):
        if ids.ndim != 2:
            raise ValueError("input token ids must be [batch, seq]")
        B, T = ids.shape
        prefix = 0 if past is None else past[0][0].size(-2)
        if T + prefix > self.config.context:
            raise ValueError("context length exceeded")
        x = self.embed_tokens(ids)
        if self.config.experiment == "phi-pos":
            idx = torch.arange(
                prefix + 1, prefix + T + 1, device=ids.device, dtype=torch.float32
            )
            angle = 2 * pi / (PHI_CUSTOM**2)
            vec = torch.stack(
                (
                    torch.sin(idx * angle),
                    torch.cos(idx * angle),
                    torch.log1p(idx) / log(1 + self.config.context),
                ),
                dim=-1,
            )
            x = x + self.phi_projection(vec)[None, :, :]
        cache = []
        for i, layer in enumerate(self.layers):
            if (
                getattr(self, "gradient_checkpointing", False)
                and self.training
                and torch.is_grad_enabled()
            ):
                if past is not None or return_cache:
                    raise ValueError(
                        "Activation checkpointing training cannot use a KV cache"
                    )
                from torch.utils.checkpoint import checkpoint

                x = checkpoint(
                    lambda h, block=layer: block(h)[0], x, use_reentrant=False
                )
            else:
                x, kv = layer(x, None if past is None else past[i])
                cache.append(kv)
        logits = self.lm_head(self.norm(x))
        loss = None
        if targets is not None:
            loss = F.cross_entropy(
                logits.float().reshape(-1, self.config.vocab_size),
                targets.reshape(-1),
                ignore_index=-100,
            )
        return (logits, loss, cache) if return_cache else (logits, loss)

    def n_parameters(self):
        return sum(p.numel() for p in self.parameters())


@torch.inference_mode()
def generate(
    model,
    ids,
    max_new_tokens=32,
    temperature=0.85,
    top_k=30,
    stop_id=None,
    seed=739,
    metrics=None,
):
    # Full-window fallback for experimental masking; KV-cached incremental decode for standard model.
    if seed is not None:
        torch.manual_seed(seed)
    max_new_tokens = min(int(max_new_tokens), model.config.context - 1)
    if max_new_tokens < 1:
        raise ValueError("max_new_tokens must be >=1")
    model.eval()
    ids = ids[-max(1, model.config.context - max_new_tokens) :]
    inp = torch.tensor(ids, dtype=torch.long).unsqueeze(0)
    begin = time.perf_counter()
    cache = None
    out = list(ids)
    for step in range(max_new_tokens):
        if model.config.experiment in ("fibra", "fibra-golden"):
            inp = torch.tensor(out[-model.config.context :], dtype=torch.long)[None, :]
            logits, _ = model(inp)
        else:
            logits, _, cache = model(inp, past=cache, return_cache=True)
        l = logits[0, -1].float() / max(1e-5, temperature)
        if top_k and top_k < l.numel():
            values, _ = torch.topk(l, int(top_k))
            l[l < values[-1]] = -float("inf")
        tok = int(torch.multinomial(torch.softmax(l, dim=-1), 1).item())
        out.append(tok)
        if step == 0 and metrics is not None:
            metrics["first_token_ms"] = (time.perf_counter() - begin) * 1000
        if stop_id is not None and (
            tok == stop_id or isinstance(stop_id, (set, tuple, list)) and tok in stop_id
        ):
            break
        if model.config.experiment in ("fibra", "fibra-golden"):
            continue
        # For standard model use cache until max context, then re-prefill trimmed window.
        if len(out) >= model.config.context:
            cache = None
            inp = torch.tensor(out[-model.config.context :], dtype=torch.long)[None, :]
        else:
            inp = torch.tensor([[tok]], dtype=torch.long)
    if metrics is not None:
        metrics["total_generation_ms"] = (time.perf_counter() - begin) * 1000
        metrics["output_tokens"] = len(out) - len(ids)
    return out[len(ids) :]

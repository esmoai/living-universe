from types import SimpleNamespace

import gguf
import numpy as np
import torch
import pytest

from vox.gguf_lora import PackedLinear, merged_gguf, cache_active_layers


@pytest.mark.parametrize('cache', [False, True])
def test_packed_frozen_projection_and_lora_gradients_match_dense(cache):
    torch.manual_seed(739)
    weight = torch.randn(7, 5)
    record = SimpleNamespace(shape=np.array([5, 7]), data=weight.numpy(), tensor_type=gguf.GGMLQuantizationType.F32)
    module = PackedLinear(record, rank=4, alpha=8)
    if cache:
        assert cache_active_layers(module)['cached_bytes'] == weight.numel() * 4
    with torch.no_grad():
        module.lora_B.normal_(std=0.1)
    x = torch.randn(2, 3, 5, requires_grad=True)
    expected_x = x.detach().clone().requires_grad_()
    a = module.lora_A.detach().clone().requires_grad_()
    b = module.lora_B.detach().clone().requires_grad_()
    actual = module(x)
    expected = torch.nn.functional.linear(expected_x, weight) + torch.nn.functional.linear(torch.nn.functional.linear(expected_x, a), b) * 2
    actual.square().mean().backward()
    expected.square().mean().backward()
    assert torch.allclose(actual, expected, atol=1e-6)
    assert torch.allclose(x.grad, expected_x.grad, atol=1e-6)
    assert torch.allclose(module.lora_A.grad, a.grad, atol=1e-6)
    assert torch.allclose(module.lora_B.grad, b.grad, atol=1e-6)


def test_chunked_vocabulary_projection_backward_matches_dense():
    torch.manual_seed(739)
    weight = torch.randn(16385, 4)
    record = SimpleNamespace(shape=np.array([4, 16385]), data=weight.numpy(), tensor_type=gguf.GGMLQuantizationType.F32)
    module = PackedLinear(record)
    x = torch.randn(1, 2, 4, requires_grad=True)
    reference = x.detach().clone().requires_grad_()
    output = module(x)
    expected = torch.nn.functional.linear(reference, weight)
    output.sum().backward()
    expected.sum().backward()
    assert torch.allclose(output, expected, atol=1e-5)
    assert torch.allclose(x.grad, reference.grad, atol=1e-3)


def test_layerwise_frozen_prefix_matches_full_causal_forward():
    from transformers import Qwen2Config, Qwen2Model
    torch.manual_seed(739)
    config = Qwen2Config(vocab_size=32, hidden_size=16, intermediate_size=32,
                        num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=1)
    config._attn_implementation = 'sdpa'
    model = Qwen2Model(config).eval()
    ids = torch.tensor([[1, 4, 8, 12, 6]])
    with torch.no_grad():
        expected = model(input_ids=ids, use_cache=False).last_hidden_state
        h = model.embed_tokens(ids)
        positions = torch.arange(ids.shape[1]).unsqueeze(0)
        rotary = model.rotary_emb(h, positions)
        for layer in model.layers:
            h = layer(h, position_ids=positions, position_embeddings=rotary, use_cache=False)
        assert torch.allclose(model.norm(h), expected, atol=1e-6)
        # Future-token changes must not affect the first contextual position.
        changed = model(input_ids=torch.tensor([[1, 9, 2, 3, 5]]), use_cache=False).last_hidden_state
        assert torch.allclose(changed[:, :1], expected[:, :1], atol=1e-6)


def test_merged_gguf_contains_adapter_updates_and_preserves_base(tmp_path):
    source = tmp_path / 'base.gguf'
    weight = np.arange(32 * 8, dtype=np.float32).reshape(8, 32) / 256
    writer = gguf.GGUFWriter(str(source), 'qwen2')
    writer.add_name('test source')
    writer.add_tensor('blk.0.attn_q.weight', weight)
    writer.add_tensor('output_norm.weight', np.ones(8, dtype=np.float32))
    writer.write_header_to_file(); writer.write_kv_data_to_file(); writer.write_tensors_to_file(); writer.close()
    original = source.read_bytes()
    reader = gguf.GGUFReader(str(source))
    module = PackedLinear(reader.tensors[0], rank=4, alpha=4)
    with torch.no_grad():
        module.lora_A.fill_(0.1); module.lora_B.fill_(0.2)
    model = torch.nn.Sequential(module)
    model._gguf_reader, model._gguf_path = reader, source.resolve()
    out = tmp_path / 'merged.gguf'
    report = merged_gguf(model, out, 'q8_0')
    merged = gguf.GGUFReader(str(out))
    updated = gguf.quants.dequantize(merged.tensors[0].data, merged.tensors[0].tensor_type)
    assert np.allclose(updated, weight + 0.08, atol=0.01)
    assert report['changed_tensors'] == 1
    assert source.read_bytes() == original

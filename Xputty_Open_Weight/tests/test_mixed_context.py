import json
from dataclasses import asdict

import pytest
import torch

from vox.model import ModelConfig, TinyLlama
from vox.presets import (
    resolve,
    policy_for,
    parameter_count,
    window_for_step,
    learning_rate,
)
from vox.plain_text import build
from vox.tokenizer import train as tokenize
from vox.data import prepare
from vox.train import train
from vox.evaluate import evaluate


def test_actual_48m_shape_and_policy_validation():
    cfg = resolve({"preset": "research-48m-v1"})
    with torch.device("meta"):
        model = TinyLlama(
            ModelConfig(
                vocab_size=cfg["vocab_size"],
                dim=cfg["dim"],
                layers=cfg["layers"],
                heads=cfg["heads"],
                ffn_dim=cfg["ffn_dim"],
                context=cfg["max_context"],
            )
        )
    assert model.n_parameters() == parameter_count(cfg) == 48116224
    assert resolve({})["preset"] == "tiny-1m-v1"
    for bad in [
        {"windows": [512, 4096], "window_weights": [1, 1]},
        {"window_weights": [1, 1]},
        {"ramp_updates": -1},
        {"lr": float("nan")},
        {"min_lr": 0.9},
    ]:
        with pytest.raises(ValueError):
            resolve({"preset": "research-48m-v1", "training_settings": bad})


def test_deterministic_curriculum_and_stable_lr_horizon():
    cfg = resolve({"preset": "research-48m-v1"})
    policy = policy_for(cfg)
    assert all(window_for_step(policy, i) == 256 for i in range(250))
    assert max(window_for_step(policy, i) for i in range(250, 500)) == 512
    assert max(window_for_step(policy, i) for i in range(500, 750)) == 1024
    assert set(window_for_step(policy, i) for i in range(750, 1500)) == {
        256,
        512,
        1024,
        2048,
    }
    assert learning_rate(policy, 0, cfg["lr"]) < cfg["lr"]
    assert learning_rate(
        policy, policy["schedule_updates"], cfg["lr"]
    ) == pytest.approx(cfg["min_lr"])


def test_mixed_training_resumes_exactly_and_evaluates_windows(tmp_path):
    paths = []
    for i in range(4):
        p = tmp_path / f"book{i}.txt"
        p.write_text(
            (
                f"Work {i}: the travellers discussed a curious discovery in the quiet library.\n"
                * 200
            ),
            encoding="utf-8",
        )
        paths.append(p)
    data = tmp_path / "data"
    build(paths, data)
    tokenize(data, 512)
    prepare(data)
    cfg = resolve(
        {
            "preset": "research-48m-v1",
            "training_settings": {
                "windows": [128, 256, 512, 1024],
                "window_weights": [1, 1, 1, 1],
                "ramp_updates": 0,
                "warmup_updates": 2,
                "schedule_updates": 20,
                "tokens_per_update": 256,
            },
        }
    )
    policy = policy_for(cfg)
    opts = dict(
        dim=32,
        layers=1,
        heads=2,
        ffn_dim=64,
        seq_len=128,
        max_context=1024,
        batch=1,
        training_policy=policy,
        lr=cfg["lr"],
        save_every=1,
        log_interval=1,
    )
    first = tmp_path / "resumed"
    full = tmp_path / "full"
    train(data, first, steps=2, **opts)
    resumed = train(data, first, steps=4, resume=True, **opts)
    expected = train(data, full, steps=4, **opts)
    assert resumed["context_updates"] == {"128": 1, "256": 1, "512": 1, "1024": 1}
    assert resumed["cumulative_tokens_processed"] == 256 + 256 + 512 + 1024
    assert (
        resumed["cumulative_tokens_processed"]
        == expected["cumulative_tokens_processed"]
    )
    a = torch.load(first / "checkpoint.pt", weights_only=True)
    b = torch.load(full / "checkpoint.pt", weights_only=True)
    assert all(torch.equal(a["weights"][k], b["weights"][k]) for k in a["weights"])
    assert a["config"]["context"] == 1024
    assert json.loads((first / "progress.json").read_text())["context_tokens"] == 1024
    assert (
        evaluate(data, first / "checkpoint.pt", samples=1, context=128)[
            "context_tokens"
        ]
        == 128
    )
    with pytest.raises(ValueError, match="policy differs"):
        train(
            data,
            first,
            steps=5,
            resume=True,
            **{**opts, "training_policy": {**policy, "ramp_updates": 1}},
        )


def test_activation_checkpointing_preserves_gradients():
    config = ModelConfig(
        vocab_size=256, dim=32, layers=2, heads=2, ffn_dim=64, context=128
    )
    torch.manual_seed(12)
    a = TinyLlama(config)
    b = TinyLlama(config)
    b.load_state_dict(a.state_dict())
    b.gradient_checkpointing = True
    x = torch.tensor([[7, 9, 11, 13, 15]])
    y = x.roll(-1, 1)
    a(x, y)[1].backward()
    b(x, y)[1].backward()
    for p, q in zip(a.parameters(), b.parameters()):
        assert torch.allclose(p.grad, q.grad, atol=1e-7, rtol=1e-5)

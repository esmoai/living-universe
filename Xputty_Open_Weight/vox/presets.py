"""Versioned experiment presets. Existing projects retain their 1.6M architecture."""

import copy
import hashlib
import json
import math
import random

PRESETS = {
    "tiny-1m-v1": dict(
        label="1.6M · quick pipeline test",
        vocab_size=4096,
        dim=128,
        layers=3,
        heads=4,
        ffn_dim=320,
        max_context=512,
        windows=[512],
        window_weights=[1],
        ramp_updates=0,
        lr=0.0005,
        min_lr=0.0005,
        warmup_updates=0,
        schedule_updates=10000,
        micro_batch=2,
        tokens_per_update=1024,
        activation_checkpointing=False,
        eval_samples=8,
        save_every=25,
    ),
    "research-48m-v1": dict(
        label="48M · mixed-context research",
        vocab_size=8192,
        dim=512,
        layers=12,
        heads=8,
        ffn_dim=1472,
        max_context=2048,
        windows=[256, 512, 1024, 2048],
        window_weights=[4, 3, 2, 1],
        ramp_updates=1000,
        lr=0.0003,
        min_lr=0.00003,
        warmup_updates=100,
        schedule_updates=10000,
        micro_batch=1,
        tokens_per_update=512,
        activation_checkpointing=True,
        eval_samples=4,
        save_every=50,
    ),
}


def resolve(state):
    name = state.get("preset", "tiny-1m-v1")
    if name not in PRESETS:
        raise ValueError("Unknown model preset")
    config = copy.deepcopy(PRESETS[name])
    overrides = state.get("training_settings", {})
    allowed = {
        "windows",
        "window_weights",
        "ramp_updates",
        "warmup_updates",
        "schedule_updates",
        "lr",
        "min_lr",
        "tokens_per_update",
    }
    if not isinstance(overrides, dict) or set(overrides) - allowed:
        raise ValueError("Unsupported training setting")
    config.update(overrides)
    lengths, weights = config["windows"], config["window_weights"]
    if (
        not isinstance(lengths, list)
        or not isinstance(weights, list)
        or not 1 <= len(lengths) <= 4
        or len(lengths) != len(weights)
    ):
        raise ValueError("Choose one to four context windows with matching weights")
    if any(
        type(n) is not int
        or n not in (128, 256, 512, 1024, 2048)
        or n > config["max_context"]
        for n in lengths
    ) or lengths != sorted(set(lengths)):
        raise ValueError(
            "Context windows must be unique, increasing, and within the preset maximum"
        )
    if any(
        not isinstance(w, (int, float))
        or isinstance(w, bool)
        or not math.isfinite(w)
        or not 0 < w <= 100
        for w in weights
    ):
        raise ValueError("Window weights must be positive and at most 100")
    for field in ("ramp_updates", "warmup_updates"):
        if type(config[field]) is not int or not 0 <= config[field] <= 100000:
            raise ValueError("Invalid warmup or context ramp")
    if (
        type(config["schedule_updates"]) is not int
        or not 1 <= config["schedule_updates"] <= 1000000
        or config["warmup_updates"] >= config["schedule_updates"]
    ):
        raise ValueError("Learning-rate horizon must exceed warmup")
    if (
        any(
            not isinstance(config[k], (float, int))
            or isinstance(config[k], bool)
            or not math.isfinite(config[k])
            for k in ("lr", "min_lr")
        )
        or not 0 < config["min_lr"] <= config["lr"] <= 0.01
    ):
        raise ValueError("Invalid learning-rate range")
    if (
        type(config["tokens_per_update"]) is not int
        or not 128 <= config["tokens_per_update"] <= 8192
    ):
        raise ValueError("Token budget must be 128–8192 per update")
    config["preset"] = name
    return config


def policy_for(config):
    policy = {
        k: copy.deepcopy(config[k])
        for k in (
            "windows",
            "window_weights",
            "ramp_updates",
            "warmup_updates",
            "schedule_updates",
            "min_lr",
            "tokens_per_update",
            "activation_checkpointing",
        )
    }
    policy["peak_lr"] = config["lr"]
    return policy


def digest(policy):
    return hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest()


def window_for_step(policy, step, seed=739):
    lengths = policy["windows"]
    ramp = policy.get("ramp_updates", 0)
    if not ramp and step < len(lengths):
        return lengths[step]
    # Unlock progressively; short windows remain in the mixture after the ramp.
    unlocked = (
        len(lengths) if not ramp else min(len(lengths), 1 + step * len(lengths) // ramp)
    )
    return random.Random(seed * 1000003 + step).choices(
        lengths[:unlocked], weights=policy["window_weights"][:unlocked], k=1
    )[0]


def learning_rate(policy, step, peak):
    warmup, horizon = policy["warmup_updates"], policy["schedule_updates"]
    if step < warmup:
        return peak * (step + 1) / max(1, warmup)
    progress = min(1.0, (step - warmup) / max(1, horizon - warmup))
    return policy["min_lr"] + 0.5 * (peak - policy["min_lr"]) * (
        1 + math.cos(math.pi * progress)
    )


def parameter_count(config):
    d = config["dim"]
    return (
        2 * config["vocab_size"] * d
        + config["layers"] * (4 * d * d + 3 * d * config["ffn_dim"] + 2 * d)
        + d
    )

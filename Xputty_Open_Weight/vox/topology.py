"""Deterministic Phi-Pi experimental causal selection mask.

This builds a DENSE BOOLEAN MASK despite few active edges. It is for functional
comparison, not CPU acceleration. The R01 CSR topology is the reference for a
future kernel that actually skips inactive Q/K comparisons.
"""

from functools import lru_cache
from math import sqrt, sin, cos, pi

PHI_CUSTOM = 1.618314159265358979323846
GOLDEN = (1 + sqrt(5)) / 2
OFFSETS = (13, 21, 34, 55, 89)


def point(n, angle=None):
    if angle is None:
        angle = 2 * pi / (PHI_CUSTOM * PHI_CUSTOM)
    r = sqrt(n)
    return (r * cos(n * angle), r * sin(n * angle))


@lru_cache(maxsize=32)
def mask_indices(count, mode="fibra", angle="custom", local=16, geometric=8, radius=55):
    if count > 2048:
        raise ValueError("R02 experimental mask intentionally limited to 2048 tokens")
    if mode not in ("fibra", "dense", "fibonacci", "local"):
        raise ValueError(mode)
    a = 2 * pi / ((GOLDEN if angle == "golden" else PHI_CUSTOM) ** 2)
    coords = [point(i + 1, a) for i in range(count)]
    out = []
    for i in range(count):
        if mode == "dense":
            allowed = list(range(i + 1))
        else:
            allowed = {i}
            if mode in ("fibra", "local"):
                allowed.update(range(max(0, i - local), i))
            if mode in ("fibra", "fibonacci"):
                allowed.update(i - off for off in OFFSETS if i >= off)
            if mode == "fibra":
                x, y = coords[i]
                matches = sorted(
                    (
                        ((x - a) ** 2 + (y - b) ** 2, j)
                        for j, (a, b) in enumerate(coords[:i])
                        if (x - a) ** 2 + (y - b) ** 2 <= radius**2
                    ),
                    key=lambda it: it[0],
                )
                allowed.update(j for _, j in matches[:geometric])
            allowed = sorted(allowed)
        out.append(tuple(allowed))
    return tuple(out)


def torch_mask(count, device, angle="custom", mode="fibra"):
    import torch

    rows = mask_indices(count, mode=mode, angle=angle)
    mask = torch.zeros((count, count), device=device, dtype=torch.bool)
    for i, cols in enumerate(rows):
        mask[i, list(cols)] = True
    return mask


def stats(count=128, mode="fibra", angle="custom"):
    rows = mask_indices(count, mode=mode, angle=angle)
    allowed = sum(len(x) for x in rows)
    dense = count * (count + 1) // 2
    return dict(
        count=count,
        mode=mode,
        angle=angle,
        eligible_edges=allowed,
        dense_edges=dense,
        fraction=round(allowed / dense, 5),
    )

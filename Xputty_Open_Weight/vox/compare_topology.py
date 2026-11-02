"""Reproducible topology ablation report, not a language-quality benchmark."""

import argparse
import json
from decimal import Decimal, localcontext
from pathlib import Path
from .topology import mask_indices


def compare(sizes=(128, 512, 2048)):
    result = {
        "schema": "vox-topology-comparison/1",
        "scope": "Eligible causal edges only; no claim of neural quality or inference acceleration.",
        "custom_constant_literal": "1.618314159265358979323846",
        "runtime_precision": "Python float64; digits beyond float64 precision are not retained",
        "controls": {
            "local": 16,
            "geometric": 8,
            "radius": 55,
            "coordinate_scale": 1,
            "fibonacci_offsets": [13, 21, 34, 55, 89],
        },
        "sizes": [],
    }
    with localcontext() as ctx:
        ctx.prec = 50
        phi = (1 + Decimal(5).sqrt()) / 2
        custom = Decimal(result["custom_constant_literal"])
        result["golden_angle_degrees"] = str(360 / (phi * phi))
        result["custom_angle_degrees"] = str(360 / (custom * custom))
    for n in sizes:
        graphs = {
            name: mask_indices(n, mode=mode, angle=angle)
            for name, mode, angle in [
                ("custom", "fibra", "custom"),
                ("golden", "fibra", "golden"),
                ("local", "local", "custom"),
                ("fibonacci", "fibonacci", "custom"),
            ]
        }
        for rows in graphs.values():
            assert all(all(0 <= key <= i for key in row) for i, row in enumerate(rows))
        custom, golden = graphs["custom"], graphs["golden"]
        result["sizes"].append(
            {
                "tokens": n,
                "eligible_edges": {
                    name: sum(map(len, rows)) for name, rows in graphs.items()
                },
                "custom_vs_golden_rows_changed": sum(
                    a != b for a, b in zip(custom, golden)
                ),
                "custom_vs_golden_symmetric_edge_difference": sum(
                    len(set(a) ^ set(b)) for a, b in zip(custom, golden)
                ),
            }
        )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = compare()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sizes": len(result["sizes"]),
                "scope": result["scope"],
            }
        )
    )

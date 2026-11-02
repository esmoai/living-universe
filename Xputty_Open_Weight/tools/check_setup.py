"""Fast standard-library preflight. A listening server is not proof of installed tools."""

import importlib.util, sys


def check():
    required = [
        "torch",
        "numpy",
        "sentencepiece",
        "safetensors",
        "psutil",
        "transformers",
        "certifi",
    ]
    missing = [name for name in required if importlib.util.find_spec(name) is None]
    python_ok = (3, 10) <= sys.version_info[:2] < (3, 13)
    return {
        "ready": not missing and python_ok,
        "python": sys.version.split()[0],
        "supported_python": python_ok,
        "missing": missing,
    }


if __name__ == "__main__":
    import json

    report = check()
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["ready"] else 1)

"""Inspect installed ingestion dependencies and local models without processing user files."""

import importlib.util
import json
import urllib.request
from pathlib import Path
from .media_processing import ROOT, config


def check():
    cfg = config()
    checks = {}
    for package in [
        "av",
        "PIL",
        "pillow_heif",
        "pypdf",
        "pypdfium2",
        "rapidocr_onnxruntime",
        "vosk",
        "striprtf",
    ]:
        checks[package] = importlib.util.find_spec(package) is not None
    checks["speech_model"] = (
        (ROOT / cfg["vosk_model"]).resolve() / "am/final.mdl"
    ).is_file()
    checks["tika_jar"] = (ROOT / cfg["tika_jar"]).is_file()
    checks["java"] = Path(cfg["java"]).is_file()
    try:
        body = json.dumps({"model": cfg["vision_model"]}).encode()
        request = urllib.request.Request(
            cfg["vision_url"] + "/api/show",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        info = json.load(urllib.request.urlopen(request, timeout=5))
        checks["local_vision"] = "vision" in info.get("capabilities", [])
    except Exception as error:
        checks["local_vision"] = False
        checks["vision_error"] = str(error)
    ready = all(value is True for key, value in checks.items() if key != "vision_error")
    return {
        "ready": ready,
        "checks": checks,
        "vision_model": cfg["vision_model"],
        "local_only": True,
    }


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["ready"] else 1)

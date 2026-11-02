"""Convert a local public-model export with a checksum-pinned llama.cpp toolchain."""
import argparse
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vox.public_baseline import download, sha256, write_json

REVISION = "1b6935b227b9f9aa89deea8016c0e208f547446f"
ARCHIVE_SHA = "b335a3daef89ad2bdb6b969057ae5ac575a2cb39be98c06fa5b6840da9e23626"


def convert(folder, cache, precision="q8_0"):
    folder, cache = Path(folder).resolve(), Path(cache).resolve()
    if precision not in ("f16", "q8_0"):
        raise ValueError("Choose f16 or q8_0")
    tool = cache / "llama-tools"
    archive = download(f"https://codeload.github.com/ggml-org/llama.cpp/zip/{REVISION}", tool / "tooling.zip", ARCHIVE_SHA)
    with zipfile.ZipFile(archive) as z:
        for member in z.namelist():
            rel = Path(*Path(member).parts[1:])
            if not rel.parts or (rel.parts[0] not in ("conversion", "gguf-py", "LICENSE", "convert_hf_to_gguf.py")):
                continue
            if member.endswith("/"):
                continue
            target = (tool / rel).resolve()
            if not target.is_relative_to(tool):
                raise ValueError("Unsafe converter archive member")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(member))
    output = folder / ("model-" + precision + ".gguf")
    environment = {**os.environ, "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2"}
    subprocess.run([sys.executable, str(tool / "convert_hf_to_gguf.py"), str(folder), "--outfile", str(output), "--outtype", precision], env=environment, check=True)
    with output.open("rb") as stream:
        if stream.read(4) != b"GGUF":
            raise ValueError("Converter did not produce GGUF")
    result = {"converter_repository": "ggml-org/llama.cpp", "converter_revision": REVISION,
              "converter_archive_sha256": ARCHIVE_SHA, "input_weights_sha256": sha256(folder / "model.safetensors"),
              "precision": precision, "output_sha256": sha256(output), "bytes": output.stat().st_size,
              "verification": "Conversion only. Native generation and quality checks are separate."}
    write_json(folder / ("conversion-" + precision + ".json"), result)
    model_file = f"FROM ./{output.name}\nPARAMETER num_ctx 2048\nPARAMETER temperature 0.6\n"
    report_path = folder / "export_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    if report.get("persona_profiles"):
        persona = next(iter(report["persona_profiles"].values()))
        system = report["persona_rules"] + f" Your name is {persona['name']}; you are {persona['traits']}."
        model_file += "SYSTEM " + json.dumps(system) + "\n"
    (folder / "Modelfile").write_text(model_file, encoding="utf-8")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", required=True, type=Path)
    p.add_argument("--cache", type=Path, default=Path("storage/public-source-cache"))
    p.add_argument("--precision", choices=["f16", "q8_0"], default="q8_0")
    a = p.parse_args()
    print(json.dumps(convert(a.model, a.cache, a.precision), indent=2))

"""Repairable installation using a supported interpreter; preserve old environments."""

import datetime, json, os, subprocess, sys, venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def supported(version):
    return (3, 10) <= tuple(version[:2]) < (3, 13)


def install():
    if not supported(sys.version_info):
        raise SystemExit(
            "Setup needs Python 3.11 (supported: 3.10–3.12). Current: "
            + sys.version.split()[0]
            + ". In Codespaces, pull the latest branch and rebuild its container."
        )
    folder = ROOT / ".venv"
    python = folder / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    existing = None
    if python.is_file():
        try:
            existing = json.loads(
                subprocess.check_output(
                    [
                        str(python),
                        "-c",
                        "import sys,json;print(json.dumps(list(sys.version_info[:2])))",
                    ],
                    text=True,
                    timeout=15,
                )
            )
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    if folder.exists() and existing != list(sys.version_info[:2]):
        backup = ROOT / (
            ".venv-backup-"
            + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        )
        folder.rename(backup)
        print("Preserved old environment as " + backup.name, flush=True)
    venv.EnvBuilder(with_pip=True).create(folder)
    commands = [[str(python), "-m", "pip", "install", "--upgrade", "pip", "certifi"]]
    if sys.platform != "darwin":
        commands.append(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "torch>=2.6,<3",
                "--index-url",
                "https://download.pytorch.org/whl/cpu",
            ]
        )
    commands.extend(
        [
            [str(python), "-m", "pip", "install", "-r", "requirements.txt"],
            [str(python), "-m", "pip", "check"],
            [
                str(python),
                "-c",
                'import torch,numpy,sentencepiece,safetensors,psutil,transformers,certifi; torch.from_numpy(numpy.zeros(1)); print("Training dependencies verified")',
            ],
            [str(python), "tools/fetch_assets.py"],
        ]
    )
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)
    print("Setup complete. Run start.sh or START-WINDOWS.cmd.", flush=True)


if __name__ == "__main__":
    install()

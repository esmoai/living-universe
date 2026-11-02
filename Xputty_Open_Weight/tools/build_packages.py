"""Create source/OS/deployment ZIPs from a strict allowlist. Never ships projects."""

import argparse, hashlib, json, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = {"vox", "web", "tests", "tools", "deploy", "ci", "docs"}
FILES = {
    "server.py",
    "worker.py",
    "audition.py",
    "export_chat.py",
    "materials.py",
    "web_capture.py",
    "launch.py",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-public.txt",
    "ingestion-config.json",
    "assets-manifest.json",
    "Caddyfile",
    "Dockerfile",
    "Dockerfile.gpu",
    "compose.yaml",
    "compose.gpu.yaml",
    "README.md",
    "THIRD-PARTY-NOTICES.txt",
    "INSTALL-WINDOWS.cmd",
    "START-WINDOWS.cmd",
    "START-MAC.command",
    "install.sh",
    "start.sh",
    ".gitignore",
    ".dockerignore",
    "VERSION",
    "LICENSE",
    "VERIFICATION.json",
}


def sources():
    candidates = [ROOT / name for name in FILES]
    for folder in FOLDERS:
        candidates.extend((ROOT / folder).rglob("*"))
    for file in sorted(candidates):
        rel = file.relative_to(ROOT)
        if not file.is_file() or "__pycache__" in rel.parts:
            continue
        if (
            rel.parts[0] in FOLDERS
            and file.suffix
            in {
                ".py",
                ".js",
                ".css",
                ".html",
                ".md",
                ".yml",
                ".yaml",
                ".json",
                ".service",
                ".sh",
                ".txt",
            }
            or rel.as_posix() in FILES
        ):
            yield file, rel


def build(kind, assets=None):
    version = (ROOT / "VERSION").read_text().strip()
    out = ROOT / "dist" / f"Xputty-Open-Weight-{version}-{kind}.zip"
    out.parent.mkdir(exist_ok=True)
    entries = list(sources())
    if assets and kind != "shared-hosting":
        asset_root = Path(assets).resolve()
        for folder in [
            "models/vosk-model-small-en-us-0.15",
            "tools/tika-app-3.2.3.jar",
        ]:
            path = asset_root / folder
            if not path.exists():
                raise FileNotFoundError(path)
            for file in [path] if path.is_file() else sorted(path.rglob("*")):
                if file.is_file():
                    entries.append((file, file.relative_to(asset_root)))
    if kind == "shared-hosting":
        entries = [(p, Path(p.name)) for p, rel in entries if rel.parts[0] == "web"]
    manifest = {}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for file, rel in entries:
            name = (
                rel.as_posix()
                if kind == "shared-hosting"
                else "Xputty_Open_Weight/" + rel.as_posix()
            )
            data = file.read_bytes()
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (
                0o100755 if file.suffix in {".sh", ".command"} else 0o100644
            ) << 16
            z.writestr(info, data)
            manifest[name] = hashlib.sha256(data).hexdigest()
        z.writestr("FILE-MANIFEST.sha256.json", json.dumps(manifest, indent=2))
    return {
        "path": str(out),
        "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "bytes": out.stat().st_size,
        "files": len(manifest),
        "assets_bundled": bool(assets) and kind != "shared-hosting",
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        "--kind",
        choices=[
            "windows",
            "macos",
            "linux",
            "deployment",
            "shared-hosting",
            "source",
            "all",
        ],
        default="all",
    )
    p.add_argument("--assets", type=Path)
    a = p.parse_args()
    kinds = (
        ["windows", "macos", "linux", "deployment", "shared-hosting"]
        if a.kind == "all"
        else [a.kind]
    )
    records = [build(kind, a.assets) for kind in kinds]
    (ROOT / "dist/packages.json").write_text(json.dumps(records, indent=2))
    print(json.dumps(records, indent=2))

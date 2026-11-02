"""Download checksum-pinned media assets for release packaging or a source install."""

import hashlib, json, shutil, ssl, tempfile, urllib.request, zipfile
from pathlib import Path
import certifi

ROOT = Path(__file__).resolve().parents[1]


def fetch():
    context = ssl.create_default_context(cafile=certifi.where())
    for asset in json.loads((ROOT / "assets-manifest.json").read_text())["assets"]:
        target = ROOT / asset["destination"]
        if (
            target.is_file()
            and hashlib.sha256(target.read_bytes()).hexdigest() == asset["sha256"]
        ):
            continue
        if target.is_dir() and (target / "am/final.mdl").is_file():
            continue
        with tempfile.TemporaryDirectory() as work:
            download = Path(work) / "download"
            digest = hashlib.sha256()
            with (
                urllib.request.urlopen(
                    asset["url"], context=context, timeout=120
                ) as response,
                download.open("wb") as stream,
            ):
                while chunk := response.read(1024**2):
                    stream.write(chunk)
                    digest.update(chunk)
            if digest.hexdigest() != asset["sha256"]:
                raise ValueError("Asset checksum mismatch: " + asset["name"])
            if asset.get("archive"):
                with zipfile.ZipFile(download) as z:
                    for member in z.infolist():
                        path = (ROOT / "models" / member.filename).resolve()
                        if (
                            not path.is_relative_to((ROOT / "models").resolve())
                            or member.file_size > 200 * 1024**2
                        ):
                            raise ValueError("Invalid asset archive member")
                    z.extractall(ROOT / "models")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(download, target)
        print("Installed verified asset:", asset["name"])


if __name__ == "__main__":
    fetch()

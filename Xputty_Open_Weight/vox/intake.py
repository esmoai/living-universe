"""Local, lossless format adapters with working ASR, OCR, vision and document processing.

Original bytes are always retained. Derived text is a distinct asset, never
silently substituted for the source document or recording.
"""

import argparse
import csv
import io
import json
import re
import tempfile
import shutil
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from .upod import (
    _json,
    sha256_bytes,
    sha256_file,
    open_upod,
    stage_upod,
    import_capture,
    MAX_MEMBER_BYTES,
    MAX_TRANSCRIPT_BYTES,
)

TEXT = {".txt", ".md", ".text", ".log"}
STRUCTURED = {".json", ".jsonl", ".csv", ".tsv"}
SUBTITLES = {".srt", ".vtt"}
AUDIO = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".aiff", ".aif"}
VIDEO = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"}
IMAGES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic"}
DOCUMENTS = {".docx", ".pdf", ".doc", ".rtf", ".odt"}
SUPPORTED = (
    TEXT | STRUCTURED | SUBTITLES | AUDIO | VIDEO | IMAGES | DOCUMENTS | {".upod"}
)


def decode_text(blob):
    if blob.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        return blob.decode("utf-32"), "utf-32"
    if blob.startswith((b"\xff\xfe", b"\xfe\xff")):
        return blob.decode("utf-16"), "utf-16"
    try:
        return blob.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        # Common Windows exports use a legacy code page. Do not guess the
        # encoding of binary data merely because its extension is .txt.
        if b"\x00" in blob:
            raise ValueError("unrecognized text encoding with NUL bytes")
        return blob.decode("cp1252"), "windows-1252"


def milliseconds(stamp):
    m = re.fullmatch(r"(?:(\d+):)?(\d{2}):(\d{2})(?:[.,](\d{1,3}))?", stamp.strip())
    if not m:
        raise ValueError("unsupported timestamp: " + stamp)
    h, minute, second, fraction = m.groups()
    if int(minute) > 59 or int(second) > 59:
        raise ValueError("invalid timestamp")
    return ((int(h or 0) * 60 + int(minute)) * 60 + int(second)) * 1000 + int(
        (fraction or "").ljust(3, "0") or 0
    )


def subtitles(text):
    rows = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
        lines = block.splitlines()
        if not lines or lines[0].startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            continue
        at = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if at is None:
            continue
        start, end = lines[at].split("-->", 1)
        body = "\n".join(lines[at + 1 :]).strip()
        if not body:
            continue
        first, last = milliseconds(start), milliseconds(end.strip().split()[0])
        if last < first:
            raise ValueError("subtitle ends before it starts")
        rows.append(
            {"speaker_id": "unknown", "start_ms": first, "end_ms": last, "text": body}
        )
    if not rows:
        raise ValueError("no subtitle cues found")
    return rows


def structured(text, suffix):
    if suffix in (".csv", ".tsv"):
        values = list(
            csv.DictReader(
                io.StringIO(text), delimiter="\t" if suffix == ".tsv" else ","
            )
        )
    elif suffix == ".jsonl":
        values = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        value = json.loads(text)
        values = (
            value
            if isinstance(value, list)
            else value.get("segments", value.get("turns"))
        )
    if not isinstance(values, list) or not values:
        raise ValueError("expected nonempty text rows or segments/turns array")
    result = []
    for row in values:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("text"), str)
            or not row["text"].strip()
        ):
            raise ValueError("every structured row must contain text")
        out = {
            "text": row["text"],
            "speaker_id": str(row.get("speaker_id") or row.get("speaker") or "unknown"),
        }
        if row.get("start_ms") is not None:
            out["start_ms"] = int(row["start_ms"])
        elif row.get("timestamp"):
            out["start_ms"] = milliseconds(row["timestamp"])
        if row.get("end_ms") is not None:
            out["end_ms"] = int(row["end_ms"])
        if out.get("start_ms", 0) < 0 or out.get(
            "end_ms", out.get("start_ms", 0)
        ) < out.get("start_ms", 0):
            raise ValueError("invalid structured time range")
        result.append(out)
    return result


def docx_text(source):
    with zipfile.ZipFile(source) as z:
        info = z.getinfo("word/document.xml")
        if info.file_size > MAX_TRANSCRIPT_BYTES:
            raise ValueError("Word document XML exceeds extraction cap")
        tree = ET.fromstring(z.read(info))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    return "\n".join(
        "".join(t.text or "" for t in p.findall(".//w:t", ns))
        for p in tree.findall(".//w:p", ns)
    )


def ingest_container(source, output):
    """Process source media in a ZIP UPOD while preserving the original ZIP."""
    from .media_processing import process

    manifest, _ = open_upod(source)
    report = stage_upod(source, output)
    candidates = [
        json.loads(line)
        for line in (output / "candidate_turns.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    had_transcript = bool(candidates)
    processing = []
    with (
        zipfile.ZipFile(source) as z,
        tempfile.TemporaryDirectory(prefix="vox-contained-") as temporary,
    ):
        for i, item in enumerate(manifest["assets"]):
            # Previously derived images are not original source media.
            if item["role"] not in ("audio", "video", "image", "document") or item[
                "path"
            ].startswith(("processed/", "derived/")):
                continue
            file = Path(temporary) / ("asset-" + str(i) + Path(item["path"]).suffix)
            with z.open(item["path"]) as src, file.open("wb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
            kind = "pdf" if file.suffix.lower() == ".pdf" else item["role"]
            result = process(
                file,
                output.parent / (".processing-" + output.name + "-" + str(i)),
                kind,
            )
            processing.append(
                {"source_asset": item["path"], "report": result["report"]}
            )
            for derived in result["assets"]:
                target = output / "processed" / str(i) / Path(derived["path"]).name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(derived["path"], target)
                if not had_transcript and derived["role"] == "structured_turns":
                    for line in target.read_text(encoding="utf-8").splitlines():
                        if line.strip():
                            row = json.loads(line)
                            row.update(
                                reviewed=False,
                                speaker_label_source="provided_unreviewed",
                            )
                            candidates.append(row)
                elif not had_transcript and derived["role"] == "raw_transcript":
                    from .upod import suggest_turns

                    candidates.extend(suggest_turns(target.read_text(encoding="utf-8")))
    if processing:
        candidates.sort(
            key=lambda row: (
                row.get("start_ms") if row.get("start_ms") is not None else -1
            )
        )
        (output / "candidate_turns.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in candidates),
            encoding="utf-8",
        )
        review = json.loads((output / "review.json").read_text(encoding="utf-8"))
        review["turns"] = candidates
        (output / "review.json").write_bytes(_json(review))
        report.update(
            status="needs_review" if candidates else "processed",
            pending_processing=[],
            raw_turn_candidates=len(candidates),
            unknown_speaker_turns=sum(r["speaker_id"] == "unknown" for r in candidates),
            processing=processing,
            adapter="zip-upod-media",
        )
    report["adapter"] = report.get("adapter", "zip-upod")
    (output / "intake_report.json").write_bytes(_json(report))
    return report


def ingest_file(source, output, *, series_id="imported", episode_id=None):
    source, output = Path(source), Path(output)
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError("unsupported input extension: " + suffix)
    if source.is_symlink():
        raise ValueError("symlink input is not accepted")
    if suffix == ".upod":
        if zipfile.is_zipfile(source):
            return ingest_container(source, output)
        return import_capture(
            source, output, series_id=series_id, episode_id=episode_id
        )
    size = source.stat().st_size
    if size > MAX_MEMBER_BYTES:
        raise ValueError("input exceeds single-asset size cap")
    role = (
        "audio"
        if suffix in AUDIO
        else "video"
        if suffix in VIDEO
        else "image"
        if suffix in IMAGES
        else "document"
    )
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("intake output must be empty")
    if (
        shutil.disk_usage(
            output.parent if output.parent.exists() else source.parent
        ).free
        < size * 2 + 64 * 1024**2
    ):
        raise OSError("Not enough free disk space to preserve and stage this source")
    derived = None
    derived_role = "raw_transcript"
    adapter = "archive-only"
    warnings = []
    processed = None
    if suffix in TEXT | STRUCTURED | SUBTITLES:
        if size > MAX_TRANSCRIPT_BYTES:
            raise ValueError("text exceeds intake cap")
        text, encoding = decode_text(source.read_bytes())
        if suffix in TEXT:
            adapter = "text-" + encoding
            if encoding == "utf-8":
                role = "raw_transcript"
            else:
                derived = text.encode("utf-8")
                role = "document"
        else:
            rows = subtitles(text) if suffix in SUBTITLES else structured(text, suffix)
            derived = "".join(
                json.dumps(row, ensure_ascii=False) + "\n" for row in rows
            ).encode("utf-8")
            derived_role = "structured_turns"
            adapter = "subtitle-cues" if suffix in SUBTITLES else "structured-text"
    elif suffix == ".docx":
        derived = docx_text(source).encode("utf-8")
        adapter = "docx-paragraph-text"
    elif suffix in AUDIO | VIDEO | IMAGES | DOCUMENTS:
        from .media_processing import process

        kind = (
            "audio"
            if suffix in AUDIO
            else "video"
            if suffix in VIDEO
            else "image"
            if suffix in IMAGES
            else "pdf"
            if suffix == ".pdf"
            else "document"
        )
        work = output.parent / (".processing-" + output.name)
        processed = process(source, work, kind)
        adapter = "local-" + kind
    if derived is not None and len(derived) > MAX_TRANSCRIPT_BYTES:
        raise ValueError("derived text exceeds cap")
    if derived is not None and not derived.strip():
        derived = None
        warnings.append(
            "No text extracted; OCR or another extraction adapter is required."
        )
    source_path = "original/source" + suffix
    assets = [
        {
            "path": source_path,
            "role": role,
            "bytes": size,
            "sha256": sha256_file(source),
            "original_filename": source.name,
        }
    ]
    if derived is not None:
        assets.append(
            {
                "path": "derived/turns.jsonl"
                if derived_role == "structured_turns"
                else "derived/text.txt",
                "role": derived_role,
                "bytes": len(derived),
                "sha256": sha256_bytes(derived),
            }
        )
    if processed:
        for item in processed["assets"]:
            file = Path(item["path"])
            assets.append(
                {
                    "path": "processed/" + file.name,
                    "role": item["role"],
                    "bytes": file.stat().st_size,
                    "sha256": sha256_file(file),
                }
            )
    manifest = {
        "format": "vox-upod",
        "version": 1,
        "stage": "unsorted",
        "origin": "unverified_source",
        "podcast": {
            "episode_id": episode_id or source.stem,
            "series_id": series_id,
            "title": source.stem,
            "language": "und",
            "recorded_date": "",
            "source_uri": "",
        },
        "rights": {"status": "unknown"},
        "assets": assets,
        "adapter": {
            "name": adapter,
            "warnings": warnings,
            "source_is_podcast": "unverified",
        },
    }
    # Source modality does not establish that the content is a podcast.
    with tempfile.TemporaryDirectory(prefix="vox-intake-") as temporary:
        container = Path(temporary) / "source.upod"
        with zipfile.ZipFile(container, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("manifest.json", _json(manifest))
            z.write(
                source,
                source_path,
                compress_type=zipfile.ZIP_STORED
                if role in {"audio", "video", "image"}
                else zipfile.ZIP_DEFLATED,
            )
            if derived is not None:
                z.writestr(assets[1]["path"], derived)
            if processed:
                for item in processed["assets"]:
                    z.write(item["path"], "processed/" + Path(item["path"]).name)
        open_upod(container)
        report = stage_upod(container, output)
    report.update(adapter=adapter, warnings=warnings, original_filename=source.name)
    if processed:
        report["processing"] = processed["report"]
        report["pending_processing"] = []
        report["status"] = (
            "needs_review"
            if report["raw_turn_candidates"]
            else processed["report"]["status"]
        )
        for item in processed["assets"]:
            target = output / "processed" / Path(item["path"]).name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item["path"], target)
    (output / "intake_report.json").write_bytes(_json(report))
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source")
    p.add_argument("--output", required=True)
    p.add_argument("--series-id", default="imported")
    args = p.parse_args()
    print(
        json.dumps(
            ingest_file(args.source, args.output, series_id=args.series_id), indent=2
        )
    )


if __name__ == "__main__":
    main()

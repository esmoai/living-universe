"""UPOD v1: lossless, unsorted podcast *intake* container.

An .upod is a ZIP file with manifest.json and optional transcript/audio sources.
The contents are never equivalent to an approved training sample. Promotion
requires explicit human-reviewed turns and the corpus rights gate.
"""

from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
import stat
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from .corpus import require_episode

FORMAT = "vox-upod"
VERSION = 1
MAX_FILES = 10000
MAX_MEMBER_BYTES = 8 * 1024 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024 * 1024
MAX_TRANSCRIPT_BYTES = 16 * 1024 * 1024
TIMESTAMP = re.compile(
    r"^\[(?:(\d{1,2}):)?(\d{1,2}):(\d{2})(?:[.,](\d{1,3}))?\]\s*(.*)$"
)
SPEAKER = re.compile(r"^([^:\n]{1,64}):\s+(.+)$")


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def sha256_file(path: Path) -> str:
    hash_ = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hash_.update(block)
    return hash_.hexdigest()


def _json(data: Any) -> bytes:
    return (
        json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf8")


def _safe_name(name: str) -> bool:
    if (
        not name
        or len(name) > 256
        or "\\" in name
        or ":" in name
        or name.startswith("/")
    ):
        return False
    if "//" in name or name.endswith("/"):
        return False
    p = PurePosixPath(name)
    return not any(x in (".", "..", "") for x in p.parts)


def _validate_manifest(manifest: dict, entries: dict[str, zipfile.ZipInfo]) -> None:
    if (
        not isinstance(manifest, dict)
        or manifest.get("format") != FORMAT
        or manifest.get("version") != VERSION
    ):
        raise ValueError("unsupported UPOD format/version")
    if manifest.get("stage") != "unsorted":
        raise ValueError("UPOD must have stage=unsorted")
    podcast = manifest.get("podcast")
    if not isinstance(podcast, dict):
        raise ValueError("missing podcast object")
    for key in ("episode_id", "series_id", "title"):
        if not isinstance(podcast.get(key), str) or not podcast[key].strip():
            raise ValueError(f"podcast.{key} required")
    if not isinstance(manifest.get("rights"), dict):
        raise ValueError("rights object required, even if status=unknown")
    if manifest["rights"].get("status") not in ("unknown", "pending", "cleared"):
        raise ValueError("rights.status must be unknown/pending/cleared")
    assets = manifest.get("assets")
    if not isinstance(assets, list) or not assets:
        raise ValueError("at least one source asset required")
    if len(assets) > MAX_FILES:
        raise ValueError("too many assets")
    paths = set()
    for a in assets:
        if (
            not isinstance(a, dict)
            or not isinstance(a.get("path"), str)
            or not _safe_name(a["path"])
        ):
            raise ValueError("invalid asset record or path")
        name = a["path"]
        if name in paths or name == "manifest.json":
            raise ValueError("duplicate or reserved asset path")
        paths.add(name)
        if name not in entries:
            raise ValueError(f"asset missing from container: {name}")
        if a.get("role") not in (
            "raw_transcript",
            "structured_turns",
            "audio",
            "video",
            "image",
            "document",
            "notes",
            "rights_evidence",
        ):
            raise ValueError(f"unknown asset role {a.get('role')}")
        if not re.fullmatch("[0-9a-f]{64}", str(a.get("sha256", ""))):
            raise ValueError(f"asset missing SHA-256: {name}")
        if a.get("bytes") != entries[name].file_size:
            raise ValueError(f"asset declared byte size mismatch: {name}")
    if set(entries) != paths | {"manifest.json"}:
        raise ValueError("all file entries must be declared in manifest.assets")


def open_upod(path: str | Path) -> tuple[dict, dict[str, zipfile.ZipInfo]]:
    path = Path(path)
    if path.suffix.lower() != ".upod":
        raise ValueError("expected a .upod container")
    try:
        zf = zipfile.ZipFile(path, "r")
    except zipfile.BadZipFile as e:
        raise ValueError(
            "UPOD v1 is ZIP-based; supplied file is not a ZIP container"
        ) from e
    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_FILES + 1:
            raise ValueError("UPOD has too many members")
        entries = {}
        total = 0
        for info in infos:
            if (
                info.is_dir()
                or not _safe_name(info.filename)
                or info.filename in entries
            ):
                raise ValueError(f"unsafe or duplicate UPOD ZIP name: {info.filename}")
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError("UPOD symlinks prohibited")
            if info.file_size > MAX_MEMBER_BYTES:
                raise ValueError("UPOD single member exceeds cap")
            total += info.file_size
            if total > MAX_TOTAL_BYTES:
                raise ValueError("UPOD expanded size exceeds cap")
            entries[info.filename] = info
        if "manifest.json" not in entries:
            raise ValueError("UPOD manifest.json missing")
        if entries["manifest.json"].file_size > 1024 * 1024:
            raise ValueError("UPOD manifest too large")
        try:
            manifest = json.loads(zf.read("manifest.json").decode("utf8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ValueError("invalid UPOD manifest JSON") from e
        _validate_manifest(manifest, entries)
        # Stream hashes: never materialize audio/video payloads in RAM.
        for asset in manifest["assets"]:
            h = hashlib.sha256()
            with zf.open(asset["path"]) as handle:
                while chunk := handle.read(1024 * 1024):
                    h.update(chunk)
            if h.hexdigest() != asset["sha256"]:
                raise ValueError(f"UPOD checksum mismatch: {asset['path']}")
    return manifest, entries


def _parse_timestamp(line: str) -> tuple[int | None, str]:
    if re.fullmatch(r"\d{1,}:\d{2}:\d{2}(?:[.,]\d{1,3})?", line.strip()):
        line = "[" + line.strip() + "]"
    match = TIMESTAMP.match(line)
    if not match:
        return None, line
    hours, minute, second, millis, rest = match.groups()
    if int(minute) > 59 or int(second) > 59:
        raise ValueError("timestamp minutes/seconds must be in 0..59")
    start = ((int(hours or 0) * 60 + int(minute)) * 60 + int(second)) * 1000 + int(
        (millis or "").ljust(3, "0") or 0
    )
    return start, rest


def suggest_turns(text: str) -> list[dict]:
    """Explicit labels only. No speaker diarization or semantic assumptions."""
    # Browser captures place each timestamp on its own line. Associate the
    # entire following paragraph with that timestamp, never a separate turn.
    lines = text.splitlines()
    standalone = any(
        _parse_timestamp(line.strip())[0] is not None
        and not _parse_timestamp(line.strip())[1].strip()
        for line in lines
    )
    if standalone:
        out, body, pending, previous = [], [], None, -1

        def flush():
            if not body:
                if pending is not None:
                    raise ValueError("timestamp has no following dialogue")
                return
            content = "\n".join(body).strip()
            # This capture format contains no speaker field. A colon inside
            # ordinary dialogue must never be mistaken for an identity label.
            row = {
                "speaker_id": "unknown",
                "text": content,
                "reviewed": False,
                "speaker_label_source": "unknown",
            }
            if pending is not None:
                row["start_ms"] = pending
            out.append(row)

        for line in lines:
            at, remainder = _parse_timestamp(line.strip())
            if at is not None:
                if at < previous:
                    raise ValueError("timestamps must be nondecreasing")
                flush()
                body = []
                pending = at
                previous = at
                if remainder.strip():
                    body.append(remainder.strip())
            elif line.strip():
                body.append(line)
        flush()
        return out
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        at, body = _parse_timestamp(line)
        speaker = SPEAKER.match(body)
        raw_label = speaker.group(1).strip() if speaker else None
        body = speaker.group(2).strip() if speaker else body
        # Never treat headings or arbitrary lines with colon as proven identities.
        row = {
            "speaker_id": raw_label or "unknown",
            "text": body,
            "reviewed": False,
            "speaker_label_source": "explicit_text" if raw_label else "unknown",
        }
        if at is not None:
            row["start_ms"] = at
        out.append(row)
    return out


def import_capture(
    path: str | Path,
    output: str | Path,
    *,
    series_id: str = "imported",
    episode_id: str | None = None,
    title: str | None = None,
    source_uri: str = "",
) -> dict:
    """Explicit plain-text-to-ZIP adapter. Never rewrite the original capture."""
    path, output = Path(path), Path(output)
    if zipfile.is_zipfile(path):
        return stage_upod(path, output)
    if path.stat().st_size > MAX_TRANSCRIPT_BYTES:
        raise ValueError("capture exceeds transcript size limit")
    text = path.read_text(encoding="utf-8-sig")
    candidates = suggest_turns(text)
    if not candidates:
        raise ValueError("capture has no dialogue")
    with tempfile.TemporaryDirectory(prefix="vox-capture-") as temporary:
        container = Path(temporary) / "wrapped.upod"
        build_upod(
            path,
            container,
            episode_id=episode_id or path.stem,
            series_id=series_id,
            title=title or path.stem,
            source_uri=source_uri,
        )
        report = stage_upod(container, output)
    report["source_capture"] = {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "format": "plain-utf8-transcript",
        "bytes": path.stat().st_size,
    }
    (output / "intake_report.json").write_bytes(_json(report))
    return report


def import_folder(
    folder: str | Path,
    output: str | Path,
    *,
    series_id: str = "imported",
    selected_paths=None,
    on_progress=None,
) -> dict:
    """Resumable intake of .txt/.md/.upod files. No source renaming or edits."""
    folder, output = Path(folder).resolve(), Path(output).resolve()
    if not folder.is_dir():
        raise ValueError("capture folder does not exist")
    if output == folder or output.is_relative_to(folder):
        raise ValueError("choose an output folder outside the capture folder")
    output.mkdir(parents=True, exist_ok=True)
    checkpoint = output / "capture-index.json"
    index = (
        json.loads(checkpoint.read_text(encoding="utf-8"))
        if checkpoint.exists()
        else {"schema": "vox-capture-folder/1", "captures": {}}
    )
    if index.get("schema") != "vox-capture-folder/1":
        raise ValueError("unsupported capture index")
    results = []
    from .intake import SUPPORTED, ingest_file

    code_root = Path(__file__).resolve().parent
    fingerprint = hashlib.sha256()
    for file in (
        code_root / "upod.py",
        code_root / "intake.py",
        code_root / "media_processing.py",
        code_root.parent / "ingestion-config.json",
    ):
        fingerprint.update(file.read_bytes())
    pipeline = fingerprint.hexdigest()
    sources = (
        folder.iterdir()
        if selected_paths is None
        else [Path(p).resolve() for p in selected_paths]
    )
    for source in sorted(sources, key=lambda p: p.name.casefold()):
        from .media_processing import CANCEL

        if CANCEL.is_set():
            break
        if not source.is_file() or source.suffix.lower() not in SUPPORTED:
            continue
        if source.is_symlink():
            continue
        key = str(source)
        if on_progress:
            on_progress("Processing " + source.name)
        if source.stat().st_size > MAX_TOTAL_BYTES:
            results.append(
                {
                    "path": key,
                    "status": "error",
                    "error": "capture exceeds intake size cap",
                }
            )
            continue
        digest = sha256_file(source)
        prior = index["captures"].get(key)
        if (
            prior
            and prior.get("sha256") == digest
            and prior.get("pipeline") == pipeline
            and (output / prior["staging"] / "intake_report.json").is_file()
        ):
            results.append({"path": key, "status": "unchanged"})
            continue
        identity = re.sub(r"[^a-zA-Z0-9_-]", "-", source.stem)[:100] or "episode"
        # Distinct paths with the same title remain separate; revisions get a
        # new staging directory so an existing source is never overwritten.
        destination = (
            identity
            + "-"
            + hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]
            + "-"
            + digest[:12]
            + "-"
            + pipeline[:8]
        )
        target = output / destination
        try:
            if target.exists() and any(target.iterdir()):
                raise FileExistsError(
                    "staging already exists without a matching checkpoint; inspect before retry"
                )
            report = ingest_file(
                source, target, series_id=series_id, episode_id=identity
            )
            index["captures"][key] = {
                "sha256": digest,
                "staging": destination,
                "pipeline": pipeline,
                "segments": report["raw_turn_candidates"],
                "status": report["status"],
            }
            temporary = checkpoint.with_suffix(".tmp")
            temporary.write_bytes(_json(index))
            temporary.replace(checkpoint)
            results.append({"path": key, "status": "imported", "staging": str(target)})
            if on_progress:
                on_progress("Imported " + source.name)
        except Exception as error:
            # Adapter-specific errors (malformed PDF/XML/ZIP, missing optional
            # decoder, etc.) must not stop ingestion of the other captures.
            results.append({"path": key, "status": "error", "error": str(error)})
            if on_progress:
                on_progress("Failed " + source.name + ": " + str(error)[-300:])
    summary = {
        "schema": "vox-capture-folder-report/1",
        "input": str(folder),
        "imported": sum(r["status"] == "imported" for r in results),
        "unchanged": sum(r["status"] == "unchanged" for r in results),
        "errors": sum(r["status"] == "error" for r in results),
        "files": results,
    }
    (output / "last-import-report.json").write_bytes(_json(summary))
    return summary


def _read_transcript(zf: zipfile.ZipFile, asset: dict) -> list[dict]:
    size = zf.getinfo(asset["path"]).file_size
    if size > MAX_TRANSCRIPT_BYTES:
        raise ValueError("transcript asset too large for R02 intake")
    txt = zf.read(asset["path"]).decode("utf-8-sig")
    if asset["role"] == "raw_transcript":
        return suggest_turns(txt)
    if asset["role"] == "structured_turns":
        rows = []
        for line in txt.splitlines():
            if line.strip():
                row = json.loads(line)
                if not isinstance(row, dict) or not isinstance(row.get("text"), str):
                    raise ValueError("invalid structured_turns row")
                candidate = {
                    "speaker_id": str(row.get("speaker_id") or "unknown"),
                    "text": row["text"],
                    "start_ms": row.get("start_ms"),
                    "reviewed": False,
                    "speaker_label_source": "provided_unreviewed",
                }
                if row.get("end_ms") is not None:
                    candidate["end_ms"] = row["end_ms"]
                for key in (
                    "words",
                    "track_index",
                    "timing_source",
                    "speaker_attribution",
                ):
                    if key in row:
                        candidate[key] = row[key]
                rows.append(candidate)
        return rows
    return []


def build_upod(
    transcript: str | Path | None,
    destination: str | Path,
    *,
    episode_id: str,
    series_id: str,
    title: str,
    recorded_date: str = "",
    source_uri: str = "",
    language: str = "en",
    synthetic_smoke: bool = False,
    media: list[str | Path] | None = None,
) -> dict:
    """Assemble one unreviewed session. Audio-only UPODs are valid and need transcription."""
    sources = []
    if transcript is not None:
        src = Path(transcript)
        if not src.is_file():
            raise FileNotFoundError(src)
        if src.stat().st_size > MAX_TRANSCRIPT_BYTES:
            raise ValueError("transcript exceeds R02 intake maximum")
        src.read_text(encoding="utf-8-sig")
        sources.append((src, "transcript/raw.txt", "raw_transcript"))
    for i, media_file in enumerate(media or [], 1):
        src = Path(media_file)
        if not src.is_file():
            raise FileNotFoundError(src)
        kind = src.suffix.lower()
        if kind in (".mp3", ".m4a", ".aac", ".opus", ".ogg", ".wav", ".flac"):
            role = "audio"
        elif kind in (".mp4", ".mov", ".webm", ".mkv"):
            role = "video"
        else:
            raise ValueError(f"unsupported audio/video source extension: {kind}")
        if src.stat().st_size > MAX_MEMBER_BYTES:
            raise ValueError("media exceeds single-member size limit")
        safe_basename = re.sub(r"[^a-zA-Z0-9._-]", "_", src.name)[-120:]
        sources.append((src, f"media/{i:03d}-{safe_basename}", role))
    if not sources:
        raise ValueError("UPOD requires at least one transcript or media asset")
    if (
        len(sources) > MAX_FILES
        or sum(src.stat().st_size for src, _, _ in sources) > MAX_TOTAL_BYTES
    ):
        raise ValueError("UPOD source count or expanded byte budget exceeded")
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    assets = [
        {
            "path": name,
            "role": role,
            "sha256": sha256_file(src),
            "bytes": src.stat().st_size,
            "original_filename": src.name,
        }
        for src, name, role in sources
    ]
    manifest = {
        "format": FORMAT,
        "version": VERSION,
        "stage": "unsorted",
        "podcast": {
            "episode_id": episode_id,
            "series_id": series_id,
            "title": title,
            "recorded_date": recorded_date,
            "language": language,
            "source_uri": source_uri,
        },
        "origin": "synthetic_smoke" if synthetic_smoke else "real_podcast",
        "rights": {
            "status": "unknown",
            "rights_holder": None,
            "permission_basis": None,
            "permission_reference": None,
            "allowed_uses": [],
        },
        "assets": assets,
    }
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zip_:
        zip_.writestr("manifest.json", _json(manifest))
        for src, name, role in sources:
            zip_.write(
                src,
                arcname=name,
                compress_type=zipfile.ZIP_STORED
                if role in ("audio", "video")
                else zipfile.ZIP_DEFLATED,
            )
    open_upod(dest)
    return manifest


def stage_upod(path: str | Path, output: str | Path) -> dict:
    path = Path(path)
    manifest, entries = open_upod(path)
    out = Path(output)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"intake destination must be empty: {out}")
    out.mkdir(parents=True, exist_ok=True)
    candidates = []
    with zipfile.ZipFile(path) as zf:
        for asset in manifest["assets"]:
            if asset["role"] in ("raw_transcript", "structured_turns"):
                candidates.extend(_read_transcript(zf, asset))
    shutil.copyfile(path, out / "source.upod")
    (out / "intake_manifest.json").write_bytes(_json(manifest))
    (out / "candidate_turns.jsonl").write_text(
        "".join(json.dumps(t, ensure_ascii=False) + "\n" for t in candidates),
        encoding="utf8",
    )
    review = {
        "upod_sha256": sha256_file(out / "source.upod"),
        "review_complete": False,
        "approved_for_training": False,
        "reviewed_by": "",
        "podcast": manifest["podcast"],
        "origin": manifest["origin"],
        "rights": manifest["rights"],
        "turns": candidates,
    }
    (out / "review.json").write_bytes(_json(review))
    roles = {a["role"] for a in manifest["assets"]}
    pending = []
    if roles & {"audio", "video"}:
        pending.append("transcription")
    if "image" in roles:
        pending.append("visual_description_or_ocr")
    if "document" in roles and not candidates:
        pending.append("document_text_extraction")
    status = (
        "needs_review"
        if candidates
        else (
            "needs_transcription"
            if roles & {"audio", "video"}
            else "needs_visual_processing"
            if "image" in roles
            else "needs_text_extraction"
        )
    )
    report = {
        "format": FORMAT,
        "status": status,
        "source_sha256": review["upod_sha256"],
        "raw_turn_candidates": len(candidates),
        "unknown_speaker_turns": sum(t["speaker_id"] == "unknown" for t in candidates),
        "rights_status": manifest["rights"]["status"],
        "trainable": False,
        "audio_assets": sum(a["role"] == "audio" for a in manifest["assets"]),
        "pending_processing": pending,
        "staging": str(out),
    }
    (out / "intake_report.json").write_bytes(_json(report))
    return report


def promote(staging: str | Path, output_jsonl: str | Path) -> dict:
    folder = Path(staging)
    source = folder / "source.upod"
    base, _ = open_upod(source)
    review = json.loads((folder / "review.json").read_text(encoding="utf8"))
    if review.get("upod_sha256") != sha256_file(source):
        raise ValueError("UPOD source SHA changed since intake")
    if (
        review.get("review_complete") is not True
        or review.get("approved_for_training") is not True
    ):
        raise ValueError(
            "human review and separate explicit training approval required"
        )
    if (
        not isinstance(review.get("reviewed_by"), str)
        or not review["reviewed_by"].strip()
    ):
        raise ValueError("reviewed_by required")
    rights = review.get("rights", {})
    if rights.get("status") != "cleared":
        raise ValueError("rights.status must be cleared before training promotion")
    turns = review.get("turns", [])
    if not isinstance(turns, list) or len(turns) < 2:
        raise ValueError("review must contain >=2 dialogue turns")
    cleaned = []
    for i, turn in enumerate(turns):
        if not isinstance(turn, dict) or turn.get("reviewed") is not True:
            raise ValueError(f"turn {i} not manually reviewed")
        who = turn.get("speaker_id")
        if not isinstance(who, str) or not who.strip() or who == "unknown":
            raise ValueError(f"turn {i} speaker must be resolved")
        if not isinstance(turn.get("text"), str) or not turn["text"].strip():
            raise ValueError(f"turn {i} missing text")
        row = {"speaker_id": who.strip(), "text": turn["text"].strip()}
        if turn.get("start_ms") is not None:
            row["start_ms"] = int(turn["start_ms"])
        if turn.get("end_ms") is not None:
            row["end_ms"] = int(turn["end_ms"])
        if turn.get("words") is not None:
            row["words"] = turn["words"]
        cleaned.append(row)
    podcast = review.get("podcast", {})
    if base["podcast"]["episode_id"] != podcast.get("episode_id") or base["podcast"][
        "series_id"
    ] != podcast.get("series_id"):
        raise ValueError("series/episode identity cannot change in review")
    origin = base["origin"]
    if origin == "unverified_source":
        if review.get("origin") != "real_podcast":
            raise ValueError(
                "unverified source requires explicit podcast-origin review before corpus promotion"
            )
        origin = "real_podcast"
    episode = {
        "episode_id": podcast["episode_id"],
        "series_id": podcast["series_id"],
        "recorded_date": podcast.get("recorded_date"),
        "title": podcast["title"],
        "rights_holder": rights.get("rights_holder"),
        "permission_basis": rights.get("permission_basis"),
        "permission_reference": rights.get("permission_reference"),
        "source_uri": podcast.get("source_uri"),
        "origin": origin,
        "is_podcast": origin == "real_podcast",
        "language": podcast.get("language", "en"),
        "allowed_uses": rights.get("allowed_uses", []),
        "turns": cleaned,
        "provenance": {
            "container_format": FORMAT,
            "container_version": VERSION,
            "upod_sha256": sha256_file(source),
            "reviewed_by": review["reviewed_by"],
            "promoted_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    require_episode(episode, allow_smoke=origin == "synthetic_smoke")
    dest = Path(output_jsonl)
    if dest.exists():
        raise FileExistsError("never overwrite an existing curated corpus file")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(episode, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf8"
    )
    return {
        "episode_id": episode["episode_id"],
        "output": str(dest),
        "origin": episode["origin"],
        "release_eligible": episode["origin"] == "real_podcast",
        "turns": len(cleaned),
    }


def main():
    p = argparse.ArgumentParser(description="Vox FIBRA .upod unsorted podcast intake")
    sub = p.add_subparsers(dest="command", required=True)
    create = sub.add_parser(
        "create", help="Package raw UTF-8 text as .upod (unreviewed)"
    )
    create.add_argument("--transcript")
    create.add_argument("--media", action="append", default=[])
    create.add_argument("--output", required=True)
    for name in ("episode-id", "series-id", "title"):
        create.add_argument("--" + name, required=True)
    create.add_argument("--recorded-date", default="")
    create.add_argument("--source-uri", default="")
    create.add_argument("--synthetic-smoke", action="store_true")
    inspect = sub.add_parser("inspect")
    inspect.add_argument("upod")
    stage = sub.add_parser("stage")
    stage.add_argument("upod")
    stage.add_argument("--output", required=True)
    capture = sub.add_parser(
        "import-capture",
        help="Stage plain-text .upod or ZIP UPOD without changing source bytes",
    )
    capture.add_argument("upod")
    capture.add_argument("--output", required=True)
    capture.add_argument("--series-id", default="imported")
    capture.add_argument("--episode-id")
    capture.add_argument("--title")
    capture.add_argument("--source-uri", default="")
    batch = sub.add_parser(
        "import-folder",
        help="Import a folder of .txt/.md/.upod captures; unchanged files are skipped",
    )
    batch.add_argument("folder")
    batch.add_argument("--output", required=True)
    batch.add_argument("--series-id", default="imported")
    pro = sub.add_parser("promote")
    pro.add_argument("staging")
    pro.add_argument("--output", required=True)
    a = p.parse_args()
    if a.command == "create":
        result = build_upod(
            a.transcript,
            a.output,
            episode_id=a.episode_id,
            series_id=a.series_id,
            title=a.title,
            recorded_date=a.recorded_date,
            source_uri=a.source_uri,
            synthetic_smoke=a.synthetic_smoke,
            media=a.media,
        )
    elif a.command == "inspect":
        result, _ = open_upod(a.upod)
    elif a.command == "stage":
        result = stage_upod(a.upod, a.output)
    elif a.command == "import-capture":
        result = import_capture(
            a.upod,
            a.output,
            series_id=a.series_id,
            episode_id=a.episode_id,
            title=a.title,
            source_uri=a.source_uri,
        )
    elif a.command == "import-folder":
        result = import_folder(a.folder, a.output, series_id=a.series_id)
    else:
        result = promote(a.staging, a.output)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

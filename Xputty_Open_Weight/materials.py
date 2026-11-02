"""Draft material operations with immutable originals and conflict detection."""

import hashlib, uuid
from vox.intake import decode_text, TEXT, STRUCTURED, SUBTITLES
from worker import write

EDITABLE = TEXT | STRUCTURED | SUBTITLES | {".upod"}


def identity(record):
    return record.get("id", record["sha256"])


def record(state, identifier):
    for item in state["files"]:
        if identity(item) == identifier:
            return item
    raise ValueError("Material no longer exists in this project")


def source_path(root, item):
    path = (
        root / item.get("path", "uploads/" + item["sha256"][:12] + "-" + item["name"])
    ).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Invalid stored material path")
    return path


def editable(root, item):
    path = source_path(root, item)
    return (
        path.suffix.lower() in EDITABLE
        and path.stat().st_size <= 16 * 1024**2
        and not path.read_bytes()[:4] == b"PK\x03\x04"
    )


def inspect(root, state, identifier):
    item = record(state, identifier)
    result = {**item, "id": identity(item), "editable": editable(root, item)}
    if result["editable"]:
        result["text"] = decode_text(source_path(root, item).read_bytes())[0]
    return result


def mutate(root, state, action, body):
    if state["status"] != "draft":
        raise ValueError(
            "Materials are locked after a build starts. Create a new project for different training data."
        )
    if action == "restore":
        removed = state.get("removed_files", [])
        item = next((x for x in removed if identity(x) == body.get("id")), None)
        if item is None:
            raise ValueError("Removed material not found")
        if any(
            identity(x) == identity(item) or x["sha256"] == item["sha256"]
            for x in state["files"]
        ):
            raise ValueError("This material is already active")
        removed.remove(item)
        state["files"].append(item)
        write(root / "state.json", state)
        return state
    item = record(state, str(body.get("id", "")))
    identifier = identity(item)
    if action == "remove":
        state["files"].remove(item)
        state.setdefault("removed_files", []).append(item)
    elif action == "edit":
        if not editable(root, item):
            raise ValueError(
                "This binary file cannot be edited as text. Replace it with an edited file instead."
            )
        if body.get("expected_sha256") != item["sha256"]:
            raise ValueError(
                "This file changed while you were editing. Reopen it to load the latest version."
            )
        text = body.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Material text cannot be empty")
        blob = text.encode("utf-8")
        if len(blob) > 16 * 1024**2:
            raise ValueError("Edited text exceeds 16 MiB")
        destination = (
            root / "edits" / (uuid.uuid4().hex + source_path(root, item).suffix)
        )
        destination.parent.mkdir(exist_ok=True)
        destination.write_bytes(blob)
        state.setdefault("material_history", []).append(dict(item))
        item.update(
            id=identifier,
            path=destination.relative_to(root).as_posix(),
            sha256=hashlib.sha256(blob).hexdigest(),
            bytes=len(blob),
            edited=True,
        )
    else:
        raise ValueError("Unknown material operation")
    write(root / "state.json", state)
    return state

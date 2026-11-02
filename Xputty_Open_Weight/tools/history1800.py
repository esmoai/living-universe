"""Reproducible nineteenth-century starter, downloaded from a listed PG mirror.

Sources are a curated pilot, not a representative sample of the whole century.
Gutenberg release dates are never used as historical publication dates.
"""

import argparse
import hashlib
import json
import re
import ssl
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from worker import write

# Year = first publication of the work, not the current digitization/edition.
WORKS = [
    (11, 1865, "Alice's Adventures in Wonderland", "Lewis Carroll", "fiction"),
    (
        23,
        1845,
        "Narrative of the Life of Frederick Douglass",
        "Frederick Douglass",
        "memoir",
    ),
    (35, 1895, "The Time Machine", "H. G. Wells", "fiction"),
    (36, 1898, "The War of the Worlds", "H. G. Wells", "fiction"),
    (46, 1843, "A Christmas Carol", "Charles Dickens", "fiction"),
    (74, 1876, "The Adventures of Tom Sawyer", "Mark Twain", "fiction"),
    (76, 1884, "Adventures of Huckleberry Finn", "Mark Twain", "fiction"),
    (84, 1818, "Frankenstein", "Mary Shelley", "fiction"),
    (174, 1890, "The Picture of Dorian Gray", "Oscar Wilde", "fiction"),
    (205, 1854, "Walden", "Henry David Thoreau", "essays"),
    (1260, 1847, "Jane Eyre", "Charlotte Bronte", "fiction"),
    (1342, 1813, "Pride and Prejudice", "Jane Austen", "fiction"),
    (1400, 1861, "Great Expectations", "Charles Dickens", "fiction"),
    (2009, 1859, "The Origin of Species", "Charles Darwin", "science"),
    (2701, 1851, "Moby Dick", "Herman Melville", "fiction"),
    (11224, 1861, "Utilitarianism", "John Stuart Mill", "philosophy"),
]
MIRROR = "https://gutenberg.pglaf.org/cache/epub/{id}/pg{id}.txt"
POLICY = "https://www.gutenberg.org/MIRRORS.ALL"


def clean(blob):
    # Some mirror files have CR-CR-LF: normalize before splitting paragraphs.
    text = (
        blob.decode("utf-8-sig")
        .replace("\r\r\n", "\n")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    start = re.search(
        r"(?im)^\*\*\* START OF (?:THE|THIS) PROJECT GUTENBERG.*?\*\*\*", text
    )
    end = re.search(
        r"(?im)^\*\*\* END OF (?:THE|THIS) PROJECT GUTENBERG.*?\*\*\*", text
    )
    if not start or not end or end.start() <= start.end():
        raise ValueError("Missing Gutenberg boundaries; review this edition manually")
    body = text[start.end() : end.start()]
    # Known modern editorial sections inside the PG boundaries. Keep originals;
    # remove only the explicitly identified digital notes from working copies.
    body = re.sub(
        r"(?is)Note from the original file:.*?\[Officially celebrated.*?\]", "", body
    )
    body = re.sub(
        r"(?is)Original Transcriber[’']s Notes:.*?(?=\n\s*ETYMOLOGY\.)", "", body
    )
    body = re.sub(
        r"(?is)There are several editions of this ebook.*?(?=\nOn the Origin of Species)",
        "",
        body,
    )
    body = re.sub(r"(?im)^\s*\[Illustration[^\n]*\]\s*$", "", body)
    # Remove clearly labelled digital transcriber notes, never rewrite the author's words.
    body = re.sub(r"(?is)\[transcriber[’']?s? note:.*?\]", "", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    if len(body.split()) < 5000:
        raise ValueError("Unexpectedly short book; manual review needed")
    return body + "\n"


def collect(root, limit=None):
    import certifi

    root = Path(root).resolve()
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    if state.get("mode") != "plain" or (root / "dense/checkpoint.pt").exists():
        raise ValueError("Use a fresh plain-text project")
    records = []
    failures = []
    for i, (identifier, year, title, author, genre) in enumerate(WORKS[:limit]):
        state.update(
            status="running", phase=f"Collecting {i + 1}/{len(WORKS[:limit])}: {title}"
        )
        write(root / "state.json", state)
        print(state["phase"], flush=True)
        raw = root / "historical-originals" / f"pg{identifier}.txt"
        raw.parent.mkdir(exist_ok=True)
        url = MIRROR.format(id=identifier)
        try:
            if not raw.exists():
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Xputty-Open-Weight-Historical-Pilot/1.0"},
                )
                with urllib.request.urlopen(
                    req,
                    context=ssl.create_default_context(cafile=certifi.where()),
                    timeout=30,
                ) as response:
                    blob = response.read(8 * 1024**2 + 1)
                if len(blob) > 8 * 1024**2:
                    raise ValueError("Book exceeds pilot file limit")
                # Validate before accepting the download as a reusable original.
                clean(blob)
                raw.write_bytes(blob)
                time.sleep(2)
            blob = raw.read_bytes()
            body = clean(blob)
            digest = hashlib.sha256(body.encode()).hexdigest()
            name = f"{year}-pg{identifier}.txt"
            target = root / "uploads" / name
            target.parent.mkdir(exist_ok=True)
            if not target.exists():
                target.write_text(body, encoding="utf-8", newline="\n")
            item = dict(
                id=uuid.uuid4().hex,
                name=name,
                path="uploads/" + name,
                sha256=digest,
                bytes=len(body.encode()),
                source_url=f"https://www.gutenberg.org/ebooks/{identifier}",
            )
            if not any(f["sha256"] == digest for f in state["files"]):
                state["files"].append(item)
            records.append(
                dict(
                    gutenberg_id=identifier,
                    first_publication_year=year,
                    title=title,
                    author=author,
                    genre=genre,
                    download_url=url,
                    catalog_url=item["source_url"],
                    original_sha256=hashlib.sha256(blob).hexdigest(),
                    working_sha256=digest,
                    words=len(body.split()),
                    working_path=item["path"],
                    original_path=str(raw.relative_to(root)),
                    edition_notes={
                        84: "1831 revised text; work first published 1818",
                        174: "1891 expanded book; magazine version 1890",
                        2009: "1872 sixth London edition; first edition 1859",
                    }.get(
                        identifier,
                        "First-publication year is curated. Digital editorial material has not been exhaustively audited.",
                    ),
                )
            )
        except (OSError, ValueError, UnicodeError) as error:
            failures.append(dict(gutenberg_id=identifier, error=str(error)))
            print(f"Skipped pg{identifier}: {error}", flush=True)
        write(root / "state.json", state)
    record = dict(
        schema="xow-historical-pilot/1",
        period=[1800, 1899],
        language="en",
        date_basis="Curated first publication of work, not ebook release or author lifespan",
        downloaded_at=datetime.now(timezone.utc).isoformat(),
        mirror_policy=POLICY,
        sources=records,
        failures=failures,
        scope="Literature-heavy English pilot, not a representative historical worldview. Modern transcriptions; edition purity unverified.",
        rights_basis="Project Gutenberg public-domain-in-USA texts; original download and its license preserved separately.",
        cleaning="PG header/footer; illustration markers; labelled bracketed transcriber notes; Douglass electronic dedication; Moby-Dick digital transcriber preface; Darwin ebook-edition guide. Original bytes retained.",
    )
    write(root / "historical-sources.json", record)
    state.update(
        status="draft",
        phase="Review 1800s material",
        mode="plain",
        steps=2000,
        historical_summary=dict(
            works=len(records),
            words=sum(r["words"] for r in records),
            failures=failures,
        ),
    )
    if len(records) < 3:
        state.update(
            status="failed",
            error="Fewer than three books downloaded; inspect activity and retry in a new project",
        )
    write(root / "state.json", state)
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--collect-only", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--steps", type=int, default=2000)
    parser.add_argument("--preset", choices=["research-48m-v1", "tiny-1m-v1"], default="research-48m-v1")
    args = parser.parse_args()
    root = args.root.resolve()
    if (root / "dense/checkpoint.pt").exists():
        raise SystemExit(
            "This project already has trained weights. Continue with worker.py --steps TOTAL, or choose a new collection root."
        )
    if not (root / "state.json").exists():
        root.mkdir(parents=True, exist_ok=True)
        write(
            root / "state.json",
            dict(
                id=root.name,
                name="1800s · first experiment",
                created=time.time(),
                status="draft",
                mode="plain",
                preset=args.preset,
                phase="Collecting historical works",
                files=[],
            ),
        )
    try:
        report = collect(root, args.limit)
        print(
            json.dumps(
                {
                    "works": len(report["sources"]),
                    "words": sum(r["words"] for r in report["sources"]),
                    "failures": report["failures"],
                }
            ),
            flush=True,
        )
        if not args.collect_only and len(report["sources"]) >= 3:
            from worker import run

            run(root, args.steps)
    except Exception as error:
        state = json.loads((root / "state.json").read_text())
        state.update(status="failed", error=str(error))
        write(root / "state.json", state)
        raise

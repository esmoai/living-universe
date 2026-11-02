"""Import selected files/folders through the same resumable pipeline as the desk."""

import argparse
import json
from pathlib import Path
from .upod import import_folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reports = []
    for source in args.sources:
        reports.append(
            import_folder(
                source if source.is_dir() else source.parent,
                args.output,
                selected_paths=None if source.is_dir() else [source],
                on_progress=lambda text: print(text, flush=True),
            )
        )
    totals = {
        key: sum(report[key] for report in reports)
        for key in ("imported", "unchanged", "errors")
    }
    print(json.dumps(totals, indent=2))
    raise SystemExit(1 if totals["errors"] else 0)


if __name__ == "__main__":
    main()

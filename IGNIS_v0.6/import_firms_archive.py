#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from backend.archive_store import ARCHIVE_SOURCES, archive_store


def main() -> None:
    parser = argparse.ArgumentParser(description="Import NASA FIRMS archive CSV/ZIP files into IGNIS local DuckDB.")
    parser.add_argument("paths", nargs="+", help="CSV/TXT/ZIP archive files")
    parser.add_argument("--source", required=True, choices=sorted(ARCHIVE_SOURCES), help="Sensor/source represented by these files")
    args = parser.parse_args()

    for raw in args.paths:
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            print(f"[SKIP] Not found: {path}")
            continue
        print(f"[IMPORT] {path.name} as {args.source}")
        for result in archive_store.import_path(path, args.source):
            print(f"  {result.status}: {result.rows_inserted:,} inserted / {result.rows_seen:,} seen · {result.file}")

    status = archive_store.status()
    print(f"\n[IGNIS] Archive now contains {status['observations']:,} observations from {status['imports']} file(s).")
    print(f"[IGNIS] Coverage: {status['min_date']} → {status['max_date']}")


if __name__ == "__main__":
    main()

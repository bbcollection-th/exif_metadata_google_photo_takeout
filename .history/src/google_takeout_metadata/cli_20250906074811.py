"""Command line interface."""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

from .processor import process_directory


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Merge Google Takeout metadata into images")
    parser.add_argument("path", type=Path, help="Directory to scan recursively")
    parser.add_argument(
        "--localtime", action="store_true",
        help="Convert timestamps to local time instead of UTC (default: UTC)"
    )
    parser.add_argument(
        "--append-only", action="store_true",
        help="Only add metadata fields if they are absent (avoid overwriting existing data)"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)
    process_directory(args.path, use_localtime=args.localtime, append_only=args.append_only)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()

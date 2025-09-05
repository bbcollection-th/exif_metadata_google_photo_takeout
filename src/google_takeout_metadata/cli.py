"""Command line interface."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .processor import process_directory


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Merge Google Takeout metadata into images")
    parser.add_argument("path", type=Path, help="Directory to scan recursively")
    parser.add_argument(
        "--localtime", action="store_true",
        help="Convert timestamps to local time instead of UTC (default: UTC)"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)
    process_directory(args.path, use_localtime=args.localtime)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()

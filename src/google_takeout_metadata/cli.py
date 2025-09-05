"""Command line interface."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .processor import process_directory


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Merge Google Takeout metadata into images")
    parser.add_argument("path", type=Path, help="Directory to scan recursively")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)
    process_directory(args.path)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()

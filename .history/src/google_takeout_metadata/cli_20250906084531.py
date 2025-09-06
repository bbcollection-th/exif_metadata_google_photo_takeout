"""Command line interface."""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

from .processor import process_directory


def main(argv: list[str] | None = None) -> None:
    # Vérifier que exiftool est disponible
    if shutil.which("exiftool") is None:
        logging.error("exiftool not found. Please install it to use this script.")
        sys.exit(1)

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
    parser.add_argument(
        "--clean-sidecars", action="store_true",
        help="Delete JSON sidecar files after successful metadata transfer"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable verbose logging (DEBUG level)"
    )
    args = parser.parse_args(argv)

    # Configuration du logging avec le niveau approprié
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level, 
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    process_directory(args.path, use_localtime=args.localtime, append_only=args.append_only, clean_sidecars=args.clean_sidecars)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()

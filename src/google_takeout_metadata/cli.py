"""Command line interface."""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

from .processor import process_directory
from .processor_batch import process_directory_batch

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
        "--overwrite", action="store_true",
        help="Allow overwriting existing metadata fields (by default, existing metadata is preserved)"
    )
    parser.add_argument(
        "--append-only", action="store_true",
        help=argparse.SUPPRESS  # Cache l'option dépréciée de l'aide
    )
    parser.add_argument(
        "--clean-sidecars", action="store_true",
        help="Delete JSON sidecar files after successful metadata transfer"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable verbose logging (DEBUG level)"
    )
    parser.add_argument(
        "--batch", action="store_true",
        help="Process files in batches"
    )
    args = parser.parse_args(argv)

    # Configuration du logging avec le niveau approprié
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level, 
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    # Gestion de la rétrocompatibilité et validation des options
    if args.append_only and args.overwrite:
        logging.error("Cannot use both --append-only (deprecated) and --overwrite options together")
        sys.exit(1)
    
    if args.append_only:
        logging.warning("--append-only is deprecated and now the default behavior. Use --overwrite to allow overwriting existing metadata.")
    
    if not args.path.is_dir():
        logging.error("The specified path is not a directory: %s", args.path)
        sys.exit(1)
    # Le mode par défaut est maintenant append_only=True (sécurité par défaut)
    # L'option --overwrite permet d'écraser les métadonnées existantes
    append_only = not args.overwrite

    if args.batch:
        process_directory_batch(args.path, use_localtime=args.localtime, append_only=append_only, clean_sidecars=args.clean_sidecars)
    else:
        process_directory(args.path, use_localtime=args.localtime, append_only=append_only, clean_sidecars=args.clean_sidecars)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()

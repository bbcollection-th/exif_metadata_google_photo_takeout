"""High level processing of directories of Google Takeout metadata."""

from __future__ import annotations

from pathlib import Path
import logging

from .sidecar import parse_sidecar
from .exif_writer import write_metadata

logger = logging.getLogger(__name__)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".mp4", ".mov"}


def _is_sidecar_file(path: Path) -> bool:
    suffixes = [s.lower() for s in path.suffixes]
    return len(suffixes) >= 2 and suffixes[-1] == ".json" and suffixes[-2] in IMAGE_EXTS


def process_sidecar_file(json_path: Path) -> None:
    """Process a single ``.json`` sidecar file."""

    meta = parse_sidecar(json_path)
    image_path = json_path.with_name(meta.filename)
    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found for sidecar {json_path}")
    write_metadata(image_path, meta)


def process_directory(root: Path) -> None:
    """Recursively process all sidecar files under ``root``."""

    for json_file in root.rglob("*.json"):
        if not _is_sidecar_file(json_file):
            continue
        try:
            process_sidecar_file(json_file)
        except Exception as exc:  # pragma: no cover - logging
            logger.warning("Failed to process %s: %s", json_file, exc)

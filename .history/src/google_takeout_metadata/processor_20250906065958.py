"""High level processing of directories of Google Takeout metadata."""

from __future__ import annotations

from pathlib import Path
import logging

from .sidecar import parse_sidecar
from .exif_writer import write_metadata

logger = logging.getLogger(__name__)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", "heif", ".avif", ".mp4", ".mov", "m4v", ".3gp"}


def _is_sidecar_file(path: Path) -> bool:
    """Check if a file could be a Google Photos sidecar JSON file.
    
    This function uses a permissive approach since parse_sidecar() does
    strong validation by matching the title field with the expected filename.
    """
    if not path.suffix.lower() == ".json":
        return False
    
    suffixes = [s.lower() for s in path.suffixes]
    
    # Standard pattern: photo.jpg.json
    if len(suffixes) >= 2 and suffixes[-2] in IMAGE_EXTS:
        return True
    
    # Older pattern: photo.json (less specific but validated later)
    # Only consider this if the base name without .json could be an image
    stem_parts = path.stem.split('.')
    if len(stem_parts) >= 2:
        potential_ext = '.' + stem_parts[-1].lower()
        if potential_ext in IMAGE_EXTS:
            return True
    
    return False


def process_sidecar_file(json_path: Path, use_localtime: bool = False) -> None:
    """Process a single ``.json`` sidecar file."""

    meta = parse_sidecar(json_path)
    image_path = json_path.with_name(meta.filename)
    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found for sidecar {json_path}")
    write_metadata(image_path, meta, use_localtime=use_localtime)


def process_directory(root: Path, use_localtime: bool = False) -> None:
    """Recursively process all sidecar files under ``root``."""
    count = 0
    for json_file in root.rglob("*.json"):
        
        if not _is_sidecar_file(json_file):
            continue
        count += 1
        try:
            process_sidecar_file(json_file, use_localtime=use_localtime)
        except (FileNotFoundError, ValueError, RuntimeError) as exc:  # pragma: no cover - logging
            logger.warning("Failed to process %s: %s", json_file, exc, exc_info=True)
    logger.info("Processed %d sidecar files under %s", count, root)
    if count == 0:
        logger.warning("No sidecar files found under %s", root)
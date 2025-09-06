"""High level processing of directories of Google Takeout metadata."""

from __future__ import annotations

from pathlib import Path
import logging
import json
import subprocess

from .sidecar import parse_sidecar, find_albums_for_directory
from .exif_writer import write_metadata

logger = logging.getLogger(__name__)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", "heif", ".avif", ".mp4", ".mov", "m4v", ".3gp"}


def _is_sidecar_file(path: Path) -> bool:
    """Check if a file could be a Google Photos sidecar JSON file.
    
    This function uses a permissive approach since parse_sidecar() does
    strong validation by matching the title field with the expected filename.
    
    Supports both formats:
    - New format: photo.jpg.supplemental-metadata.json
    - Legacy format: photo.jpg.json
    """
    if not path.suffix.lower() == ".json":
        return False
    
    suffixes = [s.lower() for s in path.suffixes]
    
    # New Google Takeout format: photo.jpg.supplemental-metadata.json
    if len(suffixes) >= 3 and suffixes[-2] == ".supplemental-metadata" and suffixes[-3] in IMAGE_EXTS:
        return True
    
    # Legacy pattern: photo.jpg.json
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


def process_sidecar_file(json_path: Path, use_localtime: bool = False, append_only: bool = False, clean_sidecars: bool = False) -> None:
    """Process a single ``.json`` sidecar file.
    
    Args:
        json_path: Path to the JSON sidecar file
        use_localtime: Convert timestamps to local time instead of UTC
        append_only: Only add metadata fields if they are absent
        clean_sidecars: Delete the JSON file after successful processing
    """

    meta = parse_sidecar(json_path)
    
    # Find albums for this directory
    directory_albums = find_albums_for_directory(json_path.parent)
    meta.albums.extend(directory_albums)
    
    image_path = json_path.with_name(meta.filename)
    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found for sidecar {json_path}")
    
    # Write metadata to image
    write_metadata(image_path, meta, use_localtime=use_localtime, append_only=append_only)
    
    # Clean up sidecar file if requested and write was successful
    if clean_sidecars:
        try:
            json_path.unlink()
            logger.info("Deleted sidecar file: %s", json_path)
        except OSError as exc:
            logger.warning("Failed to delete sidecar file %s: %s", json_path, exc)


def process_directory(root: Path, use_localtime: bool = False, append_only: bool = False, clean_sidecars: bool = False) -> None:
    """Recursively process all sidecar files under ``root``.
    
    Args:
        root: Root directory to scan recursively
        use_localtime: Convert timestamps to local time instead of UTC
        append_only: Only add metadata fields if they are absent
        clean_sidecars: Delete JSON files after successful processing
    """
    count = 0
    cleaned_count = 0
    
    for json_file in root.rglob("*.json"):
        
        if not _is_sidecar_file(json_file):
            continue
        count += 1
        try:
            process_sidecar_file(json_file, use_localtime=use_localtime, append_only=append_only, clean_sidecars=clean_sidecars)
            if clean_sidecars:
                cleaned_count += 1
        except (FileNotFoundError, ValueError, RuntimeError) as exc:  # pragma: no cover - logging
            logger.warning("Failed to process %s: %s", json_file, exc, exc_info=True)
    
    logger.info("Processed %d sidecar files under %s", count, root)
    if clean_sidecars and cleaned_count > 0:
        logger.info("Cleaned up %d sidecar files", cleaned_count)
    if count == 0:
        logger.warning("No sidecar files found under %s", root)
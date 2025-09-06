"""High level processing of directories of Google Takeout metadata."""

from __future__ import annotations

from pathlib import Path
import logging
import json
import subprocess

from .sidecar import parse_sidecar, find_albums_for_directory
from .exif_writer import write_metadata

logger = logging.getLogger(__name__)

# Séparer les extensions images et vidéos pour une meilleure cohérence
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".avif"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".3gp"}
ALL_MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS


def detect_file_type(file_path: Path) -> str | None:
    """Detect the actual file type using file command or magic bytes.
    
    Returns:
        The correct file extension (with dot) or None if detection fails
    """
    try:
        # Try using file command first (available on most systems)
        result = subprocess.run(
            ["file", str(file_path)], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        if result.returncode == 0:
            output = result.stdout.lower()
            if "jpeg" in output or "jfif" in output:
                return ".jpg"
            elif "png" in output:
                return ".png"
            elif "gif" in output:
                return ".gif"
            elif "webp" in output:
                return ".webp"
            elif "heic" in output or "heif" in output:
                return ".heic"
            elif "mp4" in output:
                return ".mp4"
            elif "quicktime" in output or "mov" in output:
                return ".mov"
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # Fallback: Try reading magic bytes
    try:
        with open(file_path, "rb") as f:
            header = f.read(16)
            if header.startswith(b'\xff\xd8\xff'):
                return ".jpg"
            elif header.startswith(b'\x89PNG\r\n\x1a\n'):
                return ".png"
            elif header.startswith(b'GIF8'):
                return ".gif"
            elif header.startswith(b'RIFF') and b'WEBP' in header:
                return ".webp"
            elif header[4:8] == b'ftyp':
                if b'heic' in header[:16] or b'mif1' in header[:16]:
                    return ".heic"
                elif b'mp4' in header[:16] or b'isom' in header[:16]:
                    return ".mp4"
    except (OSError, IOError):
        pass
    
    return None


def fix_file_extension_mismatch(image_path: Path, json_path: Path) -> tuple[Path, Path]:
    """Fix file extension mismatch by renaming files and updating JSON content.
    
    Args:
        image_path: Path to the image/video file
        json_path: Path to the corresponding JSON sidecar file
        
    Returns:
        Tuple of (new_image_path, new_json_path)
    """
    # Detect the actual file type
    actual_ext = detect_file_type(image_path)
    if not actual_ext or actual_ext == image_path.suffix.lower():
        # No mismatch detected or detection failed
        return image_path, json_path
    
    # Create new paths with correct extension
    new_image_path = image_path.with_suffix(actual_ext)
    new_json_path = json_path.with_name(new_image_path.name + ".supplemental-metadata.json")
    
    logger.info("Detected extension mismatch for %s: should be %s", image_path, actual_ext)
    
    try:
        # Rename the image file
        image_path.rename(new_image_path)
        logger.info("Renamed %s to %s", image_path, new_image_path)
        
        # Update JSON content and rename JSON file
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        # Update the title field
        json_data['title'] = new_image_path.name
        
        # Write updated JSON to new location
        with open(new_json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        # Remove old JSON file
        json_path.unlink()
        logger.info("Updated and renamed JSON: %s to %s", json_path, new_json_path)
        
        return new_image_path, new_json_path
        
    except (OSError, IOError, json.JSONDecodeError) as exc:
        logger.warning("Failed to fix extension mismatch for %s: %s", image_path, exc)
        return image_path, json_path


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
    
    # Try to write metadata to image
    try:
        write_metadata(image_path, meta, use_localtime=use_localtime, append_only=append_only)
        current_json_path = json_path
    except RuntimeError as exc:
        # Check if this might be an extension mismatch error
        error_msg = str(exc).lower()
        if ("not a valid png" in error_msg and "looks more like a jpeg" in error_msg) or \
           ("not a valid jpeg" in error_msg and "looks more like a png" in error_msg) or \
           ("charset option" in error_msg):
            
            logger.info("Attempting to fix file extension mismatch for %s", image_path)
            
            # Try to fix the extension mismatch
            fixed_image_path, fixed_json_path = fix_file_extension_mismatch(image_path, json_path)
            
            if fixed_image_path != image_path:
                # Files were renamed, re-parse the updated JSON and retry
                meta = parse_sidecar(fixed_json_path)
                directory_albums = find_albums_for_directory(fixed_json_path.parent)
                meta.albums.extend(directory_albums)
                
                write_metadata(fixed_image_path, meta, use_localtime=use_localtime, append_only=append_only)
                current_json_path = fixed_json_path
                logger.info("Successfully processed %s after fixing extension", fixed_image_path)
            else:
                # Extension fix failed, re-raise original error
                raise
        else:
            # Not an extension mismatch error, re-raise
            raise
    
    # Clean up sidecar file if requested and write was successful
    if clean_sidecars:
        try:
            current_json_path.unlink()
            logger.info("Deleted sidecar file: %s", current_json_path)
        except OSError as exc:
            logger.warning("Failed to delete sidecar file %s: %s", current_json_path, exc)


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
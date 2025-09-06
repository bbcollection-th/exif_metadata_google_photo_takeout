import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple

from .exif_writer import build_exiftool_args
from .sidecar import find_albums_for_directory, parse_sidecar
from .processor import IMAGE_EXTS, VIDEO_EXTS, ALL_MEDIA_EXTS, detect_file_type, fix_file_extension_mismatch, _is_sidecar_file 


logger = logging.getLogger(__name__)



def process_batch(batch: List[Tuple[Path, Path, List[str]]], clean_sidecars: bool) -> int:
    """
    Process a batch of files using exiftool with an argfile.
    """
    if not batch:
        return 0

    argfile_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8', suffix=".txt") as argfile:
            argfile_path = argfile.name
        
        with open(argfile_path, 'w', encoding='utf-8') as argfile:
            for media_path, _, args in batch:
                for arg in args:
                    argfile.write(f"{arg}\n")
                argfile.write(f"{media_path}\n")
                argfile.write("-execute\n")

        logger.info(f"Processing a batch of {len(batch)} files...")

        cmd = [
            "exiftool",
            "-overwrite_original",
            "-charset", "filename=UTF8",
            "-charset", "iptc=UTF8",
            "-charset", "exif=UTF8",
            "-@", argfile_path,
        ]
        
        timeout_seconds = 60 + (len(batch) * 5)
        subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=timeout_seconds, encoding='utf-8'
        )

        if clean_sidecars:
            for _, json_path, _ in batch:
                try:
                    json_path.unlink()
                except OSError as e:
                    logger.warning(f"Failed to delete sidecar file {json_path}: {e}")
        
        return len(batch)

    except FileNotFoundError as exc:
        raise RuntimeError("exiftool not found") from exc
    except subprocess.CalledProcessError as exc:
        logger.error(f"exiftool failed for batch. Stderr: {exc.stderr or ''}. Stdout: {exc.stdout or ''}")
        return 0
    finally:
        if argfile_path and Path(argfile_path).exists():
            Path(argfile_path).unlink()


def process_directory_batch(root: Path, use_localtime: bool = False, append_only: bool = True, clean_sidecars: bool = False) -> None:
    """
    Recursively process all sidecar files under ``root`` in batches.
    """
    batch: List[Tuple[Path, Path, List[str]]] = []
    BATCH_SIZE = 100
    total_processed = 0
    
    sidecar_files = [path for path in root.rglob("*.json") if _is_sidecar_file(path)]
    total_sidecars = len(sidecar_files)
    
    if total_sidecars == 0:
        logger.warning("No sidecar files found under %s", root)
        return

    for json_path in sidecar_files:
        try:
            meta = parse_sidecar(json_path)
            
            directory_albums = find_albums_for_directory(json_path.parent)
            meta.albums.extend(directory_albums)
            
            media_path = json_path.with_name(meta.filename)
            if not media_path.exists():
                logger.warning(f"Media file not found for sidecar {json_path}, skipping.")
                continue

            fixed_media_path, fixed_json_path = fix_file_extension_mismatch(media_path, json_path)
            if fixed_json_path != json_path:
                meta = parse_sidecar(fixed_json_path)
                meta.albums.extend(find_albums_for_directory(fixed_json_path.parent))
            
            args = build_exiftool_args(
                meta, media_path=fixed_media_path, use_localtime=use_localtime, append_only=append_only
            )

            if args:
                batch.append((fixed_media_path, fixed_json_path, args))

            if len(batch) >= BATCH_SIZE:
                processed_count = process_batch(batch, clean_sidecars)
                total_processed += processed_count
                batch = []

        except (ValueError, RuntimeError) as exc:
            logger.warning("Failed to prepare %s for batch processing: %s", json_path, exc)

    if batch:
        processed_count = process_batch(batch, clean_sidecars)
        total_processed += processed_count

    logger.info("Processed %d / %d sidecar files under %s", total_processed, total_sidecars, root)
    if clean_sidecars and total_processed > 0:
        logger.info("Cleaned up %d sidecar files", total_processed)

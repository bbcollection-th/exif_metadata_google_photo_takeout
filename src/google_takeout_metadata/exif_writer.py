# Fichier : src/google_takeout_metadata/exif_writer.py
# REMPLACEZ TOUT LE CONTENU DE VOTRE FICHIER PAR CECI

import subprocess
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from .sidecar import SidecarData

logger = logging.getLogger(__name__)

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".3gp"}

def _is_video_file(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS

def _fmt_dt(ts: int | None, use_localtime: bool) -> str | None:
    if ts is None:
        return None
    dt = datetime.fromtimestamp(ts) if use_localtime else datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y:%m:%d %H:%M:%S")

def build_exiftool_args(meta: SidecarData, media_path: Path | None = None, use_localtime: bool = False, append_only: bool = True) -> List[str]:
    """Construit la liste des arguments pour exiftool avec syntaxe correcte."""
    args: List[str] = []

    # --- Configuration ---
    if media_path and _is_video_file(media_path):
        args.extend(["-api", "QuickTimeUTC=1"])
    
    # --- Description ---
    if meta.description:
        safe_desc = meta.description.replace("\r", " ").replace("\n", " ").strip()
        if append_only:
            args.extend(["-if", "not $EXIF:ImageDescription", "-EXIF:ImageDescription=", safe_desc])
            args.extend(["-if", "not $XMP-dc:Description", "-XMP-dc:Description=", safe_desc])
            args.extend(["-if", "not $IPTC:Caption-Abstract", "-IPTC:Caption-Abstract=", safe_desc])
            if media_path and _is_video_file(media_path):
                args.extend(["-if", "not $Keys:Description", "-Keys:Description=", safe_desc])
        else:
            args.extend(["-EXIF:ImageDescription=", safe_desc])
            args.extend(["-XMP-dc:Description=", safe_desc])
            args.extend(["-IPTC:Caption-Abstract=", safe_desc])
            if media_path and _is_video_file(media_path):
                args.extend(["-Keys:Description=", safe_desc])

    # --- Personnes et Albums ---
    all_keywords = (meta.people or []) + [f"Album: {a}" for a in (meta.albums or [])]
    
    if append_only:
        if meta.people or meta.albums:
            args.extend(["-api", "NoDups=1"])
        if meta.people:
            for person in meta.people:
                args.extend(["-XMP-iptcExt:PersonInImage+=", person])
        if all_keywords:
            for keyword in all_keywords:
                args.extend(["-XMP-dc:Subject+=", keyword])
                args.extend(["-IPTC:Keywords+=", keyword])
    else:
        # Écrasement : vider explicitement, puis remplir
        args.extend(["-XMP-iptcExt:PersonInImage=", ""])
        if meta.people:
            for person in meta.people:
                args.extend(["-XMP-iptcExt:PersonInImage+=", person])
        
        args.extend(["-XMP-dc:Subject=", "", "-IPTC:Keywords=", ""])
        if all_keywords:
            for keyword in all_keywords:
                args.extend(["-XMP-dc:Subject+=", keyword])
                args.extend(["-IPTC:Keywords+=", keyword])

    # --- Rating/Favoris ---
    if meta.favorite:
        if append_only:
            args.extend(["-if", "not $XMP:Rating", "-XMP:Rating=", "5"])
        else:
            args.extend(["-XMP:Rating=", "5"])
            
    # --- Dates ---
    if (s := _fmt_dt(meta.taken_at, use_localtime)):
        if append_only:
            args.extend(["-if", "not $DateTimeOriginal", "-DateTimeOriginal=", s])
            if media_path and _is_video_file(media_path):
                args.extend(["-if", "not $QuickTime:CreateDate", "-QuickTime:CreateDate=", s])
        else:
            args.extend(["-DateTimeOriginal=", s])
            if media_path and _is_video_file(media_path):
                args.extend(["-QuickTime:CreateDate=", s])

    base_ts = meta.created_at or meta.taken_at
    if (s := _fmt_dt(base_ts, use_localtime)):
        if append_only:
            args.extend(["-if", "not $CreateDate", "-CreateDate=", s])
            args.extend(["-if", "not $ModifyDate", "-ModifyDate=", s])
            if media_path and _is_video_file(media_path):
                args.extend(["-if", "not $QuickTime:ModifyDate", "-QuickTime:ModifyDate=", s])
        else:
            args.extend(["-CreateDate=", s])
            args.extend(["-ModifyDate=", s])
            if media_path and _is_video_file(media_path):
                args.extend(["-QuickTime:ModifyDate=", s])
    
    # --- GPS ---
    if meta.latitude is not None and meta.longitude is not None:
        lat = str(abs(meta.latitude))
        lon = str(abs(meta.longitude))
        lat_ref = "N" if meta.latitude >= 0 else "S"
        lon_ref = "E" if meta.longitude >= 0 else "W"
        gps_coords = f"{meta.latitude},{meta.longitude}"

        if append_only:
            args.extend(["-if", "not $GPSLatitude", "-GPSLatitude=", lat])
            args.extend(["-if", "not $GPSLatitudeRef", "-GPSLatitudeRef=", lat_ref])
            args.extend(["-if", "not $GPSLongitude", "-GPSLongitude=", lon])
            args.extend(["-if", "not $GPSLongitudeRef", "-GPSLongitudeRef=", lon_ref])
            if media_path and _is_video_file(media_path):
                args.extend(["-if", "not $QuickTime:GPSCoordinates", "-QuickTime:GPSCoordinates=", gps_coords])
                args.extend(["-if", "not $Keys:Location", "-Keys:Location=", gps_coords])
        else:
            args.extend(["-GPSLatitude=", lat])
            args.extend(["-GPSLatitudeRef=", lat_ref])
            args.extend(["-GPSLongitude=", lon])
            args.extend(["-GPSLongitudeRef=", lon_ref])
            if media_path and _is_video_file(media_path):
                args.extend(["-QuickTime:GPSCoordinates=", gps_coords])
                args.extend(["-Keys:Location=", gps_coords])

        if meta.altitude is not None:
            alt = str(abs(meta.altitude))
            alt_ref = "1" if meta.altitude < 0 else "0"
            if append_only:
                args.extend(["-if", "not $GPSAltitude", "-GPSAltitude=", alt])
                args.extend(["-if", "not $GPSAltitudeRef", "-GPSAltitudeRef=", alt_ref])
            else:
                args.extend(["-GPSAltitude=", alt])
                args.extend(["-GPSAltitudeRef=", alt_ref])

    return args

def write_metadata(media_path: Path, meta: SidecarData, use_localtime: bool = False, append_only: bool = True) -> None:
    """Écrit les métadonnées sur un média en utilisant un seul appel à ExifTool."""
    args = build_exiftool_args(meta, media_path, use_localtime, append_only)
    if args:
        _run_exiftool_command(media_path, args, _append_only=append_only)

def _run_exiftool_command(media_path: Path, args: list[str], _append_only: bool) -> None:
    """Exécute une commande exiftool avec les arguments fournis."""
    if not args:
        return
    
    print(f"DEBUG: Arguments pour {media_path.name}: {args}")
    
    cmd = [
        "exiftool",
        "-overwrite_original",
        "-charset", "filename=UTF8",
        "-charset", "iptc=UTF8",
        "-charset", "exif=UTF8",
    ]
    
    # Ajouter les arguments métadonnées
    cmd.extend(args)
    # Ajouter le fichier à traiter
    cmd.append(str(media_path))
    
    print(f"DEBUG: Commande complète: {cmd}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60, encoding='utf-8')
        logger.debug("Exiftool output for %s: %s", media_path.name, result.stdout.strip())
        print(f"DEBUG: Succès - stdout: {result.stdout}")

    except FileNotFoundError as exc:
        raise RuntimeError("exiftool introuvable") from exc
    except subprocess.CalledProcessError as exc:
        print(f"DEBUG: Erreur subprocess - stderr: {exc.stderr}, stdout: {exc.stdout}")
        if _append_only and exc.returncode == 2:
            logger.info(f"Aucune métadonnée manquante à écrire pour {media_path.name} (comportement normal en mode append-only).")
            return
            
        error_msg = f"exiftool a échoué pour {media_path.name} (code {exc.returncode}): {exc.stderr.strip() or exc.stdout.strip()}"
        raise RuntimeError(error_msg) from exc
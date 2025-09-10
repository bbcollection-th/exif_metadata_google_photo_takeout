# Fichier : src/google_takeout_metadata/exif_writer.py

import subprocess
import logging
from datetime import datetime, timezone
from pathlib import Path

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

def write_metadata(media_path: Path, meta: SidecarData, use_localtime: bool = False, append_only: bool = True) -> None:
    """Écrit les métadonnées sur un média en utilisant ExifTool."""
    
    if append_only:
        # Mode append-only : approche hybride en 3 étapes
        # 1. Tags à valeur unique avec -wm cg (créer seulement si vide)
        # 2. Tags de liste avec += (peut créer des doublons temporairement)
        # 3. Nettoyage avec NoDups pour éliminer les doublons
        
        # Étape 1 : Tags à valeur unique (Description, Dates, GPS, Rating)
        single_args = build_exiftool_args(meta, media_path, use_localtime, append_only=True)
        
        # Exécuter la commande pour tags uniques
        if single_args:
            _run_exiftool_command(media_path, single_args, _append_only=True)
        
        # Étape 2 : Tags de liste avec accumulation (peut créer des doublons)
        list_args = []
        all_keywords = (meta.people or []) + [f"Album: {a}" for a in (meta.albums or [])]
        
        if meta.people:
            for person in meta.people:
                list_args.append(f"-XMP-iptcExt:PersonInImage+={person}")
        
        if all_keywords:
            for keyword in all_keywords:
                list_args.append(f"-XMP-dc:Subject+={keyword}")
                list_args.append(f"-IPTC:Keywords+={keyword}")
        
        # Exécuter la commande pour tags de liste (avec doublons possibles)
        if list_args:
            _run_exiftool_command(media_path, list_args, _append_only=True)
            
            # Étape 3 : Nettoyage des doublons avec fonction NoDups
            _cleanup_duplicates(media_path)
            
    else:
        # Mode écrasement : utiliser build_exiftool_args directement
        all_args = build_exiftool_args(meta, media_path, use_localtime, append_only=False)
        
        # Exécuter en mode écrasement
        if all_args:
            _run_exiftool_command(media_path, all_args, _append_only=False)

def _cleanup_duplicates(media_path: Path) -> None:
    """Nettoie les doublons dans les tags de liste en utilisant l'API NoDups d'ExifTool."""
    cleanup_cmd = [
        "exiftool",
        "-tagsfromfile", "@",
        "-XMP-iptcExt:PersonInImage",
        "-XMP-dc:Subject", 
        "-IPTC:Keywords",
        "-api", "nodups",
        "-overwrite_original",
        str(media_path)
    ]
    
    try:
        result = subprocess.run(cleanup_cmd, capture_output=True, text=True, timeout=30, encoding='utf-8')
        logger.debug("Cleanup duplicates for %s: %s", media_path.name, result.stdout.strip())
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("Échec du nettoyage des doublons pour %s: %s", media_path.name, exc)

def build_exiftool_args(meta: SidecarData, media_path: Path = None, use_localtime: bool = False, append_only: bool = True) -> list[str]:
    """Construit les arguments exiftool pour traiter un fichier média avec les métadonnées fournies.
    
    Note: En mode append_only=True, cette fonction inclut tous les tags mais peut créer des doublons
    dans les tags de liste. Pour un traitement optimal sans doublons, utilisez write_metadata() directement.
    """
    args = []
    
    if append_only:
        # Mode append-only : inclusion de tous les tags avec -wm cg pour compatibilité batch
        # Note: Cela peut créer des doublons dans les tags de liste
        if media_path and _is_video_file(media_path):
            args.extend(["-api", "QuickTimeUTC=1"])
        args.extend(["-wm", "cg"])
        
        # Description
        if meta.description:
            safe_desc = meta.description.replace("\r", " ").replace("\n", " ").strip()
            args.extend([f"-EXIF:ImageDescription={safe_desc}", f"-XMP-dc:Description={safe_desc}", f"-IPTC:Caption-Abstract={safe_desc}"])
            if media_path and _is_video_file(media_path):
                args.append(f"-Keys:Description={safe_desc}")
        
        # Tags de liste avec += (peut créer des doublons en mode batch)
        if meta.people:
            for person in meta.people:
                args.append(f"-XMP-iptcExt:PersonInImage+={person}")
        
        # Mots-clés (personnes + albums)
        all_keywords = (meta.people or []) + [f"Album: {a}" for a in (meta.albums or [])]
        if all_keywords:
            for keyword in all_keywords:
                args.append(f"-XMP-dc:Subject+={keyword}")
                args.append(f"-IPTC:Keywords+={keyword}")
        
        # Dates
        if (s := _fmt_dt(meta.taken_at, use_localtime)):
            args.append(f"-DateTimeOriginal={s}")
            if media_path and _is_video_file(media_path):
                args.append(f"-QuickTime:CreateDate={s}")

        base_ts = meta.created_at or meta.taken_at
        if (s := _fmt_dt(base_ts, use_localtime)):
            args.append(f"-CreateDate={s}")
            args.append(f"-ModifyDate={s}")
            if media_path and _is_video_file(media_path):
                args.append(f"-QuickTime:ModifyDate={s}")
        
        # GPS
        if meta.latitude is not None and meta.longitude is not None:
            lat = str(abs(meta.latitude))
            lon = str(abs(meta.longitude))
            lat_ref = "N" if meta.latitude >= 0 else "S"
            lon_ref = "E" if meta.longitude >= 0 else "W"
            gps_coords = f"{meta.latitude},{meta.longitude}"
            
            args.append(f"-GPSLatitude={lat}")
            args.append(f"-GPSLatitudeRef={lat_ref}")
            args.append(f"-GPSLongitude={lon}")
            args.append(f"-GPSLongitudeRef={lon_ref}")
            if media_path and _is_video_file(media_path):
                args.append(f"-QuickTime:GPSCoordinates={gps_coords}")
                args.append(f"-Keys:Location={gps_coords}")

            if meta.altitude is not None:
                alt = str(abs(meta.altitude))
                alt_ref = "1" if meta.altitude < 0 else "0"
                args.append(f"-GPSAltitude={alt}")
                args.append(f"-GPSAltitudeRef={alt_ref}")
        
        # Rating
        if meta.favorite:
            args.append("-XMP:Rating=5")
            
    else:
        # Mode écrasement : logique complète
        if media_path and _is_video_file(media_path):
            args.extend(["-api", "QuickTimeUTC=1"])
        
        # Description
        if meta.description:
            safe_desc = meta.description.replace("\r", " ").replace("\n", " ").strip()
            args.extend([f"-EXIF:ImageDescription={safe_desc}", f"-XMP-dc:Description={safe_desc}", f"-IPTC:Caption-Abstract={safe_desc}"])
            if media_path and _is_video_file(media_path):
                args.append(f"-Keys:Description={safe_desc}")
        
        # Vider d'abord les listes puis les remplir
        args.extend(["-XMP-iptcExt:PersonInImage=", "-XMP-dc:Subject=", "-IPTC:Keywords="])
        
        # Ajouter les personnes
        if meta.people:
            for person in meta.people:
                args.append(f"-XMP-iptcExt:PersonInImage+={person}")
        
        # Ajouter mots-clés (personnes + albums)
        all_keywords = (meta.people or []) + [f"Album: {a}" for a in (meta.albums or [])]
        if all_keywords:
            for keyword in all_keywords:
                args.append(f"-XMP-dc:Subject+={keyword}")
                args.append(f"-IPTC:Keywords+={keyword}")
        
        # Rating
        if meta.favorite:
            args.append("-XMP:Rating=5")
        
        # Dates
        if (s := _fmt_dt(meta.taken_at, use_localtime)):
            args.append(f"-DateTimeOriginal={s}")
            if media_path and _is_video_file(media_path):
                args.append(f"-QuickTime:CreateDate={s}")

        base_ts = meta.created_at or meta.taken_at
        if (s := _fmt_dt(base_ts, use_localtime)):
            args.append(f"-CreateDate={s}")
            args.append(f"-ModifyDate={s}")
            if media_path and _is_video_file(media_path):
                args.append(f"-QuickTime:ModifyDate={s}")
        
        # GPS
        if meta.latitude is not None and meta.longitude is not None:
            lat = str(abs(meta.latitude))
            lon = str(abs(meta.longitude))
            lat_ref = "N" if meta.latitude >= 0 else "S"
            lon_ref = "E" if meta.longitude >= 0 else "W"
            gps_coords = f"{meta.latitude},{meta.longitude}"
            
            args.append(f"-GPSLatitude={lat}")
            args.append(f"-GPSLatitudeRef={lat_ref}")
            args.append(f"-GPSLongitude={lon}")
            args.append(f"-GPSLongitudeRef={lon_ref}")
            if media_path and _is_video_file(media_path):
                args.append(f"-QuickTime:GPSCoordinates={gps_coords}")
                args.append(f"-Keys:Location={gps_coords}")

            if meta.altitude is not None:
                alt = str(abs(meta.altitude))
                alt_ref = "1" if meta.altitude < 0 else "0"
                args.append(f"-GPSAltitude={alt}")
                args.append(f"-GPSAltitudeRef={alt_ref}")

    return args

def _run_exiftool_command(media_path: Path, args: list[str], _append_only: bool) -> None:
    """Exécute une commande exiftool avec les arguments fournis."""
    if not args:
        return

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

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60, encoding='utf-8')
        logger.debug("Exiftool output for %s: %s", media_path.name, result.stdout.strip())

    except FileNotFoundError as exc:
        raise RuntimeError("exiftool introuvable") from exc
    except subprocess.CalledProcessError as exc:
        if _append_only and exc.returncode == 2:
            logger.info(f"Aucune métadonnée manquante à écrire pour {media_path.name} (comportement normal en mode append-only).")
            return

        error_msg = f"exiftool a échoué pour {media_path.name} (code {exc.returncode}): {exc.stderr.strip() or exc.stdout.strip()}"
        raise RuntimeError(error_msg) from exc
# Fichier : src/google_takeout_metadata/exif_writer.py

import subprocess
import logging
from datetime import datetime, timezone
from pathlib import Path

from .sidecar import SidecarData

logger = logging.getLogger(__name__)

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".3gp"}

# Mots de liaison à garder en minuscules (sauf en début de nom)
SMALL_WORDS = {"de", "du", "des", "la", "le", "les", "van", "von", "da", "di", "of", "and", "der", "den", "het", "el", "al"}

def _is_video_file(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS

def _fmt_dt(ts: int | None, use_localtime: bool) -> str | None:
    if ts is None:
        return None
    dt = datetime.fromtimestamp(ts) if use_localtime else datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y:%m:%d %H:%M:%S")

def normalize_person_name(name: str) -> str:
    """Normaliser les noms de personnes (gestion intelligente de la casse).
    
    Évite .title() brute qui pose problème avec McDonald, O'Connor, etc.
    Gère les mots de liaison (de, du, van, etc.) correctement.
    
    Args:
        name: Nom de personne à normaliser
        
    Returns:
        Nom normalisé avec casse appropriée
    """
    if not name: 
        return ""
    
    parts = [p.strip() for p in name.strip().split()]
    fixed = []
    
    for i, p in enumerate(parts):
        low = p.lower()
        # Mots de liaison en minuscules (sauf en début)
        if i > 0 and low in SMALL_WORDS:
            fixed.append(low)
        # Cas spéciaux : O'Connor, McDonald, etc.
        elif low.startswith("o'") and len(p) > 2:
            fixed.append("O'" + p[2:].capitalize())
        elif low.startswith("mc") and len(p) > 2:
            fixed.append("Mc" + p[2:].capitalize())
        else:
            fixed.append(p[:1].upper() + p[1:].lower())
    
    return " ".join(fixed)

def normalize_keyword(keyword: str) -> str:
    """Normaliser les mots-clés en conservant la majuscule sur chaque mot.
    
    Args:
        keyword: Mot-clé à normaliser
        
    Returns:
        Mot-clé normalisé avec première lettre de chaque mot en majuscule
    """
    if not keyword:
        return ""
    
    parts = [p.strip() for p in keyword.strip().split() if p.strip()]
    # On met la première lettre de chaque partie en majuscule, le reste en minuscule
    return " ".join(p[:1].upper() + p[1:].lower() for p in parts)

def _build_keywords(meta: SidecarData) -> list[str]:
    """Centralise la logique de création des mots-clés à partir des personnes et albums."""
    return (meta.people or []) + [f"Album: {a}" for a in (meta.albums or [])]

def _sanitize_description(desc: str) -> str:
    """Centralise le nettoyage des descriptions pour ExifTool."""
    return desc.replace("\r", " ").replace("\n", " ").strip()

def write_metadata(media_path: Path, meta: SidecarData, use_localtime: bool = False, append_only: bool = True) -> None:
    """Écrit les métadonnées sur un média en utilisant ExifTool."""
    
    if append_only:
        # Mode append-only : utiliser build_exiftool_args qui gère déjà tout avec -wm cg
        args = build_exiftool_args(meta, media_path, use_localtime, append_only=True)
        
        if args:
            _run_exiftool_command(media_path, args, _append_only=True)
            
    else:
        # Mode écrasement : utiliser build_exiftool_args directement
        all_args = build_exiftool_args(meta, media_path, use_localtime, append_only=False)
        
        # Exécuter en mode écrasement
        if all_args:
            _run_exiftool_command(media_path, all_args, _append_only=False)

def build_exiftool_args(meta: SidecarData, media_path: Path = None, use_localtime: bool = False, append_only: bool = True) -> list[str]:
    """Construit les arguments exiftool pour traiter un fichier média avec les métadonnées fournies.
    
    APPROCHE ANTI-DUPLICATION :
    - Pour PersonInImage et mots-clés : utilise -TAG-=val puis -TAG+=val pour garantir zéro doublon
    - Normalisation obligatoire en amont pour éviter "Anthony Vincent" et "anthony vincent"
    - Pas de -wm cg en mode déduplication (incompatible avec -TAG-=)
    
    Args:
        meta: Métadonnées à écrire
        media_path: Chemin du fichier média (optionnel, pour la détection vidéo)
        use_localtime: Utiliser l'heure locale au lieu d'UTC
        append_only: Mode append-only (True) ou mode écrasement complet (False)
    
    Returns:
        Liste des arguments exiftool
    """
    args = []
    
    if append_only:
        # Mode append-only : utilisation différenciée de -wm selon les opérations
        if media_path and _is_video_file(media_path):
            args.extend(["-api", "QuickTimeUTC=1"])
        
        # Description (utiliser -if pour éviter d'écraser si existe déjà)
        if meta.description:
            safe_desc = _sanitize_description(meta.description)
            args.extend(["-wm", "cg"])  # Mode append-only pour description
            args.extend([
                "-if", "not $EXIF:ImageDescription",
                f"-EXIF:ImageDescription={safe_desc}",
                "-if", "not $XMP-dc:Description", 
                f"-XMP-dc:Description={safe_desc}",
                "-if", "not $IPTC:Caption-Abstract",
                f"-IPTC:Caption-Abstract={safe_desc}"
            ])
            if media_path and _is_video_file(media_path):
                args.extend(["-if", "not $Keys:Description", f"-Keys:Description={safe_desc}"])
        
        # PersonInImage - Approche "supprimer puis ajouter" (robuste)
        # ⚠️ SANS -wm cg car incompatible avec -TAG-= (suppression = édition)
        if meta.people:
            # Normalisation obligatoire AVANT écriture pour déduplication
            normalized_people = [normalize_person_name(person) for person in meta.people]
            for person in normalized_people:
                # Supprimer puis ajouter pour garantir zéro doublon
                args.extend([
                    f"-XMP-iptcExt:PersonInImage-={person}",
                    f"-XMP-iptcExt:PersonInImage+={person}"
                ])
        
        # Mots-clés - Approche "supprimer puis ajouter" (robuste)
        # ⚠️ SANS -wm cg car incompatible avec -TAG-= (suppression = édition)
        all_keywords = []
        # Ajouter les personnes normalisées comme mots-clés (même normalisation que PersonInImage)
        if meta.people:
            normalized_people = [normalize_person_name(person) for person in meta.people]
            all_keywords.extend(normalized_people)
        # Ajouter les albums normalisés comme mots-clés
        if meta.albums:
            album_keywords = [f"Album: {normalize_keyword(album)}" for album in meta.albums]
            all_keywords.extend(album_keywords)
            
        if all_keywords:
            # Normalisation des mots-clés
            normalized_keywords = [normalize_keyword(kw) for kw in all_keywords]
            for keyword in normalized_keywords:
                # Supprimer puis ajouter pour garantir zéro doublon
                args.extend([
                    f"-XMP-dc:Subject-={keyword}",
                    f"-XMP-dc:Subject+={keyword}",
                    f"-IPTC:Keywords-={keyword}",
                    f"-IPTC:Keywords+={keyword}"
                ])
        
        # Autres champs (dates, GPS, rating) - Mode append-only avec -wm cg
        args.extend(["-wm", "cg"])  # Réactiver -wm cg pour les champs suivants
        
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
        # Mode écrasement : logique complète SANS déduplication spéciale
        if media_path and _is_video_file(media_path):
            args.extend(["-api", "QuickTimeUTC=1"])
        
        # Description
        if meta.description:
            safe_desc = _sanitize_description(meta.description)
            args.extend([f"-EXIF:ImageDescription={safe_desc}", f"-XMP-dc:Description={safe_desc}", f"-IPTC:Caption-Abstract={safe_desc}"])
            if media_path and _is_video_file(media_path):
                args.append(f"-Keys:Description={safe_desc}")
        
        # Vider d'abord les listes puis les remplir (approche originale)
        args.extend(["-XMP-iptcExt:PersonInImage=", "-XMP-dc:Subject=", "-IPTC:Keywords="])
        
        # Ajouter les personnes normalisées
        if meta.people:
            normalized_people = [normalize_person_name(person) for person in meta.people]
            for person in normalized_people:
                args.append(f"-XMP-iptcExt:PersonInImage+={person}")
        
        # Ajouter mots-clés normalisés (personnes + albums)
        all_keywords = []
        # Ajouter les personnes normalisées comme mots-clés (même normalisation que PersonInImage)
        if meta.people:
            normalized_people = [normalize_person_name(person) for person in meta.people]
            all_keywords.extend(normalized_people)
        # Ajouter les albums normalisés comme mots-clés
        if meta.albums:
            album_keywords = [f"Album: {normalize_keyword(album)}" for album in meta.albums]
            all_keywords.extend(album_keywords)
            
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
    """Exécute une commande exiftool avec les arguments fournis.
    
    Note: L'option -api NoDups=1 n'est plus nécessaire car la déduplication
    est gérée par l'approche "supprimer puis ajouter" (-TAG-=val -TAG+=val).
    """
    if not args:
        return

    cmd = [
        "exiftool",
        "-overwrite_original",
        "-charset", "filename=UTF8",  # ✅ Support Unicode Windows
        "-charset", "iptc=UTF8",      # ✅ Pour écriture IPTC
        "-charset", "exif=UTF8",      # ✅ Pour écriture EXIF
        "-codedcharacterset=utf8",    # ✅ Définit l'encoding UTF-8 pour IPTC (syntaxe correcte)
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
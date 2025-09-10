# Fichier : src/google_takeout_metadata/exif_writer.py

import subprocess
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Iterable

from .sidecar import SidecarData

logger = logging.getLogger(__name__)

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".3gp"}

# === CONSTANTES ET NORMALISATION ===

_SMALL_WORDS = {
    "de", "du", "des", "la", "le", "les", "van", "von", "da", "di", "of", "and",
    "der", "den", "het", "el", "al"
}

def _is_video_file(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS

def _fmt_dt(ts: int | None, use_localtime: bool) -> str | None:
    if ts is None:
        return None
    dt = datetime.fromtimestamp(ts) if use_localtime else datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y:%m:%d %H:%M:%S")

def normalize_person_name(name: str) -> str:
    """Normaliser les noms de personnes (casse intelligente)"""
    if not name:
        return ""
    parts = [p.strip() for p in name.strip().split() if p.strip()]
    fixed: List[str] = []
    for i, p in enumerate(parts):
        low = p.lower()
        if i > 0 and low in _SMALL_WORDS:
            fixed.append(low)
        elif low.startswith("o'") and len(p) > 2:
            fixed.append("O'" + p[2:].capitalize())
        elif low.startswith("mc") and len(p) > 2:
            fixed.append("Mc" + p[2:].capitalize())
        else:
            fixed.append(p[:1].upper() + p[1:].lower())
    return " ".join(fixed)

def normalize_keyword(keyword: str) -> str:
    """Normaliser un mot-clé: trim + Capitalize simple."""
    return keyword.strip().capitalize() if keyword else ""

def _sanitize_description(desc: str) -> str:
    """Centralise le nettoyage des descriptions pour ExifTool."""
    return desc.replace("\r", " ").replace("\n", " ").strip()

# === CONSTRUCTION D'ARGUMENTS MODULAIRE ===

def _quote_if_needed(value: str) -> str:
    """Retourne value cotée si elle contient des espaces pour argfile."""
    return f'"{value}"' if (" " in value or "\t" in value) else value

def build_remove_then_add_args_for_people(people: Iterable[str]) -> List[str]:
    """-TAG-=val puis -TAG+=val pour chaque personne normalisée."""
    args: List[str] = []
    for raw in people:
        person = normalize_person_name(raw)
        if not person:
            continue
        args.extend([
            f"-XMP-iptcExt:PersonInImage-={person}",
            f"-XMP-iptcExt:PersonInImage+={person}"
        ])
    return args

def build_remove_then_add_args_for_keywords(keywords: Iterable[str]) -> List[str]:
    """Construction robuste pour Subject/Keywords avec déduplication."""
    args: List[str] = []
    for raw in keywords:
        kw = normalize_keyword(raw)
        if not kw:
            continue
        # XMP-dc:Subject (bag) + IPTC:Keywords (liste IPTC)
        args.extend([
            f"-XMP-dc:Subject-={kw}",
            f"-XMP-dc:Subject+={kw}",
            f"-IPTC:Keywords-={kw}",
            f"-IPTC:Keywords+={kw}"
        ])
    return args

# === VARIANTE CONDITIONNELLE (POUR PERFORMANCE) ===

def _regex_escape_word(value: str) -> str:
    """Échappe une valeur pour recherche regex avec word boundary."""
    escaped = re.escape(value)
    return rf"\b{escaped}\b"

def build_conditional_add_args_for_people(people: Iterable[str]) -> List[str]:
    """Option conditionnelle: n'ajoute que si absent (pour relances/perf)."""
    args: List[str] = []
    for raw in people:
        person = normalize_person_name(raw)
        if not person:
            continue
        regex = _regex_escape_word(person)
        args.extend([
            "-if", f"not $XMP-iptcExt:PersonInImage=~/{regex}/i",
            f"-XMP-iptcExt:PersonInImage+={person}"
        ])
    return args

def build_conditional_add_args_for_keywords(keywords: Iterable[str]) -> List[str]:
    """Option conditionnelle pour keywords."""
    args: List[str] = []
    for raw in keywords:
        kw = normalize_keyword(raw)
        if not kw:
            continue
        regex = _regex_escape_word(kw)
        args.extend([
            "-if", f"not $XMP-dc:Subject=~/{regex}/i",
            f"-XMP-dc:Subject+={kw}",
            "-if", f"not $IPTC:Keywords=~/{regex}/i",
            f"-IPTC:Keywords+={kw}"
        ])
    return args

# === CONSTRUCTION DES ARGUMENTS PRINCIPAUX ===

def build_people_keywords_args(meta: SidecarData, *, conditional_mode: bool = False) -> List[str]:
    """Construit les arguments pour PersonInImage et Keywords selon la stratégie choisie."""
    args: List[str] = []
    
    # PersonInImage
    if meta.people:
        if conditional_mode:
            args.extend(build_conditional_add_args_for_people(meta.people))
        else:
            args.extend(build_remove_then_add_args_for_people(meta.people))
    
    # Keywords (personnes + albums)
    all_keywords = []
    if meta.people:
        # Ajouter les personnes normalisées comme mots-clés
        normalized_people = [normalize_person_name(person) for person in meta.people]
        all_keywords.extend(normalized_people)
    if meta.albums:
        # Ajouter les albums avec préfixe
        album_keywords = [f"Album: {normalize_keyword(album)}" for album in meta.albums]
        all_keywords.extend(album_keywords)
    
    if all_keywords:
        if conditional_mode:
            args.extend(build_conditional_add_args_for_keywords(all_keywords))
        else:
            args.extend(build_remove_then_add_args_for_keywords(all_keywords))
    
    return args

def build_description_args(meta: SidecarData, *, conditional_mode: bool = False) -> List[str]:
    """Construit les arguments pour la description."""
    args: List[str] = []
    
    if not meta.description:
        return args
    
    safe_desc = _sanitize_description(meta.description)
    
    if conditional_mode:
        # Mode conditionnel : n'écrire que si absent
        args.extend(["-wm", "cg"])  # Mode append-only pour description
        args.extend([
            "-if", "not $EXIF:ImageDescription",
            f"-EXIF:ImageDescription={safe_desc}",
            "-if", "not $XMP-dc:Description", 
            f"-XMP-dc:Description={safe_desc}",
            "-if", "not $IPTC:Caption-Abstract",
            f"-IPTC:Caption-Abstract={safe_desc}"
        ])
    else:
        # Mode écrasement ou append-only simple
        args.extend(["-wm", "cg"])
        args.extend([
            f"-EXIF:ImageDescription={safe_desc}",
            f"-XMP-dc:Description={safe_desc}",
            f"-IPTC:Caption-Abstract={safe_desc}"
        ])
    
    return args

def build_datetime_args(meta: SidecarData, use_localtime: bool, is_video: bool) -> List[str]:
    """Construit les arguments pour les dates."""
    args: List[str] = []
    
    # Dates
    if (s := _fmt_dt(meta.taken_at, use_localtime)):
        args.append(f"-DateTimeOriginal={s}")
        if is_video:
            args.append(f"-QuickTime:CreateDate={s}")

    base_ts = meta.created_at or meta.taken_at
    if (s := _fmt_dt(base_ts, use_localtime)):
        args.append(f"-CreateDate={s}")
        args.append(f"-ModifyDate={s}")
    
    return args

def build_gps_args(meta: SidecarData) -> List[str]:
    """Construit les arguments pour GPS."""
    args: List[str] = []
    
    if meta.latitude is not None and meta.longitude is not None:
        args.extend([
            f"-GPS:GPSLatitude={meta.latitude}",
            f"-GPS:GPSLongitude={meta.longitude}",
        ])
        if meta.altitude is not None:
            args.append(f"-GPS:GPSAltitude={meta.altitude}")
    
    return args

def build_rating_args(meta: SidecarData) -> List[str]:
    """Construit les arguments pour le rating."""
    args: List[str] = []
    
    if meta.favorite:
        args.append("-XMP-xmp:Rating=5")
    
    return args

# === FONCTION PRINCIPALE REFACTORISÉE ===

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
    is_video = media_path and _is_video_file(media_path)
    
    if is_video:
        args.extend(["-api", "QuickTimeUTC=1"])
    
    if append_only:
        # Mode append-only avec approche robuste pour les listes
        
        # Description avec mode conditionnel (append-only)
        args.extend(build_description_args(meta, conditional_mode=True))
        
        # PersonInImage et Keywords avec approche robuste (supprimer-puis-ajouter)
        # IMPORTANT: On utilise conditional_mode=False pour la déduplication robuste
        args.extend(build_people_keywords_args(meta, conditional_mode=False))
        
        # Autres champs avec mode append-only classique
        args.extend(["-wm", "cg"])  # Réactiver pour les champs suivants
        
        # Dates
        args.extend(build_datetime_args(meta, use_localtime, is_video))
        
        # Vidéo spécifique
        if is_video and meta.description:
            safe_desc = _sanitize_description(meta.description)
            args.append(f"-Keys:Description={safe_desc}")
        
        # GPS
        args.extend(build_gps_args(meta))
        
        # Rating
        args.extend(build_rating_args(meta))
        
    else:
        # Mode écrasement : pas de -wm cg, pas de conditions
        
        # Description
        args.extend(build_description_args(meta, conditional_mode=False))
        
        # PersonInImage et Keywords (mode robuste)
        args.extend(build_people_keywords_args(meta, conditional_mode=False))
        
        # Dates
        args.extend(build_datetime_args(meta, use_localtime, is_video))
        
        # Vidéo spécifique
        if is_video and meta.description:
            safe_desc = _sanitize_description(meta.description)
            args.append(f"-Keys:Description={safe_desc}")
        
        # GPS
        args.extend(build_gps_args(meta))
        
        # Rating
        args.extend(build_rating_args(meta))
    
    return args

# === FONCTIONS EXISTANTES PRÉSERVÉES ===

def _run_exiftool_command(media_path: Path, args: list[str], _append_only: bool = True) -> None:
    """Exécute une commande exiftool avec gestion d'erreurs."""
    cmd = ["exiftool", "-overwrite_original", "-charset", "filename=UTF8"]
    
    if not _append_only:
        # En mode écrasement, on peut utiliser des options plus agressives
        pass
    
    cmd.extend(args)
    cmd.append(str(media_path))
    
    logger.debug(f"Commande exiftool : {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30, encoding='utf-8')
        if result.stdout.strip():
            logger.debug(f"exiftool stdout: {result.stdout.strip()}")
        if result.stderr.strip():
            logger.warning(f"exiftool stderr: {result.stderr.strip()}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Erreur exiftool pour {media_path}: code {e.returncode}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")
        raise
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout exiftool pour {media_path}")
        raise

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

# Fonctions utilitaires héritées

def _build_keywords(meta: SidecarData) -> list[str]:
    """Centralise la logique de création des mots-clés à partir des personnes et albums."""
    return (meta.people or []) + [f"Album: {a}" for a in (meta.albums or [])]

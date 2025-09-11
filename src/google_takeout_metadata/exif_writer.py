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
    "der", "den", "het", "el", "al", "bin", "ibn", "af", "zu", "ben", "ap", "abu", "binti", "bint", "della", "delle", "dalla", "delle", "del", "dos", "das", "do", "mac", "fitz"
}
def get_all_keywords(meta: SidecarData) -> List[str]:
    """Centralise la logique de création des mots-clés à partir des personnes et albums.
    
    Retourne les mots-clés normalisés :
    - Personnes normalisées avec normalize_person_name
    - Albums Google Photos préfixés 'Album: ' et normalisés avec normalize_keyword
    
    Note: local_folder_name n'est PAS inclus ici car il est traité comme application source
    dans build_source_app_args, pas comme un album.
    """
    keywords = []
    
    # Ajouter les personnes normalisées comme mots-clés
    if meta.people:
        normalized_people = [normalize_person_name(person) for person in meta.people]
        keywords.extend(normalized_people)
    
    # Ajouter les albums Google Photos avec préfixe et normalisation
    if meta.albums:
        album_keywords = [f"Album: {normalize_keyword(album)}" for album in meta.albums]
        keywords.extend(album_keywords)
    
    return keywords

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
    """Normaliser un mot-clé: trim + capitaliser chaque mot."""
    if not keyword:
        return ""
    parts = [p.strip() for p in keyword.strip().split() if p.strip()]
    # Capitaliser chaque partie (similaire à normalize_person_name mais plus simple)
    return " ".join(p[:1].upper() + p[1:].lower() for p in parts)

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
        add_remove_then_add(args, "XMP-iptcExt:PersonInImage", person)
    return args

def build_remove_then_add_args_for_keywords(keywords: Iterable[str]) -> List[str]:
    """Construction robuste pour Subject/Keywords avec déduplication.
    
    ATTENTION: Les keywords sont supposés déjà normalisés (personnes avec normalize_person_name, 
    albums avec normalize_keyword). Ne pas normaliser à nouveau.
    """
    args: List[str] = []
    for kw in keywords:
        if not kw.strip():  # Ignorer les valeurs vides
            continue
        # XMP-dc:Subject (bag) + IPTC:Keywords (liste IPTC)
        add_remove_then_add(args, "XMP-dc:Subject", kw)
        add_remove_then_add(args, "IPTC:Keywords", kw)
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

def build_overwrite_args_for_people(people: Iterable[str]) -> List[str]:
    """Arguments mode overwrite : vider puis ajouter chaque personne."""
    args: List[str] = []
    if people:
        # Vider d'abord
        args.append("-XMP-iptcExt:PersonInImage=")
        # Puis ajouter chaque personne normalisée
        for raw in people:
            person = normalize_person_name(raw)
            if person:
                args.append(f"-XMP-iptcExt:PersonInImage+={person}")
    return args

def build_overwrite_args_for_keywords(keywords: Iterable[str]) -> List[str]:
    """Arguments mode overwrite : vider puis ajouter chaque keyword."""
    args: List[str] = []
    if keywords:
        # Vider d'abord
        args.extend(["-XMP-dc:Subject=", "-IPTC:Keywords="])
        # Puis ajouter chaque keyword 
        for kw in keywords:
            if kw.strip():
                args.extend([f"-XMP-dc:Subject+={kw}", f"-IPTC:Keywords+={kw}"])
    return args

def build_conditional_add_args_for_keywords(keywords: Iterable[str]) -> List[str]:
    """Option conditionnelle pour keywords.
    
    ATTENTION: Les keywords sont supposés déjà normalisés.
    """
    args: List[str] = []
    for kw in keywords:
        if not kw.strip():
            continue
        regex = _regex_escape_word(kw)
        args.extend([
            "-if", f"not $XMP-dc:Subject=~/{regex}/i",
            f"-XMP-dc:Subject+={kw}",
            "-if", f"not $IPTC:Keywords=~/{regex}/i",
            f"-IPTC:Keywords+={kw}"
        ])
    return args

# === HELPER POUR GARANTIR L'ORDRE SUPPRIMER-PUIS-AJOUTER ===

def add_remove_then_add(args: List[str], tag: str, value: str) -> None:
    """Helper pour garantir l'ordre supprime puis ajoute et éviter les coquilles.
    
    APPROCHE ROBUSTE (NETTOYAGE) :
    Implémente la sémantique -TAG-=val puis -TAG+=val qui :
    - Supprime toutes les occurrences de 'val' dans le tag
    - Puis ajoute une seule occurrence de 'val'
    - Résultat : zéro doublon garanti, idempotent
    - Compatible avec -api NoDups=1 pour déduplication intra-lot
    
    Args:
        args: Liste d'arguments à laquelle ajouter
        tag: Tag exiftool (ex: "XMP-iptcExt:PersonInImage")  
        value: Valeur à supprimer puis ajouter
    """
    args.extend([f"-{tag}-={value}", f"-{tag}+={value}"])

# === CONSTRUCTION DES ARGUMENTS PRINCIPAUX ===

def build_people_keywords_args(meta: SidecarData, *, conditional_mode: bool = False, overwrite_mode: bool = False) -> List[str]:
    """Construit les arguments pour PersonInImage et Keywords selon la stratégie choisie."""
    args: List[str] = []
    
    # PersonInImage
    if meta.people:
        if overwrite_mode:
            args.extend(build_overwrite_args_for_people(meta.people))
        elif conditional_mode:
            args.extend(build_conditional_add_args_for_people(meta.people))
        else:
            args.extend(build_remove_then_add_args_for_people(meta.people))
    
    # Keywords (personnes + albums Google Photos uniquement)
    all_keywords = get_all_keywords(meta)
    
    if all_keywords:
        if overwrite_mode:
            args.extend(build_overwrite_args_for_keywords(all_keywords))
        elif conditional_mode:
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
        if is_video:
            args.append(f"-QuickTime:ModifyDate={s}")
    
    return args

def build_gps_args(meta: SidecarData, is_video: bool = False) -> List[str]:
    """Construit les arguments pour GPS."""
    args: List[str] = []
    
    if meta.latitude is not None and meta.longitude is not None:
        args.extend([
            f"-GPS:GPSLatitude={meta.latitude}",
            f"-GPS:GPSLongitude={meta.longitude}",
            f"-GPS:GPSLatitudeRef={'N' if meta.latitude >= 0 else 'S'}",
            f"-GPS:GPSLongitudeRef={'E' if meta.longitude >= 0 else 'W'}",
        ])
        if meta.altitude is not None:
            args.append(f"-GPSAltitude={meta.altitude}")
        
        # Pour les vidéos, ajouter aussi Keys:Location et QuickTime:GPSCoordinates
        if is_video:
            location = f"{meta.latitude},{meta.longitude}"
            args.extend([
                f"-Keys:Location={location}",
                f"-QuickTime:GPSCoordinates={location}"
            ])
    
    return args


def build_location_args(meta: SidecarData) -> List[str]:
    """Construit les arguments pour la localisation (ville/pays/lieu)."""
    args: List[str] = []

    city = getattr(meta, "city", None)
    country = getattr(meta, "country", None)
    place_name = getattr(meta, "place_name", None)

    if city:
        args.extend([f"-XMP:City={city}", f"-IPTC:City={city}"])
    if country:
        args.extend([
            f"-XMP:Country={country}",
            f"-IPTC:Country-PrimaryLocationName={country}",
        ])
    if place_name:
        args.append(f"-XMP:Location={place_name}")

    return args

def build_rating_args(meta: SidecarData) -> List[str]:
    """Construit les arguments pour le rating."""
    args: List[str] = []
    
    if meta.favorite:
        args.append("-XMP:Rating=5")
    
    return args

def build_source_app_args(meta: SidecarData, *, conditional_mode: bool = False) -> List[str]:
    """Construit les arguments pour l'application/source d'origine (local_folder_name).
    
    Écrit dans les tags Software/CreatorTool pour indiquer l'application source
    (Camera, WhatsApp, Instagram, etc.) plutôt que comme album.
    """
    args: List[str] = []
    
    if not meta.local_folder_name:
        return args
    
    source_app = meta.local_folder_name.strip()
    
    if conditional_mode:
        # Mode conditionnel : n'écrire que si absent
        args.extend([
            "-if", "not $EXIF:Software",
            f"-EXIF:Software={source_app}",
            "-if", "not $XMP-xmp:CreatorTool", 
            f"-XMP-xmp:CreatorTool={source_app}"
        ])
    else:
        # Mode écrasement ou append-only simple
        args.extend([
            f"-EXIF:Software={source_app}",
            f"-XMP-xmp:CreatorTool={source_app}"
        ])
    
    return args
# === FONCTION PRINCIPALE REFACTORISÉE ===

def build_exiftool_args(meta: SidecarData, media_path: Path = None, use_localtime: bool = False, append_only: bool = True) -> list[str]:
    """Construit les arguments exiftool pour traiter un fichier média avec les métadonnées fournies.
    
    ARCHITECTURE EN DEUX AXES INDÉPENDANTS :
    
    Axe 1 — Sémantique d'écriture (3 modes) :
    - Append-only : -wm cg + -if not $TAG pour scalaires (Description, GPS, dates)
    - Robuste (nettoyage) : -TAG-=val puis -TAG+=val pour listes → zéro doublon, idempotent
    - Conditionnel (perf) : -if 'not $TAG=~/val/i' -TAG+=val → optimisation relances
    
    Axe 2 — Stratégie d'exécution (orthogonal) :
    - Unitaire : un appel exiftool par fichier (cette fonction)
    - Batch : un seul process avec -@ args.txt (dans processor_batch.py)
    
    CHOIX PAR DÉFAUT :
    - PersonInImage/Keywords : mode robuste (-=/+=) pour éviter doublons
    - Description/GPS/Dates : mode append-only (-wm cg) pour préserver existant
    - Normalisation obligatoire en amont (normalize_person_name, normalize_keyword)
    
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
        # Mode append-only : utiliser -wm cg pour préserver l'existant + mode robuste pour les listes
        
        # 1. Arguments append-only (avec -wm cg) : écrit même si le tag existe, garde les valeurs existantes
        append_only_args = []
        
        # Description - mode simple (pas conditionnel)
        append_only_args.extend(build_description_args(meta, conditional_mode=False))
        
        # Dates
        datetime_args = build_datetime_args(meta, use_localtime, is_video)
        if datetime_args:
            append_only_args.extend(datetime_args)
        
        # Vidéo spécifique (description)
        if is_video and meta.description:
            safe_desc = _sanitize_description(meta.description)
            append_only_args.append(f"-Keys:Description={safe_desc}")
        
        # GPS
        gps_args = build_gps_args(meta, is_video)
        if gps_args:
            append_only_args.extend(gps_args)

        # Localisation (ville/pays/lieu)
        location_args = build_location_args(meta)
        if location_args:
            append_only_args.extend(location_args)
        
        # Rating
        rating_args = build_rating_args(meta)
        if rating_args:
            append_only_args.extend(rating_args)
        
        # Application source - mode simple (pas conditionnel)
        source_app_args = build_source_app_args(meta, conditional_mode=False)
        if source_app_args:
            append_only_args.extend(source_app_args)
        
        # Ajouter -wm cg pour préserver l'existant
        if append_only_args:
            args.extend(["-wm", "cg"])
            args.extend(append_only_args)
        
        # 2. Arguments robustes (avec -wm w) : remove-then-add pour éviter les doublons
        robust_args = []
        robust_args.extend(build_people_keywords_args(meta, conditional_mode=False, overwrite_mode=False))
        
        # Revenir au mode d'écrasement par défaut pour les opérations robustes
        if robust_args:
            if append_only_args:  # Si on a eu des arguments append-only, remettre le mode par défaut
                args.extend(["-wm", "w"])
            args.extend(robust_args)
        
    else:
        # Mode écrasement : pas de -wm cg, pas de conditions
        
        # Description
        args.extend(build_description_args(meta, conditional_mode=False))
        
        # PersonInImage et Keywords (mode overwrite: vider puis ajouter)
        args.extend(build_people_keywords_args(meta, conditional_mode=False, overwrite_mode=True))
        
        # Dates
        args.extend(build_datetime_args(meta, use_localtime, is_video))
        
        # Vidéo spécifique
        if is_video and meta.description:
            safe_desc = _sanitize_description(meta.description)
            args.append(f"-Keys:Description={safe_desc}")
        
        # GPS
        args.extend(build_gps_args(meta, is_video))

        # Localisation (ville/pays/lieu)
        args.extend(build_location_args(meta))
        
        # Rating
        args.extend(build_rating_args(meta))
        
        # Application source
        args.extend(build_source_app_args(meta, conditional_mode=False))

    return args

# === FONCTIONS EXISTANTES PRÉSERVÉES ===

def _run_exiftool_command(media_path: Path, args: list[str], _append_only: bool = True) -> None:
    """Exécute une commande exiftool avec gestion d'erreurs."""
    cmd = [
        "exiftool", 
        "-overwrite_original", 
        "-charset", "filename=UTF8",
        "-charset", "iptc=UTF8",
        "-charset", "exif=UTF8", 
        "-codedcharacterset=utf8"
    ]
    
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
        # En mode append_only, le code de sortie 2 avec "files failed condition" est normal
        # (cela signifie que les métadonnées existent déjà)
        if _append_only and e.returncode == 2 and e.stdout and "files failed condition" in e.stdout:
            logger.debug(f"Mode append-only: métadonnées existantes ignorées pour {media_path}")
            return
        
        logger.error(f"Erreur exiftool pour {media_path}: code {e.returncode}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")
        raise RuntimeError(f"Échec de la commande exiftool pour {media_path}: {e.stderr}")
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout exiftool pour {media_path}")
        raise RuntimeError(f"Timeout exiftool pour {media_path}")

def write_metadata(media_path: Path, meta: SidecarData, use_localtime: bool = False, append_only: bool = True) -> None:
    """Écrit les métadonnées sur un média en utilisant ExifTool."""
    
    # Utiliser build_exiftool_args pour construire tous les arguments de manière unifiée
    all_args = build_exiftool_args(meta, media_path, use_localtime, append_only)
    
    if all_args:
        _run_exiftool_command(media_path, all_args, _append_only=append_only)
        
        # En mode écrasement, pour les personnes on veut accumuler (pas écraser complètement)
        # selon les attentes du test test_explicit_overwrite_behavior
        if not append_only and meta.people:
            people_args = []
            # Utiliser remove-then-add pour les personnes pour garantir l'ajout
            people_args.extend(build_remove_then_add_args_for_people(meta.people))
            
            # Keywords pour les personnes aussi
            normalized_people = [normalize_person_name(person) for person in meta.people]
            people_args.extend(build_remove_then_add_args_for_keywords(normalized_people))
            
            if people_args:
                _run_exiftool_command(media_path, people_args, _append_only=False)

# Fonctions utilitaires héritées

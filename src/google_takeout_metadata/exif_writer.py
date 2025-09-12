# Fichier : src/google_takeout_metadata/exif_writer.py

import subprocess
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Iterable, TYPE_CHECKING

from .sidecar import SidecarData

if TYPE_CHECKING:
    from .config_loader import ConfigLoader

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
    
    Note: localFolderName n'est PAS inclus ici car il est traité comme application source
    dans build_source_app_args, pas comme un album.
    """
    keywords = []
    
    # Ajouter les personnes normalisées comme mots-clés
    if meta.people_name:
        normalized_people_name = [normalize_person_name(person) for person in meta.people_name]
        keywords.extend(normalized_people_name)
    
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

def build_remove_then_add_args_for_people_name(people_name: Iterable[str]) -> List[str]:
    """-TAG-=val puis -TAG+=val pour chaque personne normalisée."""
    args: List[str] = []
    for raw in people_name:
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

def build_conditional_add_args_for_people_name(people_name: Iterable[str]) -> List[str]:
    """Option conditionnelle: n'ajoute que si absent (pour relances/perf)."""
    args: List[str] = []
    for raw in people_name:
        person = normalize_person_name(raw)
        if not person:
            continue
        regex = _regex_escape_word(person)
        args.extend([
            "-if", f"not $XMP-iptcExt:PersonInImage=~/{regex}/i",
            f"-XMP-iptcExt:PersonInImage+={person}"
        ])
    return args

def build_overwrite_args_for_people_name(people_name: Iterable[str]) -> List[str]:
    """Arguments mode overwrite : vider puis ajouter chaque personne."""
    args: List[str] = []
    if people_name:
        # Vider d'abord
        args.append("-XMP-iptcExt:PersonInImage=")
        # Puis ajouter chaque personne normalisée
        for raw in people_name:
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

def build_people_name_keywords_args(meta: SidecarData, *, conditional_mode: bool = False, overwrite_mode: bool = False) -> List[str]:
    """Construit les arguments pour PersonInImage et Keywords selon la stratégie choisie."""
    args: List[str] = []
    
    # PersonInImage
    if meta.people_name:
        if overwrite_mode:
            args.extend(build_overwrite_args_for_people_name(meta.people_name))
        elif conditional_mode:
            args.extend(build_conditional_add_args_for_people_name(meta.people_name))
        else:
            args.extend(build_remove_then_add_args_for_people_name(meta.people_name))
    
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
        # Ne pas utiliser -wm cg qui nécessite l'existence des groupes
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
    if (s := _fmt_dt(meta.photoTakenTime_timestamp, use_localtime)):
        args.append(f"-DateTimeOriginal={s}")
        if is_video:
            args.append(f"-QuickTime:CreateDate={s}")

    base_ts = meta.creationTime_timestamp or meta.photoTakenTime_timestamp
    if (s := _fmt_dt(base_ts, use_localtime)):
        args.append(f"-CreateDate={s}")
        args.append(f"-ModifyDate={s}")
        if is_video:
            args.append(f"-QuickTime:ModifyDate={s}")
    
    return args

def build_gps_args(meta: SidecarData, is_video: bool = False) -> List[str]:
    """Construit les arguments pour GPS."""
    args: List[str] = []
    
    if meta.geoData_latitude is not None and meta.geoData_longitude is not None:
        args.extend([
            f"-GPS:GPSLatitude={meta.geoData_latitude}",
            f"-GPS:GPSLongitude={meta.geoData_longitude}",
            f"-GPS:GPSLatitudeRef={'N' if meta.geoData_latitude >= 0 else 'S'}",
            f"-GPS:GPSLongitudeRef={'E' if meta.geoData_longitude >= 0 else 'W'}",
        ])
        if meta.geoData_altitude is not None:
            args.append(f"-GPSAltitude={meta.geoData_altitude}")
        
        # Pour les vidéos, ajouter aussi Keys:Location et QuickTime:GPSCoordinates
        if is_video:
            location = f"{meta.geoData_latitude},{meta.geoData_longitude}"
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
    
    if meta.favorited:
        args.append("-XMP:Rating=5")
    
    return args

def build_source_app_args(meta: SidecarData, *, conditional_mode: bool = False) -> List[str]:
    """Construit les arguments pour l'application/source d'origine (localFolderName).
    
    Écrit dans les tags Software/CreatorTool pour indiquer l'application source
    (Camera, WhatsApp, Instagram, etc.) plutôt que comme album.
    """
    args: List[str] = []
    
    if not meta.localFolderName:
        return args
    
    source_app = meta.localFolderName.strip()
    
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

def build_exiftool_args(
    meta: SidecarData, 
    media_path: Path = None, 
    use_localtime: bool = False, 
    *,
    # Stratégies pour différents types de métadonnées
    description_strategy: str = "preserve_existing",  # "preserve_existing", "replace_all", "write_if_missing"
    people_name_keywords_strategy: str = "clean_duplicates",  # "clean_duplicates", "replace_all", "write_if_missing"
    datetime_strategy: str = "replace_all",  # Dates sont généralement écrasées
    gps_strategy: str = "replace_all",  # GPS généralement écrasé
    location_strategy: str = "replace_all",  # Localisation généralement écrasée
    rating_strategy: str = "preserve_existing",  # Rating préservé par défaut
    source_app_strategy: str = "write_if_missing",  # Application source seulement si absent
    # Legacy compatibility
    append_only: bool = None
) -> list[str]:
    """Construit les arguments exiftool avec des stratégies flexibles par type de métadonnée.
    
    STRATÉGIES DISPONIBLES :
    - "preserve_existing": Utilise -wm cg pour préserver l'existant
    - "replace_all": Remplace complètement les valeurs
    - "write_if_missing": Utilise -if pour n'écrire que si absent
    - "clean_duplicates": Pour listes, supprime puis ajoute (évite doublons)
    
    COMBINAISONS UTILES :
    - write_if_missing + preserve_existing: Inscrire que si n'existe pas, en préservant l'existant
    - clean_duplicates: Pour listes (personnes/mots-clés) - évite les doublons
    
    Args:
        meta: Métadonnées à écrire
        media_path: Chemin du fichier média (optionnel, pour la détection vidéo)
        use_localtime: Utiliser l'heure locale au lieu d'UTC
        description_strategy: Stratégie pour description
        people_name_keywords_strategy: Stratégie pour personnes et mots-clés
        datetime_strategy: Stratégie pour dates
        gps_strategy: Stratégie pour GPS
        location_strategy: Stratégie pour localisation
        rating_strategy: Stratégie pour rating
        source_app_strategy: Stratégie pour application source
        append_only: (Legacy) Si fourni, configure toutes les stratégies en mode preserve/replace
    
    Returns:
        Liste des arguments exiftool
    """
    # Compatibilité avec l'ancienne API
    if append_only is not None:
        if append_only:
            description_strategy = "preserve_existing"
            people_name_keywords_strategy = "clean_duplicates"
            rating_strategy = "preserve_existing"
            source_app_strategy = "write_if_missing"
        else:
            description_strategy = "replace_all"
            people_name_keywords_strategy = "replace_all"
            rating_strategy = "replace_all"
            source_app_strategy = "replace_all"
    
    args = []
    is_video = media_path and _is_video_file(media_path)
    
    if is_video:
        args.extend(["-api", "QuickTimeUTC=1"])
    
    # Déterminer si on a besoin de -wm cg
    needs_preserve_mode = any(strategy == "preserve_existing" for strategy in [
        description_strategy, rating_strategy
    ])
    
    if needs_preserve_mode:
        args.extend(["-wm", "cg"])
    
    # Description
    if description_strategy == "write_if_missing":
        args.extend(build_description_args(meta, conditional_mode=True))
    else:
        args.extend(build_description_args(meta, conditional_mode=False))
    
    # PersonInImage et Keywords
    if people_name_keywords_strategy == "replace_all":
        args.extend(build_people_name_keywords_args(meta, conditional_mode=False, overwrite_mode=True))
    elif people_name_keywords_strategy == "write_if_missing":
        args.extend(build_people_name_keywords_args(meta, conditional_mode=True, overwrite_mode=False))
    else:  # clean_duplicates (par défaut)
        args.extend(build_people_name_keywords_args(meta, conditional_mode=False, overwrite_mode=False))
    
    # Dates
    args.extend(build_datetime_args(meta, use_localtime, is_video))
    
    # Vidéo spécifique (description)
    if is_video and meta.description:
        safe_desc = _sanitize_description(meta.description)
        if description_strategy == "write_if_missing":
            args.extend([
                "-if", "not $Keys:Description",
                f"-Keys:Description={safe_desc}"
            ])
        else:
            args.append(f"-Keys:Description={safe_desc}")
    
    # GPS
    args.extend(build_gps_args(meta, is_video))

    # Localisation (ville/pays/lieu)
    args.extend(build_location_args(meta))
    
    # Rating
    args.extend(build_rating_args(meta))
    
    # Application source
    if source_app_strategy == "write_if_missing":
        args.extend(build_source_app_args(meta, conditional_mode=True))
    else:
        args.extend(build_source_app_args(meta, conditional_mode=False))

    return args

# === FONCTIONS EXISTANTES PRÉSERVÉES ===

def _run_exiftool_command(media_path: Path, args: list[str], _append_only: bool = True) -> None:
    """Exécute une commande exiftool avec gestion d'erreurs."""
    cmd = [
        "exiftool", 
        "-overwrite_original", 
        "-charset", "title=UTF8",
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

def write_metadata_with_config(media_path: Path, meta: SidecarData, use_localtime: bool = False, config_loader: 'ConfigLoader' = None) -> None:
    """Écrit les métadonnées en utilisant la configuration découverte automatiquement.
    
    Args:
        media_path: Chemin du fichier média
        meta: Métadonnées à écrire
        use_localtime: Utiliser l'heure locale
        config_loader: Loader de configuration (créé automatiquement si None)
    """
    if config_loader is None:
        from .config_loader import ConfigLoader
        config_loader = ConfigLoader()
        config_loader.load_config()
    
    # Construire les arguments avec la configuration
    args = build_exiftool_args_from_config(meta, media_path, use_localtime, config_loader)
    
    if args:
        # Déterminer le mode général depuis la configuration
        global_settings = config_loader.config.get('global_settings', {})
        default_strategy = global_settings.get('default_strategy', 'write_if_missing')
        append_only = default_strategy in ['preserve_existing', 'write_if_missing']
        
        _run_exiftool_command(media_path, args, _append_only=append_only)

def build_exiftool_args_from_config(meta: SidecarData, media_path: Path, use_localtime: bool, config_loader: 'ConfigLoader') -> list[str]:
    """Construit les arguments exiftool en utilisant les mappings de configuration découverts.
    
    Args:
        meta: Métadonnées à écrire
        media_path: Chemin du fichier média
        use_localtime: Utiliser l'heure locale
        config_loader: Configuration chargée
        
    Returns:
        Liste des arguments exiftool
    """
    args = []
    is_video = _is_video_file(media_path)
    
    # Récupérer la configuration
    mappings = config_loader.config.get('exif_mapping', {})
    strategies = config_loader.config.get('strategies', {})
    global_settings = config_loader.config.get('global_settings', {})
    
    # Arguments globaux
    common_args = global_settings.get('common_args', [])
    args.extend(common_args)
    
    # Traiter chaque mapping configuré
    for mapping_name, mapping_config in mappings.items():
        source_fields = mapping_config.get('source_fields', [])
        target_tags = mapping_config.get('target_tags', [])
        default_strategy = mapping_config.get('default_strategy', 'write_if_missing')
        
        # Extraire la valeur depuis les métadonnées
        value = _extract_value_from_meta(meta, source_fields)
        if value is None:
            continue
            
        # Appliquer la stratégie pour chaque tag cible
        strategy_config = strategies.get(default_strategy, {})
        for tag in target_tags:
            tag_args = _build_tag_args(tag, value, strategy_config, mapping_config, is_video)
            args.extend(tag_args)
    
    return args

def _extract_value_from_meta(meta: SidecarData, source_fields: list) -> any:
    """Extrait une valeur depuis SidecarData basé sur les champs source configurés.
    
    Supporte les patterns JSON originaux (ex: 'geoData.latitude') et les champs SidecarData directs (ex: 'geoData_latitude').
    Les patterns JSON originaux sont privilégiés pour la lisibilité et la maintenance.
    """
    for field_path in source_fields:
        # Patterns JSON originaux (privilégiés pour lisibilité)
        if field_path == "description" and meta.description:
            return meta.description
        elif field_path == "title" and meta.title:  # title -> title dans SidecarData
            return meta.title
        elif field_path in ["people", "people.name", "people[].name"] and meta.people_name:
            return meta.people_name
        elif field_path == "photoTakenTime.timestamp" and meta.photoTakenTime_timestamp:
            return meta.photoTakenTime_timestamp
        elif field_path == "creationTime.timestamp" and meta.creationTime_timestamp:
            return meta.creationTime_timestamp
        elif field_path == "geoData.latitude" and meta.geoData_latitude:
            return meta.geoData_latitude
        elif field_path == "geoData.longitude" and meta.geoData_longitude:
            return meta.geoData_longitude
        elif field_path == "geoData.altitude" and meta.geoData_altitude:
            return meta.geoData_altitude
        # Patterns simplifiés (rétrocompatibilité)
        elif field_path == "photoTakenTime" and meta.photoTakenTime_timestamp:
            return meta.photoTakenTime_timestamp
        elif field_path == "creationTime" and meta.creationTime_timestamp:
            return meta.creationTime_timestamp
        elif field_path == "latitude" and meta.geoData_latitude:
            return meta.geoData_latitude
        elif field_path == "longitude" and meta.geoData_longitude:
            return meta.geoData_longitude
        elif field_path == "altitude" and meta.geoData_altitude:
            return meta.geoData_altitude
        # Autres champs
        elif field_path == "albums" and meta.albums:
            return meta.albums
        elif field_path == "favorited" and meta.favorited is not None:
            return meta.favorited
        elif field_path == "city" and meta.city:
            return meta.city
        elif field_path == "country" and meta.country:
            return meta.country
    
    return None

def _build_tag_args(tag: str, value: any, strategy_config: dict, mapping_config: dict, is_video: bool) -> list[str]:
    """Construit les arguments pour un tag spécifique selon la stratégie."""
    args = []
    
    # Arguments de stratégie de base
    strategy_args = strategy_config.get('exiftool_args', [])
    args.extend(strategy_args)
    
    # Condition template si présente
    condition_template = strategy_config.get('condition_template')
    if condition_template:
        condition = condition_template.replace('${tag}', tag)
        args.append(condition)
    
    # Pattern personnalisé si présent (pour clean_duplicates par exemple)
    pattern = strategy_config.get('pattern')
    if pattern and isinstance(value, list):
        # Pour les patterns avec listes, traiter chaque élément individuellement
        for item in value:
            for pattern_template in pattern:
                arg = pattern_template.replace('${tag}', tag).replace('${value}', str(item))
                args.append(arg)
    elif pattern:
        # Pattern simple pour valeurs uniques
        for pattern_template in pattern:
            arg = pattern_template.replace('${tag}', tag).replace('${value}', str(value))
            args.append(arg)
    else:
        # Argument simple tag=value
        if isinstance(value, list):
            # Pour les listes, ajouter chaque élément séparément
            for item in value:
                args.append(f"-{tag}={item}")
        else:
            args.append(f"-{tag}={value}")
    
    return args

def write_metadata(media_path: Path, meta: SidecarData, use_localtime: bool = False, append_only: bool = True) -> None:
    """Écrit les métadonnées sur un média en utilisant ExifTool."""
    
    # Utiliser build_exiftool_args avec l'ancienne API pour compatibilité
    all_args = build_exiftool_args(meta, media_path, use_localtime, append_only=append_only)
    
    if all_args:
        _run_exiftool_command(media_path, all_args, _append_only=append_only)

# Fonctions utilitaires héritées

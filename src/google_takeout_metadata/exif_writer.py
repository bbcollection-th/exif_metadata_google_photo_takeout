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

def _fmt_dt(ts: int | None, use_localTime: bool) -> str | None:
    if ts is None:
        return None
    dt = datetime.fromtimestamp(ts) if use_localTime else datetime.fromtimestamp(ts, tz=timezone.utc)
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
    """Arguments mode overwrite : remplacer complètement les personnes."""
    args: List[str] = []
    # Vider d'abord puis ajouter toutes les personnes
    args.append("-XMP-iptcExt:PersonInImage=")  # Vider
    if people_name:
        for raw in people_name:
            person = normalize_person_name(raw)
            if person:
                args.append(f"-XMP-iptcExt:PersonInImage={person}")  # Utiliser = pour remplacer
    return args

def build_overwrite_args_for_keywords(keywords: Iterable[str]) -> List[str]:
    """Arguments mode overwrite : remplacer complètement les keywords."""
    args: List[str] = []
    # Vider d'abord
    args.extend(["-XMP-dc:Subject=", "-IPTC:Keywords="])
    # Puis ajouter chaque keyword en mode remplacement
    for kw in keywords:
        if kw.strip():
            args.extend([f"-XMP-dc:Subject={kw}", f"-IPTC:Keywords={kw}"])
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

def build_datetime_args(meta: SidecarData, use_localTime: bool, is_video: bool) -> List[str]:
    """Construit les arguments pour les dates."""
    args: List[str] = []
    
    # Dates
    if (s := _fmt_dt(meta.photoTakenTime_timestamp, use_localTime)):
        args.append(f"-DateTimeOriginal={s}")
        if is_video:
            args.append(f"-QuickTime:CreateDate={s}")

    base_ts = meta.creationTime_timestamp or meta.photoTakenTime_timestamp
    if (s := _fmt_dt(base_ts, use_localTime)):
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
    """Construit les arguments pour l'application/source d'origine (googlePhotosOrigin_localFolderName).
    
    Écrit dans les tags Software/CreatorTool pour indiquer l'application source
    (Camera, WhatsApp, Instagram, etc.) plutôt que comme album.
    """
    args: List[str] = []
    
    if not meta.googlePhotosOrigin_localFolderName:
        return args
    
    source_app = meta.googlePhotosOrigin_localFolderName.strip()
    
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

# === FONCTIONS EXISTANTES PRÉSERVÉES ===

def _run_exiftool_command(media_path: Path, args: list[str]) -> None:
    """Exécute une commande exiftool avec gestion d'erreurs."""
    cmd = [
        "exiftool", 
        "-overwrite_original", 
        "-charset", "utf8",
        "-codedcharacterset=utf8"
    ]
    
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
        
        # Code 2 avec "files failed condition" n'est pas une erreur fatale
        # C'est le comportement normal quand les conditions -if échouent (ex: champ déjà rempli)
        if e.returncode == 2 and "files failed condition" in e.stdout:
            logger.info(f"Conditions exiftool échouées pour {media_path} (comportement normal pour préservation)")
            return
            
        raise RuntimeError(f"Échec de la commande exiftool pour {media_path}: {e.stderr}")
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout exiftool pour {media_path}")
        raise RuntimeError(f"Timeout exiftool pour {media_path}")

def write_metadata(media_path: Path, meta: SidecarData, use_localTime: bool = False, config_loader: 'ConfigLoader' = None) -> None:
    """Écrit les métadonnées en utilisant la configuration découverte automatiquement.
    
    Args:
        media_path: Chemin du fichier média
        meta: Métadonnées à écrire
        use_localTime: Utiliser l'heure locale
        config_loader: Loader de configuration (créé automatiquement si None)
    """
    if config_loader is None:
        from .config_loader import ConfigLoader
        config_loader = ConfigLoader()
        config_loader.load_config()
    
    # Séparer les arguments par type de stratégie pour éviter les conflits
    args_by_strategy = _group_args_by_strategy(meta, media_path, use_localTime, config_loader)
    
    # Exécuter chaque groupe d'arguments séparément
    for strategy_type, args in args_by_strategy.items():
        if args:
            logger.debug(f"Exécution des arguments {strategy_type}: {args}")
            _run_exiftool_command(media_path, args)

def _group_args_by_strategy(meta: SidecarData, media_path: Path, use_localTime: bool, config_loader: 'ConfigLoader') -> dict:
    """Groupe les arguments par type de stratégie pour les exécuter séparément."""
    is_video = _is_video_file(media_path)
    
    # Récupérer la configuration
    mappings = config_loader.config.get('exif_mapping', {})
    strategies = config_loader.config.get('strategies', {})
    
    # Groupes d'arguments par type de stratégie
    grouped_args = {
        'conditional': [],     # Arguments avec conditions -if
        'unconditional': [],   # Arguments sans condition (replace_all, clean_duplicates)
        'patterns': [],        # Arguments avec patterns spéciaux
        'special_logic': []    # Arguments avec logique spéciale (ex: preserve_positive_rating)
    }
    
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
            
            # Classer les arguments selon leur type
            if strategy_config.get('special_logic'):
                # Logique spéciale exécutée séparément pour éviter les conflits
                grouped_args['special_logic'].extend(tag_args)
            elif any('-if' in str(arg) for arg in tag_args):
                grouped_args['conditional'].extend(tag_args)
            elif strategy_config.get('pattern'):
                grouped_args['patterns'].extend(tag_args)
            else:
                grouped_args['unconditional'].extend(tag_args)
    
    return grouped_args

def build_exiftool_args(meta: SidecarData, media_path: Path, use_localTime: bool, config_loader: 'ConfigLoader') -> list[str]:
    """Construit les arguments exiftool en utilisant les mappings de configuration découverts.
    
    Args:
        meta: Métadonnées à écrire
        media_path: Chemin du fichier média
        use_localTime: Utiliser l'heure locale
        config_loader: Configuration chargée
        
    Returns:
        Liste des arguments exiftool
    """
    args = []
    is_video = _is_video_file(media_path)
    
    # Récupérer la configuration
    mappings = config_loader.config.get('exif_mapping', {})
    strategies = config_loader.config.get('strategies', {})
    
    # Arguments globaux (SANS les ajouter via common_args pour éviter les doublons)
    # common_args = global_settings.get('common_args', [])
    # args.extend(common_args)
    
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
        elif field_path == "photoTakenTime.timestamp" and meta.photoTakenTime_timestamp is not None:
            return meta.photoTakenTime_timestamp
        elif field_path == "creationTime.timestamp" and meta.creationTime_timestamp is not None:
            return meta.creationTime_timestamp
        elif field_path == "geoData.latitude" and meta.geoData_latitude is not None:
            return meta.geoData_latitude
        elif field_path == "geoData.longitude" and meta.geoData_longitude is not None:
            return meta.geoData_longitude
        elif field_path == "geoData.altitude" and meta.geoData_altitude is not None:
            return meta.geoData_altitude
        # Gérer les références GPS (N/S, E/W) basées sur le signe
        elif field_path == "geoData.latitude.ref" and hasattr(meta, 'geoData_latitude') and meta.geoData_latitude is not None:
            return "positive" if meta.geoData_latitude >= 0 else "negative"
        elif field_path == "geoData.longitude.ref" and hasattr(meta, 'geoData_longitude') and meta.geoData_longitude is not None:
            return "positive" if meta.geoData_longitude >= 0 else "negative"
        # Autres champs
        elif field_path == "albums" and meta.albums:
            return meta.albums
        elif field_path == "favorited" and meta.favorited is not None:
            return meta.favorited
        elif field_path == "city" and meta.city:
            return meta.city
        elif field_path == "country" and meta.country:
            return meta.country
        elif field_path == "state" and meta.state:
            return meta.state
        elif field_path == "place_name" and meta.place_name:
            return meta.place_name
    
    return None

def boolean_to_rating(val: bool | None) -> int | None:
    if val is True:
        return 5
    return None  # False ou None => pas d'écriture

def make_rating_args(favorited: bool | None) -> list[str]: 
    value = boolean_to_rating(favorited)
    if value is None:
        return []  # ne rien écrire si False/None

    # Windows: garder les guillemets dans l'argument -if
    return [
        '-if', 'not defined $XMP:Rating or $XMP:Rating eq 0',
        f'-XMP:Rating={value}'
    ]

def _format_timestamp_value(value: any, format_template: str) -> any:
    """Formate une valeur timestamp selon le template spécifié."""
    if not format_template or not isinstance(value, (int, float)):
        return value
    
    try:
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(value, tz=timezone.utc)
        return dt.strftime(format_template)
    except (ValueError, OSError):
        # En cas d'erreur, garder la valeur originale
        return value

def _apply_processing_to_value(value: any, processing: dict) -> any:
    """Applique le traitement (prefix, normalisation) à une valeur."""
    if not processing:
        return value
    
    prefix = processing.get('prefix', '')
    processing_normalize = processing.get('normalize')
    
    if not prefix and not processing_normalize:
        return value
    
    def process_single_item(item):
        processed_item = item
        if prefix:
            processed_item = f"{prefix}{processed_item}"
        if processing_normalize == 'keyword':
            processed_item = normalize_keyword(processed_item)
        elif processing_normalize == 'person_name':
            processed_item = normalize_person_name(processed_item)
        return processed_item
    
    if isinstance(value, list):
        return [process_single_item(item) for item in value]
    else:
        return process_single_item(value)

def _apply_direct_normalization(value: any, normalize_type: str) -> any:
    """Applique la normalisation directe selon le type spécifié."""
    if not normalize_type or not value:
        return value
    
    if normalize_type == 'person_name':
        if isinstance(value, list):
            return [normalize_person_name(item) for item in value]
        else:
            return normalize_person_name(str(value))
    elif normalize_type == 'keyword':
        if isinstance(value, list):
            return [normalize_keyword(item) for item in value]
        else:
            return normalize_keyword(str(value))
    
    return value

def _apply_value_mapping(value: any, value_mapping: dict) -> any:
    """Applique le mapping de valeurs selon la configuration."""
    if not value_mapping:
        return value
    
    str_value = str(value).lower()
    if str_value in value_mapping:
        mapped_value = value_mapping[str_value]
        if mapped_value is None:
            # Valeur mappée à null = signal pour ignorer
            return None
        return mapped_value
    
    return value

def _build_condition_args(condition_template: str, tag: str) -> list[str]:
    """Construit les arguments de condition pour ExifTool."""
    if not condition_template:
        return []
    
    condition = condition_template.replace('${tag}', tag)
    
    if condition.startswith('-if'):
        # Extraire la condition après "-if "
        condition_value = condition[4:].strip()
        return ["-if", condition_value]
    else:
        return [condition]

def _build_pattern_args(pattern: list, tag: str, value: any) -> list[str]:
    """Construit les arguments basés sur des patterns personnalisés."""
    if not pattern:
        return []
    
    args = []
    
    if isinstance(value, list):
        # Pour les patterns avec listes, traiter chaque élément individuellement
        for item in value:
            for pattern_template in pattern:
                arg = pattern_template.replace('${tag}', tag).replace('${value}', str(item))
                # Les arguments doivent commencer par -
                if not arg.startswith('-'):
                    arg = f'-{arg}'
                args.append(arg)
    else:
        # Pattern simple pour valeurs uniques
        for pattern_template in pattern:
            arg = pattern_template.replace('${tag}', tag).replace('${value}', str(value))
            # Les arguments doivent commencer par -
            if not arg.startswith('-'):
                arg = f'-{arg}'
            args.append(arg)
    
    return args

def _build_simple_tag_args(tag: str, value: any) -> list[str]:
    """Construit les arguments simples tag=value."""
    if isinstance(value, list):
        # Pour les listes, ajouter chaque élément séparément
        return [f"-{tag}={item}" for item in value]
    else:
        return [f"-{tag}={value}"]

def _build_preserve_positive_rating_args(tag: str, value: any) -> list[str]:
    """Logique spéciale pour preserve_positive_rating (favorited/Rating).
    
    Si favorited=true ET Rating>0 existant → ne pas toucher (preserve)
    Si favorited=true ET Rating=0 → changer à Rating=5 
    Si favorited=true ET Rating absent → créer Rating=5
    Si favorited=false ET Rating>0 → ne pas changer
    Si favorited=false ET Rating=0 → ne pas changer  
    Si favorited=false ET Rating absent → ne pas ajouter
    """
    if not value or str(value).lower() == 'false':
        # favorited=false → ne jamais toucher à Rating
        return []
    
    if str(value).lower() == 'true' or str(value) == '5':
        # favorited=true → écrire Rating=5 seulement si absent ou =0
        # Note: Testing both string and numeric 0 for ExifTool compatibility
        return [
            "-if", f"not defined ${tag} or ${tag} eq '0' or ${tag} eq 0",
            f"-{tag}=5"
        ]
    
    return []

def _build_tag_args(tag: str, value: any, strategy_config: dict, mapping_config: dict, is_video: bool) -> list[str]:
    """Construit les arguments pour un tag spécifique selon la stratégie."""
    args = []
    
    # 1. Appliquer le formatage de timestamp si nécessaire
    format_template = mapping_config.get('format')
    value = _format_timestamp_value(value, format_template)
    
    # 2. Appliquer le traitement (prefix, normalisation)
    processing = mapping_config.get('processing', {})
    value = _apply_processing_to_value(value, processing)
    
    # 3. Appliquer la normalisation directe si spécifiée
    normalize_type = mapping_config.get('normalize')
    value = _apply_direct_normalization(value, normalize_type)
    
    # 4. Appliquer transformation si spécifiée (ex: boolean_to_rating)
    transform = mapping_config.get('transform')
    if transform == 'boolean_to_rating' and isinstance(value, bool):
        return make_rating_args(value)
    
    # 5. Appliquer value_mapping si présent
    value_mapping = mapping_config.get('value_mapping', {})
    mapped_value = _apply_value_mapping(value, value_mapping)
    if mapped_value is None:
        # Valeur mappée à null = ignorer
        return []
    value = mapped_value
    
    # 5.5. Logique spéciale pour preserve_positive_rating (favorited/Rating)
    special_logic = strategy_config.get('special_logic')
    if special_logic == 'favorited_rating':
        logger.debug(f"Utilisation de la logique spéciale favorited_rating pour {tag} avec valeur {value}")
        special_args = _build_preserve_positive_rating_args(tag, value)
        logger.debug(f"Arguments spéciaux générés: {special_args}")
        return special_args
    
    # 6. Arguments de stratégie de base
    strategy_args = strategy_config.get('exiftool_args', [])
    args.extend(strategy_args)
    
    # 7. Condition template si présente
    condition_template = strategy_config.get('condition_template')
    condition_args = _build_condition_args(condition_template, tag)
    args.extend(condition_args)
    
    # 8. Pattern personnalisé ou arguments simples
    pattern = strategy_config.get('pattern')
    if pattern:
        pattern_args = _build_pattern_args(pattern, tag, value)
        args.extend(pattern_args)
    else:
        simple_args = _build_simple_tag_args(tag, value)
        args.extend(simple_args)
    
    return args


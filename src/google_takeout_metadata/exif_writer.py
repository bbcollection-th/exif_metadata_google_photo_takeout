# Fichier : src/google_takeout_metadata/exif_writer.py

import subprocess
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, TYPE_CHECKING

from .sidecar import SidecarData
from .timezone_calculator import create_timezone_calculator, TimezoneExifArgsGenerator

if TYPE_CHECKING:
    from .config_loader import ConfigLoader

logger = logging.getLogger(__name__)

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".3gp"}

# === CONSTANTES ET NORMALISATION ===

def _get_target_tags(mapping_config: dict, is_video: bool) -> list[str]:
    """Récupère les tags cibles selon le type de média.
    
    Args:
        mapping_config: Configuration du mapping
        is_video: True si le fichier est une vidéo
        
    Returns:
        Liste des tags cibles appropriés
    """
    if is_video:
        return mapping_config.get('target_tags_video', [])
    else:
        return mapping_config.get('target_tags_image', [])

_SMALL_WORDS = {
    "de", "du", "des", "la", "le", "les", "van", "von", "da", "di", "of", "and",
    "der", "den", "het", "el", "al", "bin", "ibn", "af", "zu", "ben", "ap", "abu", "binti", "bint", "della", "delle", "dalla", "delle", "del", "dos", "das", "do", "mac", "fitz"
}

def _is_video_file(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS

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
        out = (e.stdout or "")
        err = (e.stderr or "")
        logger.exception("Erreur exiftool pour %s: code %s\nstdout: %s\nstderr: %s",
                         media_path, e.returncode, out, err)
        # Code 2: fichiers ne satisfont pas la condition (-if) → non fatal
        if e.returncode == 2 and ("files failed condition" in out.lower() or "files failed condition" in err.lower()):
            logger.info("Conditions exiftool échouées pour %s (préservation attendue)", media_path)
            return
        raise RuntimeError(f"Échec de la commande exiftool pour {media_path}: {err or out}") from e
    except subprocess.TimeoutExpired as e:
        logger.exception("Timeout exiftool pour %s", media_path)
        raise RuntimeError(f"Timeout exiftool pour {media_path}") from e

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
    for _, mapping_config in mappings.items():
        source_fields = mapping_config.get('source_fields', [])
        target_tags = _get_target_tags(mapping_config, is_video)
        default_strategy = mapping_config.get('default_strategy', 'write_if_missing')
        
        # Extraire la valeur depuis les métadonnées
        value = _extract_value_from_meta(meta, source_fields)
        if value is None:
            continue
            
        # Appliquer la stratégie pour chaque tag cible
        strategy_config = strategies.get(default_strategy, {})
        
        for tag in target_tags:
            tag_args = _build_tag_args(tag, value, strategy_config, mapping_config, is_video, use_localTime)
            
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
    global_settings = config_loader.config.get('global_settings', {})
    
    # Arguments globaux
    common_args = global_settings.get('common_args', [])
    args.extend(common_args)
    
    # Ajouter l'API QuickTime UTC pour les vidéos
    if is_video:
        args.extend(['-api', 'QuickTimeUTC=1'])
    
    # Traiter chaque mapping configuré
    for mapping_config in mappings.values():
        source_fields = mapping_config.get('source_fields', [])
        target_tags = _get_target_tags(mapping_config, is_video)
        default_strategy = mapping_config.get('default_strategy', 'write_if_missing')
        
        # Extraire la valeur depuis les métadonnées
        value = _extract_value_from_meta(meta, source_fields)
        if value is None:
            continue
            
        # Appliquer la stratégie pour chaque tag cible
        strategy_config = strategies.get(default_strategy, {})
        for tag in target_tags:
            tag_args = _build_tag_args(tag, value, strategy_config, mapping_config, is_video, use_localTime)
            args.extend(tag_args)
    
    # Appliquer la correction de fuseau horaire si activée
    timezone_config = config_loader.config.get('timezone_correction', {})
    if timezone_config.get('enabled', False):
        args = enhance_args_with_timezone_correction(args, meta, media_path, timezone_config)
    
    return args

def _extract_value_from_meta(meta: SidecarData, source_fields: list) -> any:
    """Extrait une valeur depuis SidecarData basé sur les champs source configurés.
    
    Supporte les patterns JSON originaux (ex: 'geoData.latitude') et les champs SidecarData directs (ex: 'geoData_latitude').
    Les patterns JSON originaux sont privilégiés pour la lisibilité et la maintenance.
    
    Gère aussi les cas spéciaux comme la combinaison de latitude/longitude pour les vidéos.
    """
    # Cas spécial : combinaison GPS pour vidéos
    if len(source_fields) == 2 and "geoData.latitude" in source_fields and "geoData.longitude" in source_fields:
        if meta.geoData_latitude is not None and meta.geoData_longitude is not None:
            return f"{meta.geoData_latitude},{meta.geoData_longitude}"
        return None
    
    for field_path in source_fields:
        # Patterns JSON originaux (privilégiés pour lisibilité)
        if field_path == "description" and meta.description:
            return _sanitize_description(meta.description)
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
        elif field_path == "geoData.altitude_ref" and meta.geoData_altitude_ref is not None:
            return meta.geoData_altitude_ref
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
        elif field_path == "googlePhotosOrigin.mobileUpload.deviceFolder.localFolderName" and meta.googlePhotosOrigin_localFolderName:
            return meta.googlePhotosOrigin_localFolderName
    
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

def _format_timestamp_value(value: any, format_template: str, use_localTime: bool = False) -> any:
    """Formate une valeur timestamp selon le template spécifié."""
    if not format_template or not isinstance(value, (int, float)):
        return value
    
    try:
        dt = datetime.fromtimestamp(value) if use_localTime else datetime.fromtimestamp(value, tz=timezone.utc)
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
    """Logique spéciale pour preserve_positive_rating (favorited/Rating et favorited/Label).
    
    Si favorited=true ET tag>0 existant → ne pas toucher (preserve)
    Si favorited=true ET tag=0 → changer à valeur mappée
    Si favorited=true ET tag absent → créer avec valeur mappée
    Si favorited=false → ne jamais toucher
    
    Note: La valeur arrive ici déjà mappée (True->5 pour Rating, True->Favorite pour Label)
    """
    if not value or value is None:
        # Valeur nulle ou fausse → ne jamais toucher au tag
        return []
    
    # Si nous avons une valeur mappée valide, écrire avec conditions de préservation
    if 'Rating' in tag:
        # Pour Rating, tester les conditions 0 et absence
        return [
            "-if", f"not defined ${tag} or ${tag} eq '0' or ${tag} eq 0",
            f"-{tag}={value}"
        ]
    else:
        # Pour Label et autres, tester seulement l'absence ou vide
        return [
            "-if", f"not defined ${tag} or not length(${tag}) or ${tag} eq ''",
            f"-{tag}={value}"
        ]

def _build_tag_args(tag: str, value: any, strategy_config: dict, mapping_config: dict, is_video: bool = False, use_localTime: bool = False) -> list[str]:
    """Construit les arguments pour un tag spécifique selon la stratégie."""
    args = []
    
    # 1. Appliquer le formatage de timestamp si nécessaire
    format_template = mapping_config.get('format')
    value = _format_timestamp_value(value, format_template, use_localTime)

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
    
    # 5.5. Logique spéciale pour preserve_positive_rating (favorited/Rating et Label)
    # Détecter la stratégie preserve_positive_rating directement
    default_strategy = mapping_config.get('default_strategy', '')
    special_logic = strategy_config.get('special_logic')
    
    if default_strategy == 'preserve_positive_rating' or special_logic == 'favorited_rating':
        logger.debug(f"Utilisation de la logique spéciale preserve_positive_rating pour {tag} avec valeur {value}")
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

def enhance_args_with_timezone_correction(args: list[str], meta: SidecarData, 
                                        media_path: Path, timezone_config: dict) -> list[str]:
    """
    Enrichit les arguments ExifTool avec la correction de timezone si activée.
    
    Args:
        args: Arguments ExifTool existants
        meta: Métadonnées sidecar
        media_path: Chemin du fichier média
        timezone_config: Configuration timezone directe
        
    Returns:
        Arguments ExifTool enrichis avec correction timezone
    """
    # Vérifier si la correction timezone est activée
    if not timezone_config.get('enabled', False):
        return args
    
    # Vérifier si on a les données nécessaires (GPS + timestamp)
    if not (meta.geoData_latitude and meta.geoData_longitude and meta.photoTakenTime_timestamp):
        logger.debug(f"Données GPS ou timestamp manquantes pour {media_path}")
        return args
    
    try:
        calc = create_timezone_calculator()
        if not calc:
            logger.warning("Calculateur timezone non disponible")
            return args
        
        # Calculer timezone info
        tz_info = calc.get_timezone_info(
            meta.geoData_latitude,
            meta.geoData_longitude, 
            meta.photoTakenTime_timestamp
        )
        
        if not tz_info:
            logger.warning(f"Impossible de calculer timezone pour {media_path}")
            return args
        
        # Générer les arguments de correction
        generator = TimezoneExifArgsGenerator(calc)
        is_video = _is_video_file(media_path)
        
        if is_video:
            # Pour les vidéos, ajouter les args UTC spécifiques
            tz_args = generator.generate_video_args(media_path, meta.photoTakenTime_timestamp)
            logger.info(f"Correction timezone vidéo pour {media_path}: UTC (offset {tz_info.offset_string})")
        else:
            # Pour les images, utiliser valeurs absolues ou shift
            use_absolute = timezone_config.get('use_absolute_values', True)
            tz_args = generator.generate_image_args(media_path, tz_info, use_absolute)
            logger.info(f"Correction timezone image pour {media_path}: {tz_info.timezone_name} ({tz_info.offset_string})")
        
        # Filtrer les arguments de fichier (déjà dans args principal)
        filtered_tz_args = [arg for arg in tz_args if str(media_path) not in arg and '-overwrite_original' not in arg]
        
        # Fusionner intelligemment avec les args existants
        enhanced_args = _merge_timezone_args(args, filtered_tz_args)
        return enhanced_args
        
    except Exception as e:
        logger.error(f"Erreur correction timezone pour {media_path}: {e}")
        return args

def _merge_timezone_args(base_args: list[str], tz_args: list[str]) -> list[str]:
    """
    Fusionne intelligemment les arguments timezone avec les arguments de base.
    Les arguments timezone ont priorité sur les arguments de dates existants.
    """
    # Tags de dates qui peuvent être écrasés par timezone
    date_tags = {
        'DateTimeOriginal', 'CreateDate', 'OffsetTimeOriginal', 
        'OffsetTimeDigitized', 'OffsetTime', 'QuickTime:CreateDate',
        'QuickTime:ModifyDate', 'TrackCreateDate', 'MediaCreateDate'
    }
    
    # Filtrer les arguments de base qui seraient en conflit
    filtered_base = []
    for arg in base_args:
        if arg.startswith('-') and '=' in arg:
            tag_part = arg.split('=')[0][1:]  # Enlever le '-' et prendre la partie avant '='
            if any(date_tag in tag_part for date_tag in date_tags):
                logger.debug(f"Remplacement argument date: {arg}")
                continue
        filtered_base.append(arg)
    
    # Combiner les arguments filtrés avec les nouveaux
    return filtered_base + tz_args


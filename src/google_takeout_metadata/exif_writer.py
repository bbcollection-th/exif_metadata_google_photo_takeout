# imports: supprime import shlex, tempfile
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from .sidecar import SidecarData

logger = logging.getLogger(__name__)

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".3gp"}  # ensemble plus large d'extensions vidéo

def _analyze_exiftool_error(stderr: str, stdout: str, returncode: int, media_path: Path) -> str:
    """Analyse les erreurs d'exiftool et retourne un message plus clair."""
    stderr_msg = stderr.strip() if stderr else ""
    stdout_msg = stdout.strip() if stdout else ""
    
    if "doesn't exist or isn't writable" in stderr_msg:
        if "Keys:Location" in stderr_msg:
            return (f"Le champ GPS 'Keys:Location' n'est pas supporté par {media_path.name}. "
                   f"Ceci est normal pour certains formats de fichiers.")
        elif "QuickTime:" in stderr_msg:
            return (f"Certains champs vidéo QuickTime ne sont pas supportés par {media_path.name}. "
                   f"Les métadonnées de base ont été écrites avec succès.")
        else:
            return (f"Certains champs de métadonnées ne sont pas supportés par {media_path.name}: "
                   f"{stderr_msg}")
    
    if "character(s) could not be encoded" in stderr_msg:
        return (f"Problème d'encodage de caractères dans le nom de fichier {media_path.name}. "
               f"Les caractères spéciaux (émojis, accents) peuvent causer ce problème. "
               f"Les métadonnées ont probablement été écrites malgré cet avertissement.")
    
    if "not supported" in stderr_msg.lower():
        return (f"Certaines métadonnées ne sont pas supportées par le format de {media_path.name}. "
               f"Détails: {stderr_msg}")
    
    if "nothing to do" in stderr_msg.lower():
        return f"Aucune métadonnée à écrire pour {media_path.name} (le fichier a déjà toutes les métadonnées)."
    
    # Message d'erreur générique avec plus de contexte
    error_detail = stderr_msg or stdout_msg or "Aucune information détaillée"
    return (f"Erreur lors de l'écriture des métadonnées pour {media_path.name} "
           f"(code {returncode}): {error_detail}")

def _is_video_file(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS

def _fmt_dt(ts: int | None, use_localtime: bool) -> str | None:
    if ts is None:
        return None
    dt = datetime.fromtimestamp(ts) if use_localtime else datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y:%m:%d %H:%M:%S")  # EXIF sans fuseau

def _build_video_config_args(media_path: Path | None) -> List[str]:
    """Construire les arguments de configuration pour les vidéos."""
    args: List[str] = []
    if media_path and _is_video_file(media_path):
        args += ["-api", "QuickTimeUTC=1"]
    return args


def _build_description_args(meta: SidecarData, media_path: Path | None, append_only: bool) -> List[str]:
    """Construire les arguments pour la description."""
    args: List[str] = []
    
    if not meta.description:
        return args
    
    if append_only:
        # Mode strict "append-only" : écrire uniquement si la balise n'existe pas déjà
        args.extend([
            "-if", "not $EXIF:ImageDescription", f"-EXIF:ImageDescription={meta.description}",
            "-if", "not $XMP-dc:Description", f"-XMP-dc:Description={meta.description}",
            "-if", "not $IPTC:Caption-Abstract", f"-IPTC:Caption-Abstract={meta.description}",
        ])
        if media_path and _is_video_file(media_path):
            args.extend([
                "-if", "not $Keys:Description", f"-Keys:Description={meta.description}"
            ])
    else:
        # Mode écrasement : remplacer les descriptions existantes
        args.extend([
            f"-EXIF:ImageDescription={meta.description}",
            f"-XMP-dc:Description={meta.description}",
            f"-IPTC:Caption-Abstract={meta.description}",
        ])
        if media_path and _is_video_file(media_path):
            args.append(f"-Keys:Description={meta.description}")
    
    return args


def _build_people_args(meta: SidecarData, append_only: bool) -> List[str]:
    """Construire les arguments pour les personnes."""
    args: List[str] = []
    
    for person in meta.people:
        # En modes append_only et overwrite, on utilise += pour ajouter les personnes (sans tout remplacer)
        args += [
            f"-XMP-iptcExt:PersonInImage+={person}",
            f"-XMP-dc:Subject+={person}",
            f"-IPTC:Keywords+={person}",
        ]
    
    return args


def _build_albums_args(meta: SidecarData, append_only: bool) -> List[str]:
    """Construire les arguments pour les albums."""
    args: List[str] = []
    
    for album in meta.albums:
        album_keyword = f"Album: {album}"
        # En modes append_only et overwrite, on utilise += pour ajouter les albums (sans tout remplacer)
        args += [
            f"-XMP-dc:Subject+={album_keyword}",
            f"-IPTC:Keywords+={album_keyword}",
        ]
    
    return args


def _build_rating_args(meta: SidecarData, append_only: bool) -> List[str]:
    """Construire les arguments pour le rating/favoris."""
    args: List[str] = []
    
    if meta.favorite:
        if append_only:
            # Définir le rating uniquement s'il n'existe pas déjà
            args.extend(["-if", "not $XMP:Rating", f"-XMP:Rating=5"])
        else:
            # Mode écrasement : forcer le rating même s'il existe déjà
            args.append(f"-XMP:Rating=5")
    
    return args


def _build_date_args(meta: SidecarData, media_path: Path | None, use_localtime: bool, append_only: bool) -> List[str]:
    """Construire les arguments pour les dates."""
    args: List[str] = []
    
    # Définir les champs EXIF standard :
    # - DateTimeOriginal est défini à partir de meta.taken_at (prise de vue)
    # - CreateDate et ModifyDate sont définis à partir de meta.created_at si disponible, sinon meta.taken_at
    if (s := _fmt_dt(meta.taken_at, use_localtime)):
        if append_only:
            args.extend(["-if", "not $DateTimeOriginal", f"-DateTimeOriginal={s}"])
        else:
            args.append(f"-DateTimeOriginal={s}")

    base_ts = meta.created_at or meta.taken_at
    if (s := _fmt_dt(base_ts, use_localtime)):
        if append_only:
            args.extend(["-if", "not $CreateDate", f"-CreateDate={s}"])
            args.extend(["-if", "not $ModifyDate", f"-ModifyDate={s}"])
        else:
            args.extend([f"-CreateDate={s}", f"-ModifyDate={s}"])

    # Dates QuickTime (vidéos)
    if media_path and _is_video_file(media_path):
        if (s := _fmt_dt(meta.taken_at, use_localtime)):
            if append_only:
                args.extend(["-if", "not $QuickTime:CreateDate", f"-QuickTime:CreateDate={s}"])
            else:
                args.append(f"-QuickTime:CreateDate={s}")
        if (s := _fmt_dt(base_ts, use_localtime)):
            if append_only:
                args.extend(["-if", "not $QuickTime:ModifyDate", f"-QuickTime:ModifyDate={s}"])
            else:
                args.append(f"-QuickTime:ModifyDate={s}")
    
    return args


def _build_gps_args(meta: SidecarData, media_path: Path | None, append_only: bool) -> List[str]:
    """Construire les arguments pour les données GPS."""
    args: List[str] = []
    
    if meta.latitude is None or meta.longitude is None:
        return args
    
    lat_ref = "N" if meta.latitude >= 0 else "S"
    lon_ref = "E" if meta.longitude >= 0 else "W"
    
    if append_only:
        # Écrire le GPS uniquement s'il n'existe pas déjà
        args += [
            "-if", "not $GPSLatitude", f"-GPSLatitude={abs(meta.latitude)}",
            "-if", "not $GPSLatitudeRef", f"-GPSLatitudeRef={lat_ref}",
            "-if", "not $GPSLongitude", f"-GPSLongitude={abs(meta.longitude)}",
            "-if", "not $GPSLongitudeRef", f"-GPSLongitudeRef={lon_ref}",
        ]
    else:
        args += [
            f"-GPSLatitude={abs(meta.latitude)}",
            f"-GPSLatitudeRef={lat_ref}",
            f"-GPSLongitude={abs(meta.longitude)}",
            f"-GPSLongitudeRef={lon_ref}",
        ]
    
    if meta.altitude is not None:
        alt_ref = "1" if meta.altitude < 0 else "0"
        if append_only:
            args += ["-if", "not $GPSAltitude", f"-GPSAltitude={abs(meta.altitude)}", "-if", "not $GPSAltitudeRef", f"-GPSAltitudeRef={alt_ref}"]
        else:
            args += [f"-GPSAltitude={abs(meta.altitude)}", f"-GPSAltitudeRef={alt_ref}"]

    if media_path and _is_video_file(media_path):
        # QuickTime:GPSCoordinates accepte "lat lon" ou "lat,lon" selon les players ; cette forme marche en général
        if append_only:
            args.extend(["-if", "not $QuickTime:GPSCoordinates", f"-QuickTime:GPSCoordinates={meta.latitude},{meta.longitude}"])
            args.extend(["-if", "not $Keys:Location", f"-Keys:Location={meta.latitude},{meta.longitude}"])
        else:
            args.append(f"-QuickTime:GPSCoordinates={meta.latitude},{meta.longitude}")
            args.append(f"-Keys:Location={meta.latitude},{meta.longitude}")
    
    return args


def build_exiftool_args(meta: SidecarData, media_path: Path | None = None, use_localtime: bool = False, append_only: bool = True) -> List[str]:
    """Construire la liste complète des arguments pour exiftool."""
    args: List[str] = []

    # Configuration vidéo
    args.extend(_build_video_config_args(media_path))
    
    # Description
    args.extend(_build_description_args(meta, media_path, append_only))
    
    # Personnes
    args.extend(_build_people_args(meta, append_only))
    
    # Albums
    args.extend(_build_albums_args(meta, append_only))
    
    # Rating/Favoris
    args.extend(_build_rating_args(meta, append_only))
    
    # Dates
    args.extend(_build_date_args(meta, media_path, use_localtime, append_only))
    
    # GPS
    args.extend(_build_gps_args(meta, media_path, append_only))

    return args

def write_metadata(media_path: Path, meta: SidecarData, use_localtime: bool = False, append_only: bool = True) -> None:
    if append_only:
        # En mode append-only, exécuter des commandes séparées pour écritures conditionnelles et inconditionnelles
        # Cela évite que les conditions -if n'affectent les opérations suivantes
        _write_metadata_append_only(media_path, meta, use_localtime)
    else:
        # En mode écrasement, utiliser l'approche standard en une seule commande
        args = build_exiftool_args(meta, media_path, use_localtime=use_localtime, append_only=False)
        if args:
            _run_exiftool_command(media_path, args, append_only=False)


def _write_metadata_append_only(media_path: Path, meta: SidecarData, use_localtime: bool) -> None:
    """Écrire les métadonnées en mode append-only via des commandes séparées pour les écritures conditionnelles."""
    
    # Vérifier s'il s'agit d'un fichier vidéo
    is_video = _is_video_file(media_path)
    
    # Ajouter la configuration spécifique vidéo
    if is_video:
        video_config_args = ["-api", "QuickTimeUTC=1"]
        _run_exiftool_command(media_path, video_config_args, append_only=True)
    
    # 1. Écrire la description seulement si elle n'existe pas (conditionnel)
    if meta.description:
        desc_args = [
            "-if", "not $EXIF:ImageDescription", f"-EXIF:ImageDescription={meta.description}",
        ]
        _run_exiftool_command(media_path, desc_args, append_only=True, allow_condition_failure=True)
        
        desc_args = [
            "-if", "not $XMP-dc:Description", f"-XMP-dc:Description={meta.description}",
        ]
        _run_exiftool_command(media_path, desc_args, append_only=True, allow_condition_failure=True)
        
        desc_args = [
            "-if", "not $IPTC:Caption-Abstract", f"-IPTC:Caption-Abstract={meta.description}",
        ]
        _run_exiftool_command(media_path, desc_args, append_only=True, allow_condition_failure=True)
        
        # Ajouter le champ de description spécifique aux vidéos
        if is_video:
            desc_args = [
                "-if", "not $Keys:Description", f"-Keys:Description={meta.description}",
            ]
            _run_exiftool_command(media_path, desc_args, append_only=True, allow_condition_failure=True)
    
    # 2. Ajouter les personnes sans condition (listes, donc += est sûr)
    if meta.people:
        people_args = []
        for person in meta.people:
            people_args += [
                f"-XMP-iptcExt:PersonInImage+={person}",
                f"-XMP-dc:Subject+={person}",
                f"-IPTC:Keywords+={person}",
            ]
        _run_exiftool_command(media_path, people_args, append_only=True)
    
    # 3. Ajouter les albums sans condition (listes, donc += est sûr)
    if meta.albums:
        album_args = []
        for album in meta.albums:
            album_keyword = f"Album: {album}"
            album_args += [
                f"-XMP-dc:Subject+={album_keyword}",
                f"-IPTC:Keywords+={album_keyword}",
            ]
        _run_exiftool_command(media_path, album_args, append_only=True)
    
    # 4. Écrire le rating uniquement s'il n'existe pas (conditionnel)
    if meta.favorite:
        rating_args = ["-if", "not $XMP:Rating", f"-XMP:Rating=5"]
        _run_exiftool_command(media_path, rating_args, append_only=True, allow_condition_failure=True)
    
    # 5. Écrire les dates uniquement si elles n'existent pas (conditionnel)
    if (s := _fmt_dt(meta.taken_at, use_localtime)):
        date_args = ["-if", "not $DateTimeOriginal", f"-DateTimeOriginal={s}"]
        _run_exiftool_command(media_path, date_args, append_only=True, allow_condition_failure=True)
        
        # Ajouter QuickTime:CreateDate pour les vidéos
        if is_video:
            date_args = ["-if", "not $QuickTime:CreateDate", f"-QuickTime:CreateDate={s}"]
            _run_exiftool_command(media_path, date_args, append_only=True, allow_condition_failure=True)
    
    base_ts = meta.created_at or meta.taken_at
    if (s := _fmt_dt(base_ts, use_localtime)):
        date_args = ["-if", "not $CreateDate", f"-CreateDate={s}"]
        _run_exiftool_command(media_path, date_args, append_only=True, allow_condition_failure=True)
        
        date_args = ["-if", "not $ModifyDate", f"-ModifyDate={s}"]
        _run_exiftool_command(media_path, date_args, append_only=True, allow_condition_failure=True)
        
        # Ajouter QuickTime:ModifyDate pour les vidéos
        if is_video:
            date_args = ["-if", "not $QuickTime:ModifyDate", f"-QuickTime:ModifyDate={s}"]
            _run_exiftool_command(media_path, date_args, append_only=True, allow_condition_failure=True)
    
    # 6. Écrire le GPS uniquement s'il n'existe pas (conditionnel)
    if meta.latitude is not None and meta.longitude is not None:
        lat_ref = "N" if meta.latitude >= 0 else "S"
        lon_ref = "E" if meta.longitude >= 0 else "W"
        
        gps_args = ["-if", "not $GPSLatitude", f"-GPSLatitude={abs(meta.latitude)}"]
        _run_exiftool_command(media_path, gps_args, append_only=True, allow_condition_failure=True)
        
        gps_args = ["-if", "not $GPSLatitudeRef", f"-GPSLatitudeRef={lat_ref}"]
        _run_exiftool_command(media_path, gps_args, append_only=True, allow_condition_failure=True)
        
        gps_args = ["-if", "not $GPSLongitude", f"-GPSLongitude={abs(meta.longitude)}"]
        _run_exiftool_command(media_path, gps_args, append_only=True, allow_condition_failure=True)
        
        gps_args = ["-if", "not $GPSLongitudeRef", f"-GPSLongitudeRef={lon_ref}"]
        _run_exiftool_command(media_path, gps_args, append_only=True, allow_condition_failure=True)
        
        # Ajouter les champs GPS spécifiques aux vidéos
        if is_video:
            gps_args = ["-if", "not $QuickTime:GPSCoordinates", f"-QuickTime:GPSCoordinates={meta.latitude},{meta.longitude}"]
            _run_exiftool_command(media_path, gps_args, append_only=True, allow_condition_failure=True)
            
            gps_args = ["-if", "not $Keys:Location", f"-Keys:Location={meta.latitude},{meta.longitude}"]
            _run_exiftool_command(media_path, gps_args, append_only=True, allow_condition_failure=True)
    
    # 7. Écrire l'altitude GPS uniquement si elle n'existe pas (conditionnel)
    if meta.altitude is not None:
        alt_ref = "1" if meta.altitude < 0 else "0"
        
        gps_args = ["-if", "not $GPSAltitude", f"-GPSAltitude={abs(meta.altitude)}"]
        _run_exiftool_command(media_path, gps_args, append_only=True, allow_condition_failure=True)
        
        gps_args = ["-if", "not $GPSAltitudeRef", f"-GPSAltitudeRef={alt_ref}"]
        _run_exiftool_command(media_path, gps_args, append_only=True, allow_condition_failure=True)


def _run_exiftool_command(media_path: Path, args: list[str], append_only: bool, allow_condition_failure: bool = False) -> None:
    """Exécuter une commande exiftool avec les arguments fournis."""
    if not args:
        return

    cmd = [
        "exiftool",
        "-overwrite_original",
        "-charset", "filename=UTF8",
        "-charset", "iptc=UTF8",
        "-charset", "exif=UTF8",
        *args,
        str(media_path),
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60, encoding='utf-8')
    except FileNotFoundError as exc:
        raise RuntimeError("exiftool introuvable") from exc
    except subprocess.CalledProcessError as exc:
        # Le code de sortie 2 signifie "files failed condition" avec -if
        # Comportement attendu en mode append-only quand les balises existent déjà
        if (exc.returncode == 2 and allow_condition_failure and 
            ("files failed condition" in (exc.stderr or "") or 
             "files failed condition" in (exc.stdout or ""))):
            # Attendu : les conditions ont empêché l'écriture car les balises existent
            return
            
        # Le code 1 avec des avertissements sur des champs non inscriptibles est non fatal
        # pour des balises vidéo qui ne sont pas toujours prises en charge
        stderr_msg = exc.stderr or ""
        if (exc.returncode == 1 and allow_condition_failure and 
            ("doesn't exist or isn't writable" in stderr_msg or
             "not supported" in stderr_msg.lower() or
             "nothing to do" in stderr_msg.lower())):
            # Avertissement non fatal pour des balises vidéo non supportées
            logger.warning(_analyze_exiftool_error(exc.stderr or "", exc.stdout or "", 
                                                 exc.returncode, media_path))
            return
            
        error_msg = _analyze_exiftool_error(exc.stderr or "", exc.stdout or "", 
                                          exc.returncode, media_path)
        raise RuntimeError(error_msg) from exc

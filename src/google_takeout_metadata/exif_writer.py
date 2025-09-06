# imports: supprime import shlex, tempfile
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from .sidecar import SidecarData

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".3gp"}  # broader set of video extensions

def _is_video_file(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS

def _fmt_dt(ts: int | None, use_localtime: bool) -> str | None:
    if ts is None:
        return None
    dt = datetime.fromtimestamp(ts) if use_localtime else datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y:%m:%d %H:%M:%S")  # EXIF sans fuseau

def _build_video_config_args(image_path: Path | None) -> List[str]:
    """Construire les arguments de configuration pour les vidéos."""
    args: List[str] = []
    if image_path and _is_video_file(image_path):
        args += ["-api", "QuickTimeUTC=1"]
    return args


def _build_description_args(meta: SidecarData, image_path: Path | None, append_only: bool) -> List[str]:
    """Construire les arguments pour la description."""
    args: List[str] = []
    
    if not meta.description:
        return args
    
    if append_only:
        # True append-only mode: only write if tag doesn't already exist
        args.extend([
            "-if", "not $EXIF:ImageDescription", f"-EXIF:ImageDescription={meta.description}",
            "-if", "not $XMP-dc:Description", f"-XMP-dc:Description={meta.description}",
            "-if", "not $IPTC:Caption-Abstract", f"-IPTC:Caption-Abstract={meta.description}",
        ])
        if image_path and _is_video_file(image_path):
            args.extend([
                "-if", "not $Keys:Description", f"-Keys:Description={meta.description}"
            ])
    else:
        # Overwrite mode: replace existing descriptions
        args.extend([
            f"-EXIF:ImageDescription={meta.description}",
            f"-XMP-dc:Description={meta.description}",
            f"-IPTC:Caption-Abstract={meta.description}",
        ])
        if image_path and _is_video_file(image_path):
            args.append(f"-Keys:Description={meta.description}")
    
    return args


def _build_people_args(meta: SidecarData, append_only: bool) -> List[str]:
    """Construire les arguments pour les personnes."""
    args: List[str] = []
    
    for person in meta.people:
        # Both append_only and overwrite mode use += to add people (not replace all)
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
        # Both append_only and overwrite mode use += to add albums (not replace all)
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
            # Only set rating if not already present
            args.extend(["-if", "not $XMP:Rating", f"-XMP:Rating=5"])
        else:
            # Overwrite mode: set rating even if already present
            args.append(f"-XMP:Rating=5")
    
    return args


def _build_date_args(meta: SidecarData, image_path: Path | None, use_localtime: bool, append_only: bool) -> List[str]:
    """Construire les arguments pour les dates."""
    args: List[str] = []
    
    # Set standard EXIF date fields:
    # - DateTimeOriginal is set from meta.taken_at (when the photo/video was taken)
    # - CreateDate and ModifyDate are set from meta.created_at if available, otherwise from meta.taken_at
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
    if image_path and _is_video_file(image_path):
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


def _build_gps_args(meta: SidecarData, image_path: Path | None, append_only: bool) -> List[str]:
    """Construire les arguments pour les données GPS."""
    args: List[str] = []
    
    if meta.latitude is None or meta.longitude is None:
        return args
    
    lat_ref = "N" if meta.latitude >= 0 else "S"
    lon_ref = "E" if meta.longitude >= 0 else "W"
    
    if append_only:
        # Only write GPS if not already present
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

    if image_path and _is_video_file(image_path):
        # QuickTime:GPSCoordinates accepte "lat lon" ou "lat,lon" selon les players ; cette forme marche en général
        if append_only:
            args.extend(["-if", "not $QuickTime:GPSCoordinates", f"-QuickTime:GPSCoordinates={meta.latitude},{meta.longitude}"])
            args.extend(["-if", "not $Keys:Location", f"-Keys:Location={meta.latitude},{meta.longitude}"])
        else:
            args.append(f"-QuickTime:GPSCoordinates={meta.latitude},{meta.longitude}")
            args.append(f"-Keys:Location={meta.latitude},{meta.longitude}")
    
    return args


def build_exiftool_args(meta: SidecarData, image_path: Path | None = None, use_localtime: bool = False, append_only: bool = True) -> List[str]:
    """Construire la liste complète des arguments pour exiftool."""
    args: List[str] = []

    # Configuration vidéo
    args.extend(_build_video_config_args(image_path))
    
    # Description
    args.extend(_build_description_args(meta, image_path, append_only))
    
    # Personnes
    args.extend(_build_people_args(meta, append_only))
    
    # Albums
    args.extend(_build_albums_args(meta, append_only))
    
    # Rating/Favoris
    args.extend(_build_rating_args(meta, append_only))
    
    # Dates
    args.extend(_build_date_args(meta, image_path, use_localtime, append_only))
    
    # GPS
    args.extend(_build_gps_args(meta, image_path, append_only))

    return args

def write_metadata(image_path: Path, meta: SidecarData, use_localtime: bool = False, append_only: bool = True) -> None:
    if append_only:
        # In append-only mode, we need to run separate commands for conditional vs unconditional writes
        # This prevents -if conditions from affecting subsequent operations
        _write_metadata_append_only(image_path, meta, use_localtime)
    else:
        # In overwrite mode, use the standard single-command approach
        args = build_exiftool_args(meta, image_path, use_localtime=use_localtime, append_only=False)
        if args:
            _run_exiftool_command(image_path, args, append_only=False)


def _write_metadata_append_only(image_path: Path, meta: SidecarData, use_localtime: bool) -> None:
    """Write metadata in append-only mode using separate commands for conditional writes."""
    
    # 1. Write descriptions only if they don't exist (conditional)
    if meta.description:
        desc_args = [
            "-if", "not $EXIF:ImageDescription", f"-EXIF:ImageDescription={meta.description}",
        ]
        _run_exiftool_command(image_path, desc_args, append_only=True, allow_condition_failure=True)
        
        desc_args = [
            "-if", "not $XMP-dc:Description", f"-XMP-dc:Description={meta.description}",
        ]
        _run_exiftool_command(image_path, desc_args, append_only=True, allow_condition_failure=True)
        
        desc_args = [
            "-if", "not $IPTC:Caption-Abstract", f"-IPTC:Caption-Abstract={meta.description}",
        ]
        _run_exiftool_command(image_path, desc_args, append_only=True, allow_condition_failure=True)
    
    # 2. Add people unconditionally (they are lists, so += is safe)
    if meta.people:
        people_args = []
        for person in meta.people:
            people_args += [
                f"-XMP-iptcExt:PersonInImage+={person}",
                f"-XMP-dc:Subject+={person}",
                f"-IPTC:Keywords+={person}",
            ]
        _run_exiftool_command(image_path, people_args, append_only=True)
    
    # 3. Add albums unconditionally (they are lists, so += is safe)
    if meta.albums:
        album_args = []
        for album in meta.albums:
            album_keyword = f"Album: {album}"
            album_args += [
                f"-XMP-dc:Subject+={album_keyword}",
                f"-IPTC:Keywords+={album_keyword}",
            ]
        _run_exiftool_command(image_path, album_args, append_only=True)
    
    # 4. Write rating only if it doesn't exist (conditional)
    if meta.favorite:
        rating_args = ["-if", "not $XMP:Rating", f"-XMP:Rating=5"]
        _run_exiftool_command(image_path, rating_args, append_only=True, allow_condition_failure=True)
    
    # 5. Write dates only if they don't exist (conditional)
    if (s := _fmt_dt(meta.taken_at, use_localtime)):
        date_args = ["-if", "not $DateTimeOriginal", f"-DateTimeOriginal={s}"]
        _run_exiftool_command(image_path, date_args, append_only=True, allow_condition_failure=True)
    
    base_ts = meta.created_at or meta.taken_at
    if (s := _fmt_dt(base_ts, use_localtime)):
        date_args = ["-if", "not $CreateDate", f"-CreateDate={s}"]
        _run_exiftool_command(image_path, date_args, append_only=True, allow_condition_failure=True)
        
        date_args = ["-if", "not $ModifyDate", f"-ModifyDate={s}"]
        _run_exiftool_command(image_path, date_args, append_only=True, allow_condition_failure=True)
    
    # 6. Write GPS only if it doesn't exist (conditional)
    if meta.latitude is not None and meta.longitude is not None:
        lat_ref = "N" if meta.latitude >= 0 else "S"
        lon_ref = "E" if meta.longitude >= 0 else "W"
        
        gps_args = ["-if", "not $GPSLatitude", f"-GPSLatitude={abs(meta.latitude)}"]
        _run_exiftool_command(image_path, gps_args, append_only=True, allow_condition_failure=True)
        
        gps_args = ["-if", "not $GPSLatitudeRef", f"-GPSLatitudeRef={lat_ref}"]
        _run_exiftool_command(image_path, gps_args, append_only=True, allow_condition_failure=True)
        
        gps_args = ["-if", "not $GPSLongitude", f"-GPSLongitude={abs(meta.longitude)}"]
        _run_exiftool_command(image_path, gps_args, append_only=True, allow_condition_failure=True)
        
        gps_args = ["-if", "not $GPSLongitudeRef", f"-GPSLongitudeRef={lon_ref}"]
        _run_exiftool_command(image_path, gps_args, append_only=True, allow_condition_failure=True)


def _run_exiftool_command(image_path: Path, args: list[str], append_only: bool, allow_condition_failure: bool = False) -> None:
    """Run a single exiftool command with the given arguments."""
    if not args:
        return

    cmd = [
        "exiftool",
        "-overwrite_original",
        "-charset", "filename=UTF8",
        "-charset", "iptc=UTF8",
        "-charset", "exif=UTF8",
        *args,
        str(image_path),
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60, encoding='utf-8')
    except FileNotFoundError as exc:
        raise RuntimeError("exiftool not found") from exc
    except subprocess.CalledProcessError as exc:
        # Exit code 2 means "files failed condition" when using -if
        # This is expected behavior in append-only mode when tags already exist
        if exc.returncode == 2 and allow_condition_failure and "files failed condition" in (exc.stdout or ""):
            # This is expected - the conditions prevented writing because tags already exist
            return
        raise RuntimeError(f"exiftool failed for {image_path}: {exc.stderr or exc.stdout}") from exc

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

def build_exiftool_args(meta: SidecarData, image_path: Path | None = None, use_localtime: bool = False, append_only: bool = False) -> List[str]:
    args: List[str] = []

    # Vidéos : clarifier que nos timestamps source sont en UTC quand use_localtime=False
    if image_path and _is_video_file(image_path):
        args += ["-api", "QuickTimeUTC=1"]

    # Description
    if meta.description:
        desc_tag = "=" if not append_only else "-="
        args += [
            f"-EXIF:ImageDescription{desc_tag}{meta.description}",
            f"-XMP-dc:Description{desc_tag}{meta.description}",
            f"-IPTC:Caption-Abstract{desc_tag}{meta.description}",
        ]
        if image_path and _is_video_file(image_path):
            # Pour le moment, pas de "title" textuel distinct → on évite Keys:Title = description
            args += [f"-Keys:Description{desc_tag}{meta.description}"]

    # Personnes
    people_tag = "+=" if not append_only else "-+="
    for person in meta.people:
        args += [
            f"-XMP-iptcExt:PersonInImage{people_tag}{person}",
            f"-XMP-dc:Subject{people_tag}{person}",
            f"-IPTC:Keywords{people_tag}{person}",
        ]

    # Albums
    album_tag = "+=" if not append_only else "-+="
    for album in meta.albums:
        album_keyword = f"Album: {album}"
        args += [
            f"-XMP-dc:Subject{album_tag}{album_keyword}",
            f"-IPTC:Keywords{album_tag}{album_keyword}",
        ]

    # Rating/Favoris
    if meta.favorite:
        rating_tag = "=" if not append_only else "-="
        args.append(f"-XMP:Rating{rating_tag}5")

    # Set standard EXIF date fields:
    # - DateTimeOriginal is set from meta.taken_at (when the photo/video was taken)
    # - CreateDate and ModifyDate are set from meta.created_at if available, otherwise from meta.taken_at
    date_tag = "=" if not append_only else "-="
    if (s := _fmt_dt(meta.taken_at, use_localtime)):
        args.append(f"-DateTimeOriginal{date_tag}{s}")

    base_ts = meta.created_at or meta.taken_at
    if (s := _fmt_dt(base_ts, use_localtime)):
        args += [f"-CreateDate{date_tag}{s}", f"-ModifyDate{date_tag}{s}"]

    # Dates QuickTime (vidéos)
    if image_path and _is_video_file(image_path):
        if (s := _fmt_dt(meta.taken_at, use_localtime)):
            args += [f"-QuickTime:CreateDate{date_tag}{s}"]
        if (s := _fmt_dt(base_ts, use_localtime)):
            args += [f"-QuickTime:ModifyDate{date_tag}{s}"]
        if meta.description:
            desc_tag = "=" if not append_only else "-="
            args += [f"-Keys:Description{desc_tag}{meta.description}"]

    # GPS
    if meta.latitude is not None and meta.longitude is not None:
        lat_ref = "N" if meta.latitude >= 0 else "S"
        lon_ref = "E" if meta.longitude >= 0 else "W"
        args += [
            f"-GPSLatitude={abs(meta.latitude)}",
            f"-GPSLatitudeRef={lat_ref}",
            f"-GPSLongitude={abs(meta.longitude)}",
            f"-GPSLongitudeRef={lon_ref}",
        ]
        if meta.altitude is not None:
            alt_ref = "1" if meta.altitude < 0 else "0"
            args += [f"-GPSAltitude={abs(meta.altitude)}", f"-GPSAltitudeRef={alt_ref}"]

        if image_path and _is_video_file(image_path):
            # QuickTime:GPSCoordinates accepte "lat lon" ou "lat,lon" selon les players ; cette forme marche en général
            args += [f"-QuickTime:GPSCoordinates={meta.latitude},{meta.longitude}"]
            # Keys:Location est peu standardisé ; garde-le si ça t’aide dans ton écosystème
            args += [f"-Keys:Location={meta.latitude},{meta.longitude}"]

    return args

def write_metadata(image_path: Path, meta: SidecarData, use_localtime: bool = False, append_only: bool = False) -> None:
    args = build_exiftool_args(meta, image_path, use_localtime=use_localtime, append_only=append_only)
    if not args:
        return

    cmd = [
        "exiftool",
        "-overwrite_original",
        "-charset", "filename=UTF8",
        "-charset", "iptc=UTF8",
        "-charset", "exif=UTF8",
        "-charset", "XMP=UTF8",
        *args,
        str(image_path),
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60, encoding='utf-8')
    except FileNotFoundError as exc:
        raise RuntimeError("exiftool not found") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"exiftool failed for {image_path}: {exc.stderr or exc.stdout}") from exc

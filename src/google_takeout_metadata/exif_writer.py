"""Write metadata to images using the external ``exiftool`` utility."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List
import subprocess
import tempfile

from .sidecar import SidecarData


def build_exiftool_args(meta: SidecarData) -> List[str]:
    """Return a list of arguments for ``exiftool`` based on ``meta``."""

    args: List[str] = []

    if meta.description:
        args.extend(
            [
                f"-EXIF:ImageDescription={meta.description}",
                f"-XMP-dc:Description={meta.description}",
                f"-IPTC:Caption-Abstract={meta.description}",
            ]
        )

    for person in meta.people:
        args.extend(
            [
                f"-XMP-iptcExt:PersonInImage+={person}",
                f"-XMP-dc:Subject+={person}",
                f"-IPTC:Keywords+={person}",
            ]
        )

    if meta.taken_at is not None:
        dt = datetime.fromtimestamp(meta.taken_at, tz=timezone.utc)
        formatted = dt.strftime("%Y:%m:%d %H:%M:%S")
        args.append(f"-DateTimeOriginal={formatted}")

    base_ts = meta.created_at or meta.taken_at
    if base_ts is not None:
        dt = datetime.fromtimestamp(base_ts, tz=timezone.utc)
        formatted = dt.strftime("%Y:%m:%d %H:%M:%S")
        args.extend([f"-CreateDate={formatted}", f"-ModifyDate={formatted}"])

    if meta.latitude is not None and meta.longitude is not None:
        lat_ref = "N" if meta.latitude >= 0 else "S"
        lon_ref = "E" if meta.longitude >= 0 else "W"
        args.extend(
            [
                f"-GPSLatitude={abs(meta.latitude)}",
                f"-GPSLatitudeRef={lat_ref}",
                f"-GPSLongitude={abs(meta.longitude)}",
                f"-GPSLongitudeRef={lon_ref}",
            ]
        )
        if meta.altitude is not None:
            alt_ref = "1" if meta.altitude < 0 else "0"
            args.extend(
                [
                    f"-GPSAltitude={abs(meta.altitude)}",
                    f"-GPSAltitudeRef={alt_ref}",
                ]
            )

    return args


def write_metadata(image_path: Path, meta: SidecarData) -> None:
    """Write ``meta`` into ``image_path``.

    Raises
    ------
    RuntimeError
        If ``exiftool`` exits with a non-zero status.
    """

    args = build_exiftool_args(meta)
    if not args:
        return

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as fh:
        fh.write("\n".join(args))
        arg_path = fh.name
    cmd = ["exiftool", "-overwrite_original", "-@", arg_path, str(image_path)]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
    except FileNotFoundError as exc:  # pragma: no cover - depends on system
        ...
        raise RuntimeError("exiftool not found") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"exiftool failed for {image_path}: {exc.stderr or exc.stdout}"
        ) from exc
    finally:
        Path(arg_path).unlink(missing_ok=True)

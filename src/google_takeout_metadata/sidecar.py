from __future__ import annotations

"""Parsing of Google Takeout JSON sidecar files."""

from dataclasses import dataclass
from pathlib import Path
import json
from typing import List, Optional


@dataclass
class SidecarData:
    """Selected metadata extracted from a Google Photos sidecar JSON."""

    filename: str
    description: Optional[str]
    people: List[str]
    taken_at: Optional[int]
    created_at: Optional[int]
    latitude: Optional[float]
    longitude: Optional[float]
    altitude: Optional[float]


def parse_sidecar(path: Path) -> SidecarData:
    """Parse ``path`` and return :class:`SidecarData`.

    The function validates that the embedded ``title`` field matches the sidecar
    filename to avoid applying metadata to the wrong image.
    """

    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError as exc:  # pragma: no cover - simple wrapper
        raise FileNotFoundError(f"Sidecar not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}") from exc

    title = data.get("title")
    if not title:
        raise ValueError(f"Missing 'title' in {path}")
    if path.stem != title:
        raise ValueError(
            f"Sidecar title {title!r} does not match filename {path.name!r}"
        )

    description = data.get("description")
    people = [p["name"] for p in data.get("people", []) if "name" in p]

    def get_ts(key: str) -> Optional[int]:
        ts = data.get(key, {}).get("timestamp")
        if ts is None:
            return None
        try:
            return int(ts)
        except (TypeError, ValueError):
            return None

    taken_at = get_ts("photoTakenTime")
    created_at = get_ts("creationTime")

    geo = data.get("geoData", {})
    latitude = geo.get("latitude")
    longitude = geo.get("longitude")
    altitude = geo.get("altitude")
    lat_span = geo.get("latitudeSpan")
    lon_span = geo.get("longitudeSpan")
    
    # Clear coordinates if both latitude and longitude are None
    # Keep actual 0.0 coordinates as they may be valid (like equator/prime meridian)
    if latitude is None or longitude is None:
        latitude = longitude = altitude = None

    return SidecarData(
        filename=title,
        description=description,
        people=people,
        taken_at=taken_at,
        created_at=created_at,
        latitude=latitude,
        longitude=longitude,
        altitude=altitude,
    )

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
    favorite: bool = False
    lat_span: Optional[float] = None
    lon_span: Optional[float] = None
    albums: List[str] = None
    image_views: Optional[int] = None
    archived: bool = False
    trashed: bool = False
    google_photos_url: Optional[str] = None

    def __post_init__(self):
        """Initialize albums as empty list if None."""
        if self.albums is None:
            self.albums = []


def parse_sidecar(path: Path) -> SidecarData:
    """Parse ``path`` and return :class:`SidecarData`.

    The function validates that the embedded ``title`` field matches the sidecar
    filename to avoid applying metadata to the wrong image.
    
    Supports both formats:
    - New format: photo.jpg.supplemental-metadata.json -> title should be "photo.jpg"
    - Legacy format: photo.jpg.json -> title should be "photo.jpg"
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
    
    # Extract expected filename from sidecar path
    # For new format: IMG_001.jpg.supplemental-metadata.json -> expected title: IMG_001.jpg
    # For legacy format: IMG_001.jpg.json -> expected title: IMG_001.jpg
    if path.name.endswith(".supplemental-metadata.json"):
        expected_title = path.name[:-len(".supplemental-metadata.json")]
    elif path.name.endswith(".json"):
        expected_title = path.stem
    else:
        expected_title = path.stem
    
    if expected_title != title:
        raise ValueError(
            f"Sidecar title {title!r} does not match expected filename {expected_title!r} from {path.name!r}"
        )

    description = data.get("description")
    # Extract people names, strip whitespace, and deduplicate
    # people peut être [{ "name": "X" }] ou parfois [{ "person": { "name": "X" } }]
    raw_people = data.get("people", []) or []
    people = []
    for p in raw_people:
        if isinstance(p, dict):
            if isinstance(p.get("name"), str):
                people.append(p["name"].strip())
            elif isinstance(p.get("person"), dict) and isinstance(p["person"].get("name"), str):
                people.append(p["person"]["name"].strip())
    # déduplication
    people = sorted(set(filter(None, people)))


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

    # Extract geographical data - prefer geoData, fallback to geoDataExif
    geo = data.get("geoData", {})
    if not geo or not geo.get("latitude"):
        geo = data.get("geoDataExif", {})
    
    latitude = geo.get("latitude")
    longitude = geo.get("longitude")
    altitude = geo.get("altitude")
    lat_span = geo.get("latitudeSpan")
    lon_span = geo.get("longitudeSpan")
    
    # Clear coordinates if both latitude and longitude are None
    # Keep actual 0.0 coordinates as they may be valid (like equator/prime meridian)
    # Google met parfois 0/0 quand pas de géo fiable → on nettoie
    if any(v in (0, 0.0, None) for v in (latitude, longitude)):
        latitude = longitude = altitude = None

    # Extract favorite status - support both formats
    favorited_data = data.get("favorited")
    if isinstance(favorited_data, bool):
        # Direct boolean format: "favorited": true
        favorite = favorited_data
    elif isinstance(favorited_data, dict):
        # Object format: "favorited": {"value": true}
        favorite = bool(favorited_data.get("value", False))
    else:
        favorite = False

    # Extract additional metadata
    image_views = data.get("imageViews")
    if image_views is not None:
        try:
            image_views = int(image_views)
        except (TypeError, ValueError):
            image_views = None
    
    archived = bool(data.get("archived", False))
    trashed = bool(data.get("trashed", False))
    google_photos_url = data.get("url")

    return SidecarData(
        filename=title,
        description=description,
        people=people,
        taken_at=taken_at,
        created_at=created_at,
        latitude=latitude,
        longitude=longitude,
        altitude=altitude,
        favorite=favorite,
        lat_span=lat_span,
        lon_span=lon_span,
    )


def parse_album_metadata(path: Path) -> List[str]:
    """Parse album metadata.json file and return list of album names.
    
    Google Takeout album metadata.json files typically contain:
    {
        "title": "Album Name",
        "description": "...",
        ...
    }
    
    Returns a list of album names found in the file.
    """
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    
    albums = []
    
    # Primary album name from title field
    title = data.get("title")
    if title and isinstance(title, str):
        albums.append(title.strip())
    
    # Some metadata.json files might have multiple album references
    # Check if there are album references in other fields
    album_refs = data.get("albums", [])
    if isinstance(album_refs, list):
        for album_ref in album_refs:
            if isinstance(album_ref, dict) and "title" in album_ref:
                album_name = album_ref["title"]
                if isinstance(album_name, str):
                    albums.append(album_name.strip())
            elif isinstance(album_ref, str):
                albums.append(album_ref.strip())
    
    # Remove duplicates and empty strings
    albums = sorted(set(filter(None, albums)))
    
    return albums


def find_albums_for_directory(directory: Path) -> List[str]:
    """Find all album names that apply to photos in the given directory.
    
    Looks for metadata.json files in the directory and parent directories
    to collect album information.
    
    Supports multiple metadata file patterns:
    - metadata.json (English)
    - métadonnées.json (French)
    - métadonnées(1).json, métadonnées(2).json, etc. (French with duplicates)
    - album_metadata.json, folder_metadata.json (legacy)
    """
    albums = []
    
    # Check current directory for various metadata file patterns
    metadata_patterns = [
        "metadata.json",
        "métadonnées.json", 
        "album_metadata.json", 
        "folder_metadata.json"
    ]
    
    for pattern in metadata_patterns:
        metadata_file = directory / pattern
        if metadata_file.exists():
            albums.extend(parse_album_metadata(metadata_file))
    
    # Also check for numbered variations like métadonnées(1).json, métadonnées(2).json, etc.
    for metadata_file in directory.glob("métadonnées*.json"):
        if metadata_file.name not in ["métadonnées.json"]:  # already checked above
            albums.extend(parse_album_metadata(metadata_file))
    
    return sorted(set(albums))

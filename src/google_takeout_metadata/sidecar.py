from __future__ import annotations

"""Analyse des fichiers annexes JSON de Google Takeout."""

from dataclasses import dataclass
from pathlib import Path
import json
from typing import List, Optional


@dataclass
class SidecarData:
    """Métadonnées sélectionnées extraites d'un JSON annexe Google Photos."""

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
    archived: bool = False

    def __post_init__(self):
        """Initialiser ``albums`` comme liste vide si ``None``."""
        if self.albums is None:
            self.albums = []


def parse_sidecar(path: Path) -> SidecarData:
    """Analyser ``path`` et retourner :class:`SidecarData`.

    La fonction vérifie que le champ ``title`` intégré correspond au nom de fichier
    du sidecar pour éviter d'appliquer des métadonnées au mauvais média.
    
    Formats supportés :
    - Nouveau format : photo.jpg.supplemental-metadata.json -> title attendu "photo.jpg"
    - Ancien format : photo.jpg.json -> title attendu "photo.jpg"
    """

    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError as exc:  # pragma: no cover - simple wrapper
        raise FileNotFoundError(f"Sidecar introuvable : {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalide dans {path}") from exc

    title = data.get("title")
    if not title:
        raise ValueError(f"Champ 'title' manquant dans {path}")
    
    # Extraire le nom de fichier attendu depuis le chemin du sidecar
    # Pour le nouveau format : IMG_001.jpg.supplemental-metadata.json -> titre attendu : IMG_001.jpg
    # Pour le format hérité : IMG_001.jpg.json -> titre attendu : IMG_001.jpg
    if path.name.lower().endswith(".supplemental-metadata.json"):
        expected_title = path.name[:-len(".supplemental-metadata.json")]
    elif path.name.lower().endswith(".json"):
        expected_title = path.stem
    else:
        expected_title = path.stem
    if expected_title != title:
        raise ValueError(
            f"Le titre du sidecar {title!r} ne correspond pas au nom de fichier attendu {expected_title!r} provenant de {path.name!r}"
        )

    description = data.get("description")
    # Extraire les noms de personnes, supprimer les espaces et dédupliquer
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

    # Extraire les données géographiques - préférer geoData, repli sur geoDataExif
    geo = data.get("geoData", {})
    if not geo or not geo.get("latitude"):
        geo = data.get("geoDataExif", {})
    
    latitude = geo.get("latitude")
    longitude = geo.get("longitude")
    altitude = geo.get("altitude")
    lat_span = geo.get("latitudeSpan")
    lon_span = geo.get("longitudeSpan")
    
    # Nettoyer les coordonnées si latitude et longitude sont None
    # Conserver les vraies coordonnées 0.0 car elles peuvent être valides (équateur/méridien de Greenwich)
    # Google met parfois 0/0 quand pas de géo fiable → on nettoie
    if any(v in (0, 0.0, None) for v in (latitude, longitude)):
        latitude = longitude = altitude = None

    # Extraire le statut favori - support des deux formats
    favorited_data = data.get("favorited")
    if isinstance(favorited_data, bool):
        # Format booléen direct : "favorited": true
        favorite = favorited_data
    elif isinstance(favorited_data, dict):
        # Format objet : "favorited": {"value": true}
        favorite = bool(favorited_data.get("value", False))
    else:
        favorite = False

    # Extraire le statut archivé
    archived = bool(data.get("archived", False))

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
        archived=archived,
    )


def parse_album_metadata(path: Path) -> List[str]:
    """Analyser un fichier metadata.json d'album et retourner la liste des noms d'albums.
    
    Les fichiers metadata.json d'albums (Google Takeout) contiennent généralement :
    {
        "title": "Nom de l'album",
        "description": "...",
        ...
    }
    
    Retourne une liste des noms d'albums trouvés dans le fichier.
    """
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    
    albums = []
    
    # Nom d'album principal depuis le champ title
    title = data.get("title")
    if title and isinstance(title, str):
        albums.append(title.strip())
    
    # Certains fichiers metadata.json peuvent avoir plusieurs références d'albums
    # Vérifier s'il y a des références d'albums dans d'autres champs
    album_refs = data.get("albums", [])
    if isinstance(album_refs, list):
        for album_ref in album_refs:
            if isinstance(album_ref, dict) and "title" in album_ref:
                album_name = album_ref["title"]
                if isinstance(album_name, str):
                    albums.append(album_name.strip())
            elif isinstance(album_ref, str):
                albums.append(album_ref.strip())
    
    # Supprimer les doublons et les chaînes vides
    albums = sorted(set(filter(None, albums)))
    
    return albums


def find_albums_for_directory(directory: Path) -> List[str]:
    """Trouver tous les noms d'albums applicables aux photos du répertoire donné.
    
    Recherche des fichiers metadata.json dans le répertoire et ses parents
    pour collecter les informations d'album.
    
    Prend en charge plusieurs motifs de fichiers metadata :
    - metadata.json (anglais)
    - métadonnées.json (français)
    - métadonnées(1).json, métadonnées(2).json, etc. (français avec doublons)
    - album_metadata.json, folder_metadata.json (hérités)
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

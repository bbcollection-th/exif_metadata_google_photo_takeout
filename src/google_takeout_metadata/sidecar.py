from __future__ import annotations


from dataclasses import dataclass, field
from pathlib import Path
import json
import logging
from typing import List, Optional
"""Analyse des fichiers annexes JSON de Google Takeout."""

logger = logging.getLogger(__name__)


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
    albums: List[str] = field(default_factory=list)
    archived: bool = False


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
    
    # Nettoyer les coordonnées seulement si les DEUX sont à 0/None
    # Conserver les vraies coordonnées 0.0 car elles peuvent être valides (équateur/méridien de Greenwich)
    # Google met parfois 0/0 quand pas de géo fiable → on nettoie uniquement dans ce cas
    if ((latitude in (0, 0.0, None)) and (longitude in (0, 0.0, None))) or \
       (latitude is None or longitude is None):
        latitude = longitude = altitude = None

    # Extraire le statut favori - format booléen Google Takeout
    # Note : "favorited": true si favori, champ absent si pas favori (pas false)
    favorite = bool(data.get("favorited", False))

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


def find_albums_for_directory(directory: Path, max_depth: int = 5) -> List[str]:
    """Trouver tous les noms d'albums applicables aux photos du répertoire donné.
    
    Recherche des fichiers metadata.json dans le répertoire et ses parents
    pour collecter les informations d'album.
    
    Args:
        directory: Répertoire de départ pour la recherche
        max_depth: Nombre maximum de niveaux parents à vérifier (défaut: 5)
    
    Prend en charge plusieurs motifs de fichiers metadata :
    - metadata.json (anglais)
    - métadonnées.json (français)  
    - métadonnées(1).json, métadonnées(2).json, etc. (français avec doublons)
    - album_metadata.json, folder_metadata.json (hérités)
    """
    albums = []
    
    metadata_patterns = [
        "metadata.json",
        "métadonnées.json", 
        "album_metadata.json", 
        "folder_metadata.json"
    ]
    
    # Rechercher dans le répertoire courant et ses parents avec limite de profondeur
    current_dir = directory
    depth = 0
    
    # Motifs de répertoires marqueurs (insensibles à la casse)
    takeout_markers = ["google photos", "takeout", "google takeout"]
    
    while current_dir != current_dir.parent and depth < max_depth:
        # Vérifier les motifs standards (insensible à la casse)
        for pattern in metadata_patterns:
            # Rechercher le fichier avec la casse exacte d'abord
            metadata_file = current_dir / pattern
            if metadata_file.exists():
                try:
                    albums.extend(parse_album_metadata(metadata_file))
                except (OSError, PermissionError) as e:
                    # Ignorer les erreurs de parsing et continuer
                    logger.debug(f"Erreur lors du parsing de {metadata_file}: {e}")
            else:
                # Rechercher de manière insensible à la casse si pas trouvé
                try:
                    for existing_file in current_dir.iterdir():
                        if existing_file.is_file() and existing_file.name.lower() == pattern.lower():
                            try:
                                albums.extend(parse_album_metadata(existing_file))
                            except (OSError, PermissionError) as e:
                                logger.debug(f"Erreur lors du parsing de {existing_file}: {e}")
                            break  # Un seul fichier correspondant par motif
                except (OSError, PermissionError):
                    # Ignorer les erreurs d'accès au répertoire
                    logger.debug(f"Impossible d'accéder au répertoire {current_dir}")
        
        # Vérifier les variations numérotées comme métadonnées(1).json, métadonnées(2).json, etc.
        # (recherche insensible à la casse)
        try:
            for metadata_file in current_dir.iterdir():
                if (metadata_file.is_file() and 
                    metadata_file.name.lower().startswith("métadonnées") and 
                    metadata_file.name.lower().endswith(".json") and
                    metadata_file.name.lower() not in ["métadonnées.json"]):  # déjà vérifié ci-dessus
                    try:
                        albums.extend(parse_album_metadata(metadata_file))
                    except (OSError, PermissionError) as e:
                        # Ignorer les erreurs de parsing et continuer
                        logger.debug(f"Erreur lors du parsing de {metadata_file}: {e}")
        except (OSError, PermissionError):
            # Ignorer les erreurs d'accès au répertoire et continuer
            logger.debug(f"Impossible d'accéder au répertoire {current_dir}")
        
        # Arrêter si on atteint un répertoire "marqueur" de Google Takeout
        # pour éviter de remonter trop haut dans l'arborescence
        if any(marker in current_dir.name.lower() for marker in takeout_markers):
            logger.debug(f"Arrêt de la recherche d'albums au répertoire marqueur: {current_dir}")
            break
        
        # Remonter au répertoire parent
        current_dir = current_dir.parent
        depth += 1
    
    # Déduplication et tri tout en préservant l'ordre de priorité
    # (répertoires plus proches en premier)
    unique_albums = []
    seen = set()
    for album in albums:
        if album not in seen:
            unique_albums.append(album)
            seen.add(album)
    
    return unique_albums

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
    """Métadonnées extraites du sidecar JSON - noms mappés aux champs JSON réels."""
    
    # Identité du fichier (champ JSON direct)
    title: str
    
    # Métadonnées de base (champs JSON directs)
    description: Optional[str] = None
    people_name: List[str] = field(default_factory=list)  # Extrait de people[].name
    
    # Timestamps (sous-champs JSON)
    photoTakenTime_timestamp: Optional[int] = None
    creationTime_timestamp: Optional[int] = None
    
    # Géolocalisation (sous-champs de geoData)
    geoData_latitude: Optional[float] = None
    geoData_longitude: Optional[float] = None
    geoData_altitude: Optional[float] = None
    geoData_latitudeSpan: Optional[float] = None
    geoData_longitudeSpan: Optional[float] = None
    
    # États/flags (champs JSON directs)
    favorited: bool = False
    archived: bool = False
    trashed: bool = False
    inLockedFolder: bool = False
    
    # Métadonnées d'origine (chemin JSON complexe : googlePhotosOrigin.mobileUpload.deviceFolder.localFolderName)
    googlePhotosOrigin_localFolderName: Optional[str] = None
    
    # Données organisationnelles (calculées séparément)
    albums: List[str] = field(default_factory=list)
    
    # Données calculées par géocodage (à déplacer vers EnrichedSidecarData)
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    place_name: Optional[str] = None
    
    # === Propriétés de compatibilité pour maintenir l'ancienne API ===
    @property
    def filename(self) -> str:
        """Alias pour title (compatibilité)"""
        return self.title
    
    @property
    def people(self) -> List[str]:
        """Alias pour people_name (compatibilité)"""
        return self.people_name
    
    @property
    def taken_at(self) -> Optional[int]:
        """Alias pour photoTakenTime_timestamp (compatibilité)"""
        return self.photoTakenTime_timestamp
    
    @property
    def created_at(self) -> Optional[int]:
        """Alias pour creationTime_timestamp (compatibilité)"""
        return self.creationTime_timestamp
    
    @property
    def latitude(self) -> Optional[float]:
        """Alias pour geoData_latitude (compatibilité)"""
        return self.geoData_latitude
    
    @property
    def longitude(self) -> Optional[float]:
        """Alias pour geoData_longitude (compatibilité)"""
        return self.geoData_longitude
    
    @property
    def altitude(self) -> Optional[float]:
        """Alias pour geoData_altitude (compatibilité)"""
        return self.geoData_altitude
    
    @property
    def lat_span(self) -> Optional[float]:
        """Alias pour geoData_latitudeSpan (compatibilité)"""
        return self.geoData_latitudeSpan
    
    @property
    def lon_span(self) -> Optional[float]:
        """Alias pour geoData_longitudeSpan (compatibilité)"""
        return self.geoData_longitudeSpan
    
    @property
    def favorite(self) -> bool:
        """Alias pour favorited (compatibilité)"""
        return self.favorited
    
    @property
    def locked(self) -> bool:
        """Alias pour inLockedFolder (compatibilité)"""
        return self.inLockedFolder
    
    @property
    def local_folder_name(self) -> Optional[str]:
        """Alias pour googlePhotosOrigin_localFolderName (compatibilité)"""
        return self.googlePhotosOrigin_localFolderName
    
    @property
    def localFolderName(self) -> Optional[str]:
        """Alias pour googlePhotosOrigin_localFolderName (compatibilité avec ton changement)"""
        return self.googlePhotosOrigin_localFolderName


@dataclass
class EnrichedSidecarData:
    """Données sidecar enrichies par géocodage et analyse"""
    sidecar: SidecarData
    
    # Données calculées par géocodage
    city: Optional[str] = None
    state: Optional[str] = None  
    country: Optional[str] = None
    place_name: Optional[str] = None
    
    # Données organisationnelles (calculées)
    albums: List[str] = field(default_factory=list)


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
    # Pour le nouveau format : IMG_001.jpg.supplemental-metadata.json -> filename attendu : IMG_001.jpg
    # Pour le format hérité : IMG_001.jpg.json -> filename attendu : IMG_001.jpg
    if path.name.lower().endswith(".supplemental-metadata.json"):
        expected_filename = path.name[:-len(".supplemental-metadata.json")]
    elif path.name.lower().endswith(".supplemental-metadat.json"):
        expected_filename = path.name[:-len(".supplemental-metadat.json")]
    elif path.name.lower().endswith(".supplemental-me.json"):
        expected_filename = path.name[:-len(".supplemental-me.json")]
    elif path.name.lower().endswith(".supplemental-meta.json"):
        expected_filename = path.name[:-len(".supplemental-meta.json")]
    elif path.name.lower().endswith(".json"):
        expected_filename = path.stem
    else:
        expected_filename = path.stem
    if expected_filename != title:
        raise ValueError(
            f"Le titre du sidecar {title!r} ne correspond pas au nom de fichier attendu {expected_filename!r} provenant de {path.name!r}"
        )

    description = data.get("description")
    # Extraire les noms de personnes, supprimer les espaces et dédupliquer
    # Gère plusieurs formats :
    # - [{ "name": "X" }]
    raw_people = data.get("people", []) or []
    people_name = []
    for p in raw_people:
        if isinstance(p, dict):
            # Format standard : {"name": "X"}
            if isinstance(p.get("name"), str):
                people_name.append(p["name"].strip())
    # déduplication
    people_name = sorted(set(filter(None, people_name)))


    def get_ts(key: str) -> Optional[int]:
        ts = data.get(key, {}).get("timestamp")
        if ts is None:
            return None
        try:
            return int(ts)
        except (TypeError, ValueError):
            return None

    photoTakenTime_timestamp = get_ts("photoTakenTime")
    creationTime_timestamp = get_ts("creationTime")

    # Extraire les données géographiques - préférer geoData, repli sur geoDataExif
    geo = data.get("geoData", {})
    if not geo or not geo.get("latitude"):
        geo = data.get("geoDataExif", {})
    
    geoData_latitude = geo.get("latitude")
    geoData_longitude = geo.get("longitude")
    geoData_altitude = geo.get("altitude")
    geoData_latitudeSpan = geo.get("latitudeSpan")
    geoData_longitudeSpan = geo.get("longitudeSpan")
    
    # Nettoyer les coordonnées seulement si les DEUX sont à 0/None
    # Conserver les vraies coordonnées 0.0 car elles peuvent être valides (équateur/méridien de Greenwich)
    # Google met parfois 0/0 quand pas de géo fiable → on nettoie uniquement dans ce cas
    if ((geoData_latitude in (0, 0.0, None)) and (geoData_longitude in (0, 0.0, None))) or \
       (geoData_latitude is None or geoData_longitude is None):
        geoData_latitude = geoData_longitude = geoData_altitude = None

    # Extraire le statut favori - format booléen Google Takeout
    # Note : "favorited": true si favori, champ absent si pas favori (pas false)
    favorited = bool(data.get("favorited", False))

    # Extraire le statut archivé
    archived = bool(data.get("archived", False))

    # Extraire le statut corbeille
    trashed = bool(data.get("trashed", False))

    # Extraire le statut d'album vérouillé
    inLockedFolder = bool(data.get("inLockedFolder", False))

    # Extraire le nom du dossier local de l'appareil
    googlePhotosOrigin_localFolderName = None
    google_photos_origin = data.get("googlePhotosOrigin", {})
    if isinstance(google_photos_origin, dict):
        mobile_upload = google_photos_origin.get("mobileUpload", {})
        if isinstance(mobile_upload, dict):
            device_folder = mobile_upload.get("deviceFolder", {})
            if isinstance(device_folder, dict):
                folder_name = device_folder.get("localFolderName")
                if isinstance(folder_name, str) and folder_name.strip():
                    googlePhotosOrigin_localFolderName = folder_name.strip()

    return SidecarData(
        title=title,
        description=description,
        people_name=people_name,
        photoTakenTime_timestamp=photoTakenTime_timestamp,
        creationTime_timestamp=creationTime_timestamp,
        geoData_latitude=geoData_latitude,
        geoData_longitude=geoData_longitude,
        geoData_altitude=geoData_altitude,
        geoData_latitudeSpan=geoData_latitudeSpan,
        geoData_longitudeSpan=geoData_longitudeSpan,
        favorited=favorited,
        archived=archived,
        trashed=trashed,
        inLockedFolder=inLockedFolder,
        googlePhotosOrigin_localFolderName=googlePhotosOrigin_localFolderName,
        albums=[],  # Les albums sont gérés séparément
        city=None,
        state=None,
        country=None,
        place_name=None,
    )


def parse_album_metadata(path: Path) -> List[str]:
    """Analyser un fichier metadata.json d'album et retourner la liste des noms d'albums.
    
    Les fichiers metadata.json d'albums (Google Takeout) contiennent généralement :
    {
        "title": "halloween",
        "description": "",
        "access": "protected",
        "date": {
            "timestamp": "1730287676",
            "formatted": "30 oct. 2024, 11:27:56 UTC"
        }
    }
    
    Un seul album par fichier metadata.json.
    Retourne une liste avec le nom de l'album (ou liste vide si erreur).
    """
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    
    # Nom d'album depuis le champ title
    title = data.get("title")
    if title and isinstance(title, str):
        title = title.strip()
        if title:  # Vérifier que le titre n'est pas vide après nettoyage
            return [title]
    
    return []


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

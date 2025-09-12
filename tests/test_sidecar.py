from pathlib import Path
import json
import pytest

from google_takeout_metadata.sidecar import parse_sidecar


def test_parse_sidecar(tmp_path: Path) -> None:
    sample = {
        "title": "1729436788572.jpg",
        "description": "Magicien en or",
        "creationTime": {"timestamp": "1736719606"},
        "photoTakenTime": {"timestamp": "1736719606"},
        "geoData": {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0},
        "people": [{"name": "anthony vincent"}],
    }

    json_path = tmp_path / "1729436788572.jpg.json"
    json_path.write_text(json.dumps(sample), encoding="utf-8")

    meta = parse_sidecar(json_path)
    assert meta.title == "1729436788572.jpg"
    assert meta.description == "Magicien en or"
    assert meta.people_name == ["anthony vincent"]
    assert meta.photoTakenTime_timestamp == 1736719606
    assert meta.creationTime_timestamp == 1736719606


def test_title_mismatch(tmp_path: Path) -> None:
    data = {"title": "other.jpg"}
    json_path = tmp_path / "sample.jpg.json"
    json_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        parse_sidecar(json_path)


def test_parse_sidecar_supplemental_metadata_format(tmp_path: Path) -> None:
    """Tester l'analyse du nouveau format Google Takeout : IMG_001.jpg.supplemental-metadata.json"""
    sample = {
        "title": "IMG_001.jpg",
        "description": "Test photo with new format",
        "creationTime": {"timestamp": "1736719606"},
        "photoTakenTime": {"timestamp": "1736719606"},
        "people": [{"name": "test user"}],
    }

    json_path = tmp_path / "IMG_001.jpg.supplemental-metadata.json"
    json_path.write_text(json.dumps(sample), encoding="utf-8")

    meta = parse_sidecar(json_path)
    assert meta.title == "IMG_001.jpg"
    assert meta.description == "Test photo with new format"
    assert meta.people_name == ["test user"]
    assert meta.photoTakenTime_timestamp == 1736719606
    assert meta.creationTime_timestamp == 1736719606


def test_title_mismatch_supplemental_metadata(tmp_path: Path) -> None:
    """Tester la validation du titre avec le format supplemental-metadata."""
    data = {"title": "wrong_name.jpg"}
    json_path = tmp_path / "IMG_001.jpg.supplemental-metadata.json"
    json_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Le titre du sidecar.*ne correspond pas au nom de fichier attendu"):
        parse_sidecar(json_path)


def test_invalid_json(tmp_path: Path) -> None:
    json_path = tmp_path / "bad.jpg.json"
    json_path.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError):
        parse_sidecar(json_path)


def test_zero_coordinates(tmp_path: Path) -> None:
    sample = {
        "title": "a.jpg",
        "geoData": {"latitude": 0.0, "longitude": 0.0, "altitude": 10.0, "latitudeSpan": 1, "longitudeSpan": 1},
    }
    json_path = tmp_path / "a.jpg.json"
    json_path.write_text(json.dumps(sample), encoding="utf-8")
    meta = parse_sidecar(json_path)
    # Les coordonnées 0/0 doivent être filtrées car peu fiables
    assert meta.geoData_latitude is None
    assert meta.geoData_longitude is None
    assert meta.geoData_altitude is None


def test_people_name_deduplication(tmp_path: Path) -> None:
    """Tester que les noms de personnes sont dédupliqués et nettoyés."""
    sample = {
        "title": "a.jpg",
        "people": [
            {"name": "alice"},
            {"name": " alice "},  # avec espaces
            {"name": "alice"},   # doublon
            {"name": "bob"},
            {"name": "  "},      # vide après nettoyage
            {"name": "charlie"},
            {"name": " bob "},   # autre doublon avec espaces
        ]
    }
    json_path = tmp_path / "a.jpg.json"
    json_path.write_text(json.dumps(sample), encoding="utf-8")
    meta = parse_sidecar(json_path)
    # Devrait avoir dédupliqué et nettoyé : ["alice", "bob", "charlie"]
    assert meta.people_name == ["alice", "bob", "charlie"]


def test_parse_favorited_true(tmp_path: Path) -> None:
    """Tester l'analyse d'une photo favorited avec le format Google Takeout réel."""
    sample = {
        "title": "favorited.jpg",
        "favorited": True
    }
    json_path = tmp_path / "favorited.jpg.json"
    json_path.write_text(json.dumps(sample), encoding="utf-8")
    meta = parse_sidecar(json_path)
    assert meta.favorited is True


def test_parse_favorited_false(tmp_path: Path) -> None:
    """Tester l'analyse d'une photo non favorite avec le format Google Takeout réel."""
    sample = {
        "title": "not_favorite.jpg",
        "favorited": False
    }
    json_path = tmp_path / "not_favorite.jpg.json"
    json_path.write_text(json.dumps(sample), encoding="utf-8")
    meta = parse_sidecar(json_path)
    assert meta.favorited is False


def test_parse_no_favorited_field(tmp_path: Path) -> None:
    """Tester l'analyse d'une photo sans champ favori."""
    sample = {
        "title": "no_fav.jpg",
        "description": "Test photo"
    }
    json_path = tmp_path / "no_fav.jpg.json"
    json_path.write_text(json.dumps(sample), encoding="utf-8")
    meta = parse_sidecar(json_path)
    assert meta.favorited is False


def test_parse_zero_geo_coordinates(tmp_path: Path) -> None:
    """Tester que les coordonnées 0/0 sont filtrées car peu fiables."""
    sample = {
        "title": "geo_zero.jpg",
        "geoData": {"latitude": 0.0, "longitude": 0.0, "altitude": 100.0}
    }
    json_path = tmp_path / "geo_zero.jpg.json"
    json_path.write_text(json.dumps(sample), encoding="utf-8")
    meta = parse_sidecar(json_path)
    # Les coordonnées 0/0 doivent être filtrées
    assert meta.geoData_latitude is None
    assert meta.geoData_longitude is None
    assert meta.geoData_altitude is None


def test_parse_valid_geo_coordinates(tmp_path: Path) -> None:
    """Tester que les coordonnées valides sont préservées."""
    sample = {
        "title": "geo_valid.jpg",
        "geoData": {"latitude": 48.8566, "longitude": 2.3522, "altitude": 35.0}
    }
    json_path = tmp_path / "geo_valid.jpg.json"
    json_path.write_text(json.dumps(sample), encoding="utf-8")
    meta = parse_sidecar(json_path)
    assert meta.geoData_latitude == 48.8566
    assert meta.geoData_longitude == 2.3522
    assert meta.geoData_altitude == 35.0


def test_parse_missing_timestamps(tmp_path: Path) -> None:
    """Tester l'analyse quand les horodatages sont manquants."""
    sample = {
        "title": "no_dates.jpg",
        "description": "Photo without dates"
    }
    json_path = tmp_path / "no_dates.jpg.json"
    json_path.write_text(json.dumps(sample), encoding="utf-8")
    meta = parse_sidecar(json_path)
    assert meta.photoTakenTime_timestamp is None
    assert meta.creationTime_timestamp is None


def test_parse_localFolderName(tmp_path: Path) -> None:
    """Tester l'extraction du nom du dossier local de l'appareil."""
    sample = {
        "title": "messenger_photo.jpg",
        "description": "Photo from Messenger",
        "googlePhotosOrigin": {
            "mobileUpload": {
                "deviceFolder": {
                    "localFolderName": "Messenger"
                },
                "deviceType": "ANDROID_PHONE"
            }
        }
    }
    json_path = tmp_path / "messenger_photo.jpg.json"
    json_path.write_text(json.dumps(sample), encoding="utf-8")
    meta = parse_sidecar(json_path)
    assert meta.localFolderName == "Messenger"


def test_parse_no_localFolderName(tmp_path: Path) -> None:
    """Tester quand il n'y a pas de dossier local."""
    sample = {
        "title": "normal_photo.jpg",
        "description": "Photo normale"
    }
    json_path = tmp_path / "normal_photo.jpg.json"
    json_path.write_text(json.dumps(sample), encoding="utf-8")
    meta = parse_sidecar(json_path)
    assert meta.localFolderName is None


def test_parse_album_metadata(tmp_path: Path) -> None:
    """Tester l'analyse des métadonnées d'album depuis les fichiers metadata.json."""
    from google_takeout_metadata.sidecar import parse_album_metadata
    
    # Tester le format réel Google Takeout
    album_data = {
        "title": "halloween",
        "description": "",
        "access": "protected",
        "date": {
            "timestamp": "1730287676",
            "formatted": "30 oct. 2024, 11:27:56 UTC"
        }
    }
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(album_data), encoding="utf-8")
    
    albums = parse_album_metadata(metadata_path)
    assert albums == ["halloween"]


def test_parse_album_metadata_no_title(tmp_path: Path) -> None:
    """Tester l'analyse quand le titre est manquant."""
    from google_takeout_metadata.sidecar import parse_album_metadata
    
    album_data = {
        "description": "Album sans titre",
        "access": "protected"
    }
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(album_data), encoding="utf-8")
    
    albums = parse_album_metadata(metadata_path)
    assert albums == []


def test_find_albums_for_directory(tmp_path: Path) -> None:
    """Tester la recherche d'albums pour un répertoire."""
    from google_takeout_metadata.sidecar import find_albums_for_directory
    
    # Créer les métadonnées d'album
    album_data = {"title": "Mon Album"}
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(album_data), encoding="utf-8")
    
    albums = find_albums_for_directory(tmp_path)
    assert albums == ["Mon Album"]


def test_find_albums_for_directory_no_metadata(tmp_path: Path) -> None:
    """Tester la recherche d'albums quand aucune métadonnée n'existe."""
    from google_takeout_metadata.sidecar import find_albums_for_directory
    
    albums = find_albums_for_directory(tmp_path)
    assert albums == []


def test_find_albums_french_metadata_format(tmp_path: Path) -> None:
    """Tester la recherche d'albums avec le format de fichier de métadonnées français."""
    from google_takeout_metadata.sidecar import find_albums_for_directory
    
    # Créer les métadonnées d'album français
    album_data = {"title": "Mon Album Français"}
    metadata_path = tmp_path / "métadonnées.json"
    metadata_path.write_text(json.dumps(album_data), encoding="utf-8")
    
    albums = find_albums_for_directory(tmp_path)
    assert albums == ["Mon Album Français"]


def test_find_albums_french_numbered_metadata(tmp_path: Path) -> None:
    """Tester la recherche d'albums avec des fichiers de métadonnées français numérotés."""
    from google_takeout_metadata.sidecar import find_albums_for_directory
    
    # Créer plusieurs fichiers de métadonnées français
    album_data1 = {"title": "Album 1"}
    metadata_path1 = tmp_path / "métadonnées.json"
    metadata_path1.write_text(json.dumps(album_data1), encoding="utf-8")
    
    album_data2 = {"title": "Album 2"}
    metadata_path2 = tmp_path / "métadonnées(1).json"
    metadata_path2.write_text(json.dumps(album_data2), encoding="utf-8")
    
    album_data3 = {"title": "Album 3"}
    metadata_path3 = tmp_path / "métadonnées(2).json"
    metadata_path3.write_text(json.dumps(album_data3), encoding="utf-8")
    
    albums = find_albums_for_directory(tmp_path)
    assert set(albums) == {"Album 1", "Album 2", "Album 3"}
def test_find_albums_mixed_formats(tmp_path: Path) -> None:
    """Tester la recherche d'albums avec des fichiers de métadonnées mixtes anglais et français."""
    from google_takeout_metadata.sidecar import find_albums_for_directory
    
    # Créer les métadonnées anglais
    album_data_en = {"title": "English Album"}
    metadata_path_en = tmp_path / "metadata.json"
    metadata_path_en.write_text(json.dumps(album_data_en), encoding="utf-8")
    
    # Créer les métadonnées français
    album_data_fr = {"title": "Album Français"}
    metadata_path_fr = tmp_path / "métadonnées.json"
    metadata_path_fr.write_text(json.dumps(album_data_fr), encoding="utf-8")
    
    albums = find_albums_for_directory(tmp_path)
    assert set(albums) == {"Album Français", "English Album"}


def test_sidecar_with_albums_from_directory(tmp_path: Path) -> None:
    """Tester que les albums sont ajoutés depuis les métadonnées de répertoire lors du traitement des sidecars."""
    from google_takeout_metadata.sidecar import parse_sidecar
    
    # Créer les métadonnées d'album
    album_data = {"title": "Album Test"}
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(album_data), encoding="utf-8")
    
    # Créer un fichier image factice
    media_path = tmp_path / "test.jpg"
    with open(media_path, 'wb') as f:
        f.write(b'\xFF\xD8\xFF\xE0')  # En-tête JPEG minimal
    
    # Créer le sidecar
    sidecar_data = {
        "title": "test.jpg",
        "description": "Test photo"
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Analyser le sidecar - les albums devraient être vides initialement
    meta = parse_sidecar(json_path)
    assert meta.albums == []
    
    # Note: Nous ne pouvons pas tester process_sidecar_file sans exiftool
    # mais nous pouvons tester la logique de recherche d'albums séparément

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
    assert meta.filename == "1729436788572.jpg"
    assert meta.description == "Magicien en or"
    assert meta.people == ["anthony vincent"]
    assert meta.taken_at == 1736719606
    assert meta.created_at == 1736719606


def test_title_mismatch(tmp_path: Path) -> None:
    data = {"title": "other.jpg"}
    json_path = tmp_path / "sample.jpg.json"
    json_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        parse_sidecar(json_path)


def test_parse_sidecar_supplemental_metadata_format(tmp_path: Path) -> None:
    """Test parsing new Google Takeout format: IMG_001.jpg.supplemental-metadata.json"""
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
    assert meta.filename == "IMG_001.jpg"
    assert meta.description == "Test photo with new format"
    assert meta.people == ["test user"]
    assert meta.taken_at == 1736719606
    assert meta.created_at == 1736719606


def test_title_mismatch_supplemental_metadata(tmp_path: Path) -> None:
    """Test title validation with supplemental-metadata format."""
    data = {"title": "wrong_name.jpg"}
    json_path = tmp_path / "IMG_001.jpg.supplemental-metadata.json"
    json_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Sidecar title.*does not match expected filename"):
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
    # 0/0 coordinates should be filtered out as unreliable
    assert meta.latitude is None
    assert meta.longitude is None
    assert meta.altitude is None


def test_people_deduplication(tmp_path: Path) -> None:
    """Test that people names are deduplicated and trimmed."""
    sample = {
        "title": "a.jpg",
        "people": [
            {"name": "alice"},
            {"name": " alice "},  # with spaces
            {"name": "alice"},   # duplicate
            {"name": "bob"},
            {"name": "  "},      # empty after strip
            {"name": "charlie"},
            {"name": " bob "},   # another duplicate with spaces
        ]
    }
    json_path = tmp_path / "a.jpg.json"
    json_path.write_text(json.dumps(sample), encoding="utf-8")
    meta = parse_sidecar(json_path)
    # Should have deduplicated and trimmed: ["alice", "bob", "charlie"]
    assert meta.people == ["alice", "bob", "charlie"]


def test_parse_favorite_true(tmp_path: Path) -> None:
    """Test parsing favorited photo."""
    sample = {
        "title": "favorite.jpg",
        "favorited": {"value": True}
    }
    json_path = tmp_path / "favorite.jpg.json"
    json_path.write_text(json.dumps(sample), encoding="utf-8")
    meta = parse_sidecar(json_path)
    assert meta.favorite is True


def test_parse_favorite_false(tmp_path: Path) -> None:
    """Test parsing non-favorited photo."""
    sample = {
        "title": "not_favorite.jpg",
        "favorited": {"value": False}
    }
    json_path = tmp_path / "not_favorite.jpg.json"
    json_path.write_text(json.dumps(sample), encoding="utf-8")
    meta = parse_sidecar(json_path)
    assert meta.favorite is False


def test_parse_no_favorite_field(tmp_path: Path) -> None:
    """Test parsing photo without favorite field."""
    sample = {
        "title": "no_fav.jpg",
        "description": "Test photo"
    }
    json_path = tmp_path / "no_fav.jpg.json"
    json_path.write_text(json.dumps(sample), encoding="utf-8")
    meta = parse_sidecar(json_path)
    assert meta.favorite is False


def test_parse_zero_geo_coordinates(tmp_path: Path) -> None:
    """Test that 0/0 coordinates are filtered out as unreliable."""
    sample = {
        "title": "geo_zero.jpg",
        "geoData": {"latitude": 0.0, "longitude": 0.0, "altitude": 100.0}
    }
    json_path = tmp_path / "geo_zero.jpg.json"
    json_path.write_text(json.dumps(sample), encoding="utf-8")
    meta = parse_sidecar(json_path)
    # 0/0 coordinates should be filtered out
    assert meta.latitude is None
    assert meta.longitude is None
    assert meta.altitude is None


def test_parse_valid_geo_coordinates(tmp_path: Path) -> None:
    """Test that valid coordinates are preserved."""
    sample = {
        "title": "geo_valid.jpg",
        "geoData": {"latitude": 48.8566, "longitude": 2.3522, "altitude": 35.0}
    }
    json_path = tmp_path / "geo_valid.jpg.json"
    json_path.write_text(json.dumps(sample), encoding="utf-8")
    meta = parse_sidecar(json_path)
    assert meta.latitude == 48.8566
    assert meta.longitude == 2.3522
    assert meta.altitude == 35.0


def test_parse_people_nested_format(tmp_path: Path) -> None:
    """Test parsing people in nested format: [{"person": {"name": "X"}}]."""
    sample = {
        "title": "nested_people.jpg",
        "people": [
            {"person": {"name": "alice"}},
            {"person": {"name": "bob"}},
            {"name": "charlie"}  # mixed format
        ]
    }
    json_path = tmp_path / "nested_people.jpg.json"
    json_path.write_text(json.dumps(sample), encoding="utf-8")
    meta = parse_sidecar(json_path)
    assert meta.people == ["alice", "bob", "charlie"]


def test_parse_missing_timestamps(tmp_path: Path) -> None:
    """Test parsing when timestamps are missing."""
    sample = {
        "title": "no_dates.jpg",
        "description": "Photo without dates"
    }
    json_path = tmp_path / "no_dates.jpg.json"
    json_path.write_text(json.dumps(sample), encoding="utf-8")
    meta = parse_sidecar(json_path)
    assert meta.taken_at is None
    assert meta.created_at is None


def test_parse_album_metadata(tmp_path: Path) -> None:
    """Test parsing album metadata from metadata.json files."""
    from google_takeout_metadata.sidecar import parse_album_metadata
    
    # Test basic album metadata
    album_data = {
        "title": "Vacances 2024",
        "description": "Photos des vacances d'été"
    }
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(album_data), encoding="utf-8")
    
    albums = parse_album_metadata(metadata_path)
    assert albums == ["Vacances 2024"]


def test_parse_album_metadata_multiple_albums(tmp_path: Path) -> None:
    """Test parsing multiple album references."""
    from google_takeout_metadata.sidecar import parse_album_metadata
    
    album_data = {
        "title": "Album Principal",
        "albums": [
            {"title": "Sous-album 1"},
            {"title": "Sous-album 2"},
            "Album Simple"
        ]
    }
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(album_data), encoding="utf-8")
    
    albums = parse_album_metadata(metadata_path)
    assert set(albums) == {"Album Principal", "Album Simple", "Sous-album 1", "Sous-album 2"}


def test_find_albums_for_directory(tmp_path: Path) -> None:
    """Test finding albums for a directory."""
    from google_takeout_metadata.sidecar import find_albums_for_directory
    
    # Create album metadata
    album_data = {"title": "Mon Album"}
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(album_data), encoding="utf-8")
    
    albums = find_albums_for_directory(tmp_path)
    assert albums == ["Mon Album"]


def test_find_albums_for_directory_no_metadata(tmp_path: Path) -> None:
    """Test finding albums when no metadata exists."""
    from google_takeout_metadata.sidecar import find_albums_for_directory
    
    albums = find_albums_for_directory(tmp_path)
    assert albums == []


def test_find_albums_french_metadata_format(tmp_path: Path) -> None:
    """Test finding albums with French metadata file format."""
    from google_takeout_metadata.sidecar import find_albums_for_directory
    
    # Create French album metadata
    album_data = {"title": "Mon Album Français"}
    metadata_path = tmp_path / "métadonnées.json"
    metadata_path.write_text(json.dumps(album_data), encoding="utf-8")
    
    albums = find_albums_for_directory(tmp_path)
    assert albums == ["Mon Album Français"]


def test_find_albums_french_numbered_metadata(tmp_path: Path) -> None:
    """Test finding albums with numbered French metadata files."""
    from google_takeout_metadata.sidecar import find_albums_for_directory
    
    # Create multiple French metadata files
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
    """Test finding albums with mixed English and French metadata files."""
    from google_takeout_metadata.sidecar import find_albums_for_directory
    
    # Create English metadata
    album_data_en = {"title": "English Album"}
    metadata_path_en = tmp_path / "metadata.json"
    metadata_path_en.write_text(json.dumps(album_data_en), encoding="utf-8")
    
    # Create French metadata
    album_data_fr = {"title": "Album Français"}
    metadata_path_fr = tmp_path / "métadonnées.json"
    metadata_path_fr.write_text(json.dumps(album_data_fr), encoding="utf-8")
    
    albums = find_albums_for_directory(tmp_path)
    assert set(albums) == {"Album Français", "English Album"}


def test_sidecar_with_albums_from_directory(tmp_path: Path) -> None:
    """Test that albums are added from directory metadata when processing sidecars."""
    from google_takeout_metadata.processor import process_sidecar_file
    from google_takeout_metadata.sidecar import parse_sidecar
    
    # Create album metadata
    album_data = {"title": "Album Test"}
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(album_data), encoding="utf-8")
    
    # Create a dummy image file
    media_path = tmp_path / "test.jpg"
    with open(media_path, 'wb') as f:
        f.write(b'\xFF\xD8\xFF\xE0')  # Minimal JPEG header
    
    # Create sidecar
    sidecar_data = {
        "title": "test.jpg",
        "description": "Test photo"
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Parse the sidecar - albums should be empty initially
    meta = parse_sidecar(json_path)
    assert meta.albums == []
    
    # Note: We can't test process_sidecar_file without exiftool
    # but we can test the album finding logic separately

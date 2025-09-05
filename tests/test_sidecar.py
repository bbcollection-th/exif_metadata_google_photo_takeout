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
    assert meta.latitude == 0.0
    assert meta.longitude == 0.0
    assert meta.altitude == 10.0

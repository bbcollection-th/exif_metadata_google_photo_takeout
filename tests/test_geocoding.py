import json

import requests

from google_takeout_metadata.sidecar import parse_sidecar
from google_takeout_metadata.exif_writer import build_exiftool_args
from google_takeout_metadata.config_loader import ConfigLoader
from google_takeout_metadata import geocoding, processor


def test_parse_geocode_to_exif_args(tmp_path, monkeypatch):
    """Complete flow: parse sidecar → geocoding → build arguments."""

    config_loader = ConfigLoader()
    config_loader.load_config()
    # Create minimal sidecar with coordinates
    data = {
        "title": "a.jpg",
        "geoData": {"latitude": 48.8566, "longitude": 2.3522},
    }
    json_path = tmp_path / "a.jpg.json"
    json_path.write_text(json.dumps(data), encoding="utf-8")

    # Parse sidecar
    meta = parse_sidecar(json_path)

    # Simuler les résultats du géocodage inverse et la clé API
    fake_results = [
        {
            "address_components": [
                {"long_name": "Paris", "types": ["locality"]},
                {"long_name": "France", "types": ["country"]},
            ],
            "formatted_address": "Paris, France",
        }
    ]
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "fake_key")
    monkeypatch.setattr(geocoding, "reverse_geocode", lambda lat, lon: fake_results)

    # Enrichir les métadonnées
    processor._enrich_with_reverse_geocode(meta, json_path, geocode=True)

    # Générer les arguments exiftool
    args = build_exiftool_args(meta, json_path, False, config_loader=config_loader)

    # Vérifier les balises de localisation avec les bons noms de tags
    assert "-XMP-photoshop:City=Paris" in args
    assert "-IPTC:Country-PrimaryLocationName=France" in args
    assert "-XMP-iptcCore:Location=Paris, France" in args


def test_reverse_geocode_uses_cache(monkeypatch, tmp_path):
    """Le cache doit éviter les appels réseau répétés pour les mêmes coordonnées."""

    call_count = 0

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "OK", "results": [1]}

    def fake_get(url, params, timeout):
        nonlocal call_count
        call_count += 1
        return FakeResp()

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "dummy")
    cache_file = tmp_path / "cache.json"
    monkeypatch.setenv("GOOGLE_TAKEOUT_METADATA_CACHE", str(cache_file))

    # Première requête - doit appeler l'API
    geocoding.reverse_geocode(1.0, 2.0)
    assert call_count == 1

    # Deuxième requête identique - doit utiliser le cache
    geocoding.reverse_geocode(1.0, 2.0)
    assert call_count == 1


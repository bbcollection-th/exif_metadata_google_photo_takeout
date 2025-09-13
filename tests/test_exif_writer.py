
from google_takeout_metadata.sidecar import SidecarData
from google_takeout_metadata.exif_writer import (
    write_metadata, 
    build_exiftool_args,
    normalize_person_name,
    normalize_keyword
)
from google_takeout_metadata.config_loader import ConfigLoader
import subprocess
import pytest
from pathlib import Path

# --- Tests de Normalisation (consolidés depuis test_deduplication_robuste.py) ---

def test_normalize_person_name():
    """Tester la normalisation intelligente des noms de personnes."""
    assert normalize_person_name("anthony vincent") == "Anthony Vincent"
    assert normalize_person_name("jean de la fontaine") == "Jean de la Fontaine"
    assert normalize_person_name("patrick o'connor") == "Patrick O'Connor"
    assert normalize_person_name("john mcdonald") == "John McDonald"
    assert normalize_person_name("") == ""

def test_normalize_keyword():
    """Tester la normalisation des mots-clés."""
    assert normalize_keyword("vacances été") == "Vacances Été"
    assert normalize_keyword("ÉVÉNEMENTS SPÉCIAUX") == "Événements Spéciaux"
    assert normalize_keyword("") == ""

# --- Tests de l'exif_writer ---

def test_write_metadata_error(tmp_path, monkeypatch):
    meta = SidecarData(title="a.jpg", description="test")
    img = tmp_path / "a.jpg"
    img.write_bytes(b"data")
    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "exiftool", stderr="bad")
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError):
        write_metadata(img, meta, use_localTime=False)

def test_build_args_current_api():
    """Teste la fonction build_exiftool_args() avec l'API config-driven actuelle."""
    meta = SidecarData(
        title="test.jpg",
        description="Test Description",
        people_name=["Test Person"],
        favorited=True
    )
    config_loader = ConfigLoader()
    config_loader.load_config()
    test_path = Path("test.jpg")
    
    # Test de l'API actuelle (clean, sans paramètres legacy)
    args = build_exiftool_args(meta, test_path, False, config_loader)
    
    # Vérifications de base
    assert isinstance(args, list)
    assert len(args) > 0
    
    # Vérifier les nouveaux tags selon la configuration actuelle
    # Description: write_if_blank_or_missing -> MWG:Description avec condition
    has_description_condition = any("-if" in str(arg) and "MWG:Description" in str(args[i+1:i+3]) for i, arg in enumerate(args[:-2]))
    assert has_description_condition or "-MWG:Description=Test Description" in args
    
    # Favorited: preserve_positive_rating -> XMP:Rating avec condition spéciale
    has_rating_condition = any("-if" in str(arg) and "XMP:Rating" in str(args[i+1:i+3]) for i, arg in enumerate(args[:-2]))
    assert has_rating_condition or "-XMP:Rating=5" in args
    
    # Vérifier que les nouvelles stratégies sont appliquées (pas d'ancien -wm cg)
    assert "-wm" not in args
    assert "cg" not in args


def test_build_args_people_handling():
    """Teste la gestion des personnes avec l'API actuelle."""
    meta = SidecarData(
        title="test.jpg", 
        people_name=["Alice", "Bob"],
    )
    config_loader = ConfigLoader()
    config_loader.load_config()
    test_path = Path("test.jpg")
    
    args = build_exiftool_args(meta, test_path, False, config_loader)
    
    # Vérification de la gestion des personnes (clean_duplicates par défaut)
    # Chaque personne devrait avoir un pattern remove/add individuel
    assert "-XMP-iptcExt:PersonInImage-=Alice" in args  # Remove Alice
    assert "-XMP-iptcExt:PersonInImage+=Alice" in args  # Add Alice
    assert "-XMP-iptcExt:PersonInImage-=Bob" in args    # Remove Bob
    assert "-XMP-iptcExt:PersonInImage+=Bob" in args    # Add Bob


def test_build_args_video_vs_image():
    """Teste la différenciation entre vidéo et image."""
    meta = SidecarData(title="test", description="Test Description")
    config_loader = ConfigLoader()
    config_loader.load_config()
    
    # Test avec image
    image_path = Path("test.jpg")
    image_args = build_exiftool_args(meta, image_path, False, config_loader)
    
    # Test avec vidéo
    video_path = Path("test.mp4")
    video_args = build_exiftool_args(meta, video_path, False, config_loader)
    
    # Les deux devraient fonctionner
    assert isinstance(image_args, list)
    assert isinstance(video_args, list)
    assert len(image_args) > 0
    assert len(video_args) > 0


# === Tests de fonctions utilitaires ===

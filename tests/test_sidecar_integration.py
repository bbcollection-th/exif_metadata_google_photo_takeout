#!/usr/bin/env python3

"""
Test d'intégration pour vérifier que parse_sidecar + write_metadata 
utilisent bien la normalisation et la terminologie à jour.
"""

import json
import tempfile
from pathlib import Path
import sys
sys.path.append('src')

from google_takeout_metadata.sidecar import parse_sidecar
from google_takeout_metadata.exif_writer import build_exiftool_args, normalize_person_name, normalize_keyword


def test_sidecar_to_exiftool_integration():
    """Test d'intégration : vérifier que les noms de personnes du sidecar sont normalisés dans build_exiftool_args."""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Créer un sidecar avec des noms non normalisés
        sidecar_data = {
            "title": "test.jpg",
            "description": "Photo de test", 
            "people": [
                {"name": "anthony vincent"},  # minuscules
                {"name": "ALICE DUPONT"},     # majuscules
                {"name": "jean de la fontaine"},  # particules
                {"name": "patrick o'connor"},     # O'
                {"name": "john mcdonald"},         # Mc
            ]
        }
        
        json_path = temp_path / "test.jpg.json"
        json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
        
        # Parser le sidecar
        meta = parse_sidecar(json_path)
        print(f"Noms depuis parse_sidecar: {meta.people_name}")
        
        # Les noms depuis parse_sidecar ne sont PAS encore normalisés (comportement attendu)
        assert meta.people_name == ["ALICE DUPONT", "anthony vincent", "jean de la fontaine", "john mcdonald", "patrick o'connor"]
        
        # Construire les arguments exiftool (qui DOIT normaliser)
        args = build_exiftool_args(meta, append_only=True)
        print(f"Arguments exiftool: {args}")
        
        # Vérifier que les arguments contiennent les noms normalisés
        args_str = " ".join(args)
        
        # Vérifier la normalisation dans les arguments
        assert "Anthony Vincent" in args_str, "anthony vincent devrait être normalisé en Anthony Vincent"
        assert "Alice Dupont" in args_str, "ALICE DUPONT devrait être normalisé en Alice Dupont"
        assert "Jean de la Fontaine" in args_str, "jean de la fontaine devrait préserver 'de la'"
        assert "Patrick O'Connor" in args_str, "patrick o'connor devrait être normalisé en Patrick O'Connor"
        assert "John McDonald" in args_str, "john mcdonald devrait être normalisé en John McDonald"
        
        # Vérifier que nous utilisons bien l'approche robuste (remove-then-add)
        # Chaque personne devrait avoir une paire -PersonInImage-=X et -PersonInImage+=X
        for person in ["Anthony Vincent", "Alice Dupont", "Jean de la Fontaine", "Patrick O'Connor", "John McDonald"]:
            assert f"-XMP-iptcExt:PersonInImage-={person}" in args, f"Devrait avoir -PersonInImage-={person}"
            assert f"-XMP-iptcExt:PersonInImage+={person}" in args, f"Devrait avoir -PersonInImage+={person}"


def test_sidecar_album_normalization():
    """Test que les albums des sidecars sont normalisés avec normalize_keyword."""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Créer un sidecar
        sidecar_data = {
            "title": "test.jpg",
            "description": "Photo avec albums"
        }
        
        json_path = temp_path / "test.jpg.json"
        json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
        
        # Parser le sidecar
        meta = parse_sidecar(json_path)
        
        # Simuler des albums trouvés par find_albums_for_directory 
        # (ces albums ne sont pas normalisés à ce stade)
        meta.albums = ["vacances été", "photos de famille", "ÉVÉNEMENTS SPÉCIAUX"]
        
        # Construire les arguments exiftool
        args = build_exiftool_args(meta, append_only=True)
        args_str = " ".join(args)
        print(f"Arguments avec albums: {args_str}")
        
        # Vérifier que les albums sont normalisés avec le préfixe "Album: "
        assert "Album: Vacances Été" in args_str, "Album devrait être normalisé"
        assert "Album: Photos De Famille" in args_str, "Album devrait être normalisé"
        assert "Album: Événements Spéciaux" in args_str, "Album devrait être normalisé"


def test_manual_normalization_vs_integrated():
    """Test que la normalisation manuelle donne le même résultat que l'intégration."""
    
    # Test avec des noms divers
    test_names = [
        "anthony vincent",
        "ALICE DUPONT", 
        "jean de la fontaine",
        "patrick o'connor",
        "john mcdonald"
    ]
    
    # Normalisation manuelle
    manually_normalized = [normalize_person_name(name) for name in test_names]
    expected = ["Anthony Vincent", "Alice Dupont", "Jean de la Fontaine", "Patrick O'Connor", "John McDonald"]
    
    assert manually_normalized == expected, f"Normalisation manuelle incorrecte: {manually_normalized}"
    
    # Test albums  
    test_albums = ["vacances été", "photos de famille", "ÉVÉNEMENTS SPÉCIAUX"]
    album_normalized = [normalize_keyword(album) for album in test_albums]
    expected_albums = ["Vacances Été", "Photos De Famille", "Événements Spéciaux"]
    
    assert album_normalized == expected_albums, f"Normalisation albums incorrecte: {album_normalized}"
    
    print("✅ Normalisation manuelle cohérente avec l'intégration")


if __name__ == "__main__":
    test_sidecar_to_exiftool_integration()
    print()
    test_sidecar_album_normalization()
    print()
    test_manual_normalization_vs_integrated()
    print()
    print("🎉 Tests d'intégration sidecar + normalisation : SUCCÈS !")

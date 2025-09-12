#!/usr/bin/env python3
"""Test rapide de l'extraction du localFolderName."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "src")

from google_takeout_metadata.sidecar import parse_sidecar
from google_takeout_metadata.exif_writer import build_exiftool_args

def test_localFolderName_integration():
    """Test complet d'extraction et génération d'arguments pour localFolderName."""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # 1. Créer un sidecar avec localFolderName
        sidecar_data = {
            "title": "test_photo.jpg",
            "description": "Photo test",
            "people": [{"name": "Alice"}],
            "googlePhotosOrigin": {
                "mobileUpload": {
                    "deviceFolder": {
                        "localFolderName": "Instagram"
                    },
                    "deviceType": "ANDROID_PHONE"
                }
            }
        }
        
        json_path = temp_path / "test_photo.jpg.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(sidecar_data, f)
        
        # 2. Parser le sidecar
        meta = parse_sidecar(json_path)
        
        print("🔍 Parsing résultats:")
        print(f"   localFolderName: {meta.localFolderName}")
        print(f"   albums: {meta.albums}")
        print(f"   people_name: {meta.people_name}")
        
        # 3. Générer les arguments ExifTool
        media_path = temp_path / "test_photo.jpg"
        args = build_exiftool_args(meta, media_path=media_path, use_localtime=False, append_only=True)
        
        print("🔧 Arguments ExifTool générés:")
        for arg in args:
            if "Album:" in str(arg) or "Alice" in str(arg):
                print(f"   {arg}")
        
        # 4. Vérifications
        assert meta.localFolderName == "Instagram", f"Attendu 'Instagram', obtenu {meta.localFolderName}"
        
        # Chercher l'argument pour Alice (personnes)
        alice_found = False
        instagram_as_album_found = False
        
        for arg in args:
            if isinstance(arg, str):
                if "Alice" in arg:
                    alice_found = True
                # localFolderName ne devrait PAS être traité comme un album
                if "Album: Instagram" in arg:
                    instagram_as_album_found = True
        
        # Alice devrait être présente (personne)
        assert alice_found, "L'argument 'Alice' devrait être présent"
        
        # Instagram ne devrait PAS être traité comme un album
        assert not instagram_as_album_found, "localFolderName ne devrait PAS être traité comme un album avec préfixe 'Album:'"
        
        # Pour le moment, acceptons que localFolderName ne soit pas utilisé dans les métadonnées
        # (selon la logique métier expliquée par l'utilisateur)
        print(f"✅ localFolderName extrait correctement: {meta.localFolderName}")
        print("✅ localFolderName correctement non traité comme album")


if __name__ == "__main__":
    print("🧪 Test d'intégration localFolderName")
    print("=" * 50)
    
    try:
        test_localFolderName_integration()
        print("🎉 Tous les tests réussis!")
    except Exception as e:
        print(f"💥 Erreur: {e}")
        import traceback
        traceback.print_exc()

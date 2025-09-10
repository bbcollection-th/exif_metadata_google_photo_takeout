#!/usr/bin/env python3
"""Test de l'organisation de fichiers en mode batch."""

import tempfile
import json
from pathlib import Path
from PIL import Image

# Import des modules
import sys
sys.path.insert(0, "src")

from google_takeout_metadata.processor_batch import process_directory_batch


def test_batch_organization():
    """Test d'organisation de fichiers en mode batch."""
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = Path(temp_dir)
        
        # 1. Créer un vrai fichier image minimal avec PIL
        media_file = test_dir / "test_image.jpg"
        img = Image.new('RGB', (100, 100), color='red')
        img.save(media_file)
        
        # 2. Créer un sidecar avec statut trashed
        sidecar_file = test_dir / "test_image.jpg.json" 
        sidecar_data = {
            "title": "test_image.jpg",
            "description": "Une photo test",
            "photoTakenTime": {"timestamp": "1640995200"},
            "trashed": True,
            "archived": False,
            "locked": False
        }
        
        with open(sidecar_file, 'w', encoding='utf-8') as f:
            json.dump(sidecar_data, f, indent=2)
        
        print("📁 Structure initiale :")
        print(f"   {media_file.name}")
        print(f"   {sidecar_file.name}")
        
        # 3. Lancer le traitement batch avec organisation
        print("\n🚀 Lancement du traitement batch avec organisation...")
        process_directory_batch(
            root=test_dir,
            use_localtime=False,
            append_only=True,
            immediate_delete=False,
            organize_files=True
        )
        
        # 4. Vérifier que les fichiers ont été déplacés
        corbeille_dir = test_dir / "_Corbeille"
        moved_media = corbeille_dir / "test_image.jpg"
        moved_sidecar = corbeille_dir / "OK_test_image.jpg.json"
        
        
        print("\n📋 Vérifications :")
        print(f"   Dossier corbeille créé : {corbeille_dir.exists()}")
        print(f"   Fichier média déplacé : {moved_media.exists()}")
        print(f"   Sidecar déplacé et marqué : {moved_sidecar.exists()}")
        
        # Utiliser des assertions au lieu de return pour pytest
        assert corbeille_dir.exists(), "Le dossier corbeille devrait être créé"
        assert moved_media.exists(), "Le fichier média devrait être déplacé dans la corbeille"
        
        print("✅ Test batch avec organisation réussi !")


if __name__ == "__main__":
    print("🧪 Test d'organisation en mode batch")
    print("=" * 50)
    
    success = test_batch_organization()
    print("\n" + "=" * 50)
    if success:
        print("🎉 Test d'intégration batch réussi !")
    else:
        print("💥 Test d'intégration batch échoué")

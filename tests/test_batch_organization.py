"""Test de l'organisation de fichiers en mode batch."""

import tempfile
import json
from pathlib import Path
from PIL import Image

from google_takeout_metadata.processor_batch import process_directory_batch


def test_batch_organization():
    """Test d'organisation de fichiers en mode batch."""
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = Path(temp_dir)
        
        # 1. Créer un fichier média (vraie image JPEG)
        media_file = test_dir / "test_image.jpg"
        # Créer une vraie image JPEG avec PIL
        img = Image.new('RGB', (100, 100), color='blue')
        img.save(media_file, 'JPEG')
        img.close()
        
        # 2. Créer un sidecar avec statut trashed
        sidecar_file = test_dir / "test_image.jpg.json" 
        sidecar_data = {
            "title": "test_image.jpg",
            "description": "Une photo test",
            "photoTakenTime": {"timestamp": "1640995200"},
            "trashed": True,
            "archived": False,
            "inLockedFolder": False
        }
        
        with open(sidecar_file, 'w', encoding='utf-8') as f:
            json.dump(sidecar_data, f, indent=2)
        
        # 3. Lancer le traitement batch avec organisation
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
        
        # Utiliser des assertions au lieu de return
        assert corbeille_dir.exists(), "Le dossier corbeille devrait être créé"
        assert moved_media.exists(), "Le fichier média devrait être déplacé dans la corbeille"
        assert moved_sidecar.exists(), "Le sidecar devrait être déplacé et marqué OK"
        assert not (corbeille_dir / "test_image.jpg.json").exists(), "Le sidecar original ne devrait plus exister"

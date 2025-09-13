#!/usr/bin/env python3
"""Test rapide pour vérifier que les statistiques sont bien connectées."""

import tempfile
from pathlib import Path
import json
from PIL import Image

from google_takeout_metadata.processor import process_directory
from google_takeout_metadata import statistics


def test_stats_connected():
    """Test rapide pour vérifier les connexions des statistiques."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Réinitialiser les statistiques
        statistics.stats = statistics.ProcessingStats()
        
        # Créer une image de test
        img_path = tmp_path / "test.jpg"
        img = Image.new('RGB', (100, 100), color='red')
        img.save(img_path)
        
        # Créer un sidecar JSON
        sidecar_data = {"title": "test.jpg", "description": "Test image"}
        json_path = tmp_path / "test.jpg.json"
        json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
        
        # Créer un sidecar déjà traité (préfixe OK_)
        processed_sidecar = tmp_path / "OK_test2.jpg.json"
        processed_sidecar.write_text(json.dumps({"title": "test2.jpg"}), encoding="utf-8")
        
        # Traiter le répertoire
        process_directory(tmp_path, use_localTime=False, immediate_delete=False, organize_files=True,
            geocode=False)
        
        # Vérifier les statistiques
        print(f"Total sidecars trouvés: {statistics.stats.total_sidecars_found}")
        print(f"Total traités: {statistics.stats.total_processed}")
        print(f"Total ignorés: {statistics.stats.total_skipped}")
        print(f"Fichiers ignorés: {statistics.stats.skipped_files}")
        
        # Le sidecar déjà traité devrait être dans les ignorés
        assert statistics.stats.total_skipped == 1
        assert len(statistics.stats.skipped_files) == 1
        assert "OK_test2.jpg.json" in statistics.stats.skipped_files[0]
        
        print("✅ Toutes les statistiques sont bien connectées !")


if __name__ == "__main__":
    test_stats_connected()

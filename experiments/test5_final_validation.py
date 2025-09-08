#!/usr/bin/env python3
"""
Test 5: Validation de l'implémentation finale dans le code principal
"""

import sys
import shutil
from pathlib import Path

# Ajouter le chemin src pour importer nos modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from google_takeout_metadata.sidecar import SidecarData
from google_takeout_metadata.exif_writer import write_metadata
import subprocess

def test_final_implementation():
    print("=== Test 5: Validation implémentation finale ===")
    
    # Préparer fichier de test
    test_file = Path("experiments/test5.jpg")
    shutil.copy("test_assets/test_clean.jpg", test_file)
    
    # Étape 1: Simuler état initial (ancien takeout)
    print("\n1. État initial (ancien takeout):")
    meta1 = SidecarData(
        filename="test5.jpg",
        description="Test description",
        people=["Anthony", "Bernard"],
        albums=["Vacances"],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None
    )
    
    write_metadata(test_file, meta1, append_only=True)
    
    # Lire l'état initial
    def read_tags():
        cmd = ["exiftool", "-a", "-s", "-s", "-s", 
               "-XMP-iptcExt:PersonInImage", "-XMP-dc:Subject", "-IPTC:Keywords", 
               str(test_file)]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        lines = result.stdout.strip().split('\n')
        return {
            'persons': lines[0] if len(lines) > 0 and lines[0] else '',
            'subject': lines[1] if len(lines) > 1 and lines[1] else '',
            'keywords': lines[2] if len(lines) > 2 and lines[2] else ''
        }
    
    initial_state = read_tags()
    print(f"PersonInImage: '{initial_state['persons']}'")
    print(f"Subject: '{initial_state['subject']}'")
    print(f"Keywords: '{initial_state['keywords']}'")
    
    # Étape 2: Simuler nouveau takeout avec personne supplémentaire
    print("\n2. Nouveau takeout avec Anthony, Bernard, Cindy:")
    meta2 = SidecarData(
        filename="test5.jpg",
        description="Test description",
        people=["Anthony", "Bernard", "Cindy"],  # JSON complet avec nouvelle personne
        albums=["Vacances", "Famille"],  # Nouvel album aussi
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None
    )
    
    write_metadata(test_file, meta2, append_only=True)
    
    final_state = read_tags()
    print(f"PersonInImage: '{final_state['persons']}'")
    print(f"Subject: '{final_state['subject']}'")
    print(f"Keywords: '{final_state['keywords']}'")
    
    # Vérifications
    print("\n3. Vérifications:")
    
    # Vérifier que Cindy a été ajoutée
    cindy_added = "Cindy" in final_state['persons']
    print(f"✓ Cindy ajoutée: {cindy_added}")
    
    # Vérifier qu'il n'y a pas de doublons d'Anthony
    anthony_count = final_state['persons'].count("Anthony")
    no_anthony_duplicates = anthony_count == 1
    print(f"✓ Pas de doublons Anthony: {no_anthony_duplicates} (count: {anthony_count})")
    
    # Vérifier qu'il n'y a pas de doublons de Bernard
    bernard_count = final_state['persons'].count("Bernard")
    no_bernard_duplicates = bernard_count == 1
    print(f"✓ Pas de doublons Bernard: {no_bernard_duplicates} (count: {bernard_count})")
    
    # Vérifier que les albums sont gérés correctement
    famille_added = "Album: Famille" in final_state['subject']
    print(f"✓ Album Famille ajouté: {famille_added}")
    
    # Résultat global
    success = cindy_added and no_anthony_duplicates and no_bernard_duplicates and famille_added
    print(f"\n🎯 Test global: {'✅ SUCCÈS' if success else '❌ ÉCHEC'}")
    
    # Nettoyer
    test_file.unlink()
    
    return success

if __name__ == "__main__":
    test_final_implementation()

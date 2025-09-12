#!/usr/bin/env python3
"""
Test 7: Solution finale hybride - Notre logique Python + fonction NoDups en filet de sécurité
"""

import sys
import shutil
from pathlib import Path

# Ajouter le chemin src pour importer nos modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from google_takeout_metadata.sidecar import SidecarData
from google_takeout_metadata.exif_writer import write_metadata
import subprocess

def test_hybrid_solution():
    print("=== Test 7: Solution hybride finale ===")
    
    # Préparer fichier de test
    test_file = Path("experiments/test7.jpg")
    shutil.copy("test_assets/test_clean.jpg", test_file)
    
    # Étape 1: État initial (ancien takeout)
    print("\n1. État initial (ancien takeout):")
    meta1 = SidecarData(
        title="test7.jpg",
        description="Test description",
        people_name=["Anthony", "Bernard"],
        albums=["Vacances"],
        photoTakenTime_timestamp=None,
        creationTime_timestamp=None,
        geoData_latitude=None,
        geoData_longitude=None,
        geoData_altitude=None
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
    
    # Étape 2: Nouveau takeout avec nouvelle personne (notre logique)
    print("\n2. Nouveau takeout avec Anthony, Bernard, Cindy (notre logique):")
    meta2 = SidecarData(
        title="test7.jpg",
        description="Test description",
        people_name=["Anthony", "Bernard", "Cindy"],  # JSON complet
        albums=["Vacances", "Famille"],  # Nouvel album
        photoTakenTime_timestamp=None,
        creationTime_timestamp=None,
        geoData_latitude=None,
        geoData_longitude=None,
        geoData_altitude=None
    )
    
    write_metadata(test_file, meta2, append_only=True)
    
    after_our_logic = read_tags()
    print(f"PersonInImage: '{after_our_logic['persons']}'")
    print(f"Subject: '{after_our_logic['subject']}'")
    print(f"Keywords: '{after_our_logic['keywords']}'")
    
    # Étape 3: Nettoyage de sécurité avec fonction NoDups
    print("\n3. Nettoyage de sécurité avec fonction NoDups:")
    cmd_cleanup = [
        "exiftool", "-overwrite_original",
        "-sep", "##",
        "-XMP-iptcExt:PersonInImage<${XMP-iptcExt:PersonInImage;NoDups}",
        "-XMP-dc:Subject<${XMP-dc:Subject;NoDups}",
        "-IPTC:Keywords<${IPTC:Keywords;NoDups}",
        str(test_file)
    ]
    subprocess.run(cmd_cleanup, capture_output=True)
    
    final_state = read_tags()
    print(f"PersonInImage: '{final_state['persons']}'")
    print(f"Subject: '{final_state['subject']}'")
    print(f"Keywords: '{final_state['keywords']}'")
    
    # Vérifications finales
    print("\n4. Vérifications finales:")
    
    # Compter les occurrences
    anthony_count = final_state['persons'].count("Anthony")
    bernard_count = final_state['persons'].count("Bernard")
    cindy_present = "Cindy" in final_state['persons']
    famille_present = "Album: Famille" in final_state['subject']
    vacances_present = "Album: Vacances" in final_state['subject']
    
    print(f"✓ Anthony apparaît {anthony_count} fois (attendu: 1)")
    print(f"✓ Bernard apparaît {bernard_count} fois (attendu: 1)")
    print(f"✓ Cindy présent: {cindy_present}")
    print(f"✓ Album Famille présent: {famille_present}")
    print(f"✓ Album Vacances préservé: {vacances_present}")
    
    # Vérifier qu'on a bien toutes les personnes uniques
    persons_list = final_state['persons'].split(', ') if final_state['persons'] else []
    expected_persons = {"Anthony", "Bernard", "Cindy"}
    actual_persons = set(persons_list)
    persons_match = actual_persons == expected_persons
    
    print(f"✓ Personnes exactes: {persons_match} (attendu: {expected_persons}, réel: {actual_persons})")
    
    success = (anthony_count == 1 and bernard_count == 1 and 
               cindy_present and famille_present and vacances_present and persons_match)
    
    print(f"\n🎯 Test solution hybride: {'✅ SUCCÈS COMPLET' if success else '❌ ÉCHEC'}")
    
    # Nettoyer
    test_file.unlink()
    
    return success

if __name__ == "__main__":
    test_hybrid_solution()

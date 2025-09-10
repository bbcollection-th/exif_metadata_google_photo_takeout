#!/usr/bin/env python3
"""
Test 1: Vérifier comment exiftool lit les tags de liste avec -a
"""

import subprocess
import shutil
from pathlib import Path

def test_reading_with_a_option():
    print("=== Test 1: Lecture avec option -a ===")
    
    # Préparer fichier de test
    test_file = Path("experiments/test1.jpg")
    shutil.copy("test_assets/test_clean.jpg", test_file)
    
    # Ajouter des métadonnées manuellement
    print("\n1. Ajout de métadonnées initiales...")
    cmd1 = [
        "exiftool", "-overwrite_original",
        "-XMP-iptcExt:PersonInImage=Anthony",
        "-XMP-iptcExt:PersonInImage+=Bernard", 
        "-XMP-dc:Subject=Anthony",
        "-XMP-dc:Subject+=Bernard",
        "-XMP-dc:Subject+=Album: Vacances",
        str(test_file)
    ]
    subprocess.run(cmd1, capture_output=True)
    
    # Lire sans -a
    print("\n2. Lecture SANS -a:")
    cmd2 = ["exiftool", "-s", "-s", "-s", "-XMP-iptcExt:PersonInImage", "-XMP-dc:Subject", str(test_file)]
    result2 = subprocess.run(cmd2, capture_output=True, text=True, encoding='utf-8')
    print(f"Sortie: '{result2.stdout.strip()}'")
    
    # Lire avec -a
    print("\n3. Lecture AVEC -a:")
    cmd3 = ["exiftool", "-a", "-s", "-s", "-s", "-XMP-iptcExt:PersonInImage", "-XMP-dc:Subject", str(test_file)]
    result3 = subprocess.run(cmd3, capture_output=True, text=True, encoding='utf-8')
    print(f"Sortie: '{result3.stdout.strip()}'")
    
    # Ajouter des doublons
    print("\n4. Ajout de doublons...")
    cmd4 = [
        "exiftool", "-overwrite_original",
        "-XMP-iptcExt:PersonInImage+=Anthony",  # Doublon
        "-XMP-iptcExt:PersonInImage+=Cindy",    # Nouveau
        "-XMP-dc:Subject+=Anthony",             # Doublon
        "-XMP-dc:Subject+=Cindy",               # Nouveau
        str(test_file)
    ]
    subprocess.run(cmd4, capture_output=True)
    
    # Lire le résultat final avec -a
    print("\n5. Lecture finale AVEC -a:")
    result5 = subprocess.run(cmd3, capture_output=True, text=True, encoding='utf-8')
    print(f"Sortie: '{result5.stdout.strip()}'")
    
    # Nettoyer
    test_file.unlink()

if __name__ == "__main__":
    test_reading_with_a_option()

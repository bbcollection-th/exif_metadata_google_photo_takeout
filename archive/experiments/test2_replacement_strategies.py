#!/usr/bin/env python3
"""
Test 2: Tester différentes stratégies pour écraser complètement un tag de liste
"""

import subprocess
import shutil
from pathlib import Path

def test_tag_replacement_strategies():
    print("=== Test 2: Stratégies de remplacement de tags ===")
    
    # Préparer fichier de test
    test_file = Path("experiments/test2.jpg")
    shutil.copy("test_assets/test_clean.jpg", test_file)
    
    # Étape 1: Ajouter métadonnées initiales avec doublons
    print("\n1. Ajout métadonnées initiales avec doublons...")
    cmd1 = [
        "exiftool", "-overwrite_original",
        "-XMP-iptcExt:PersonInImage=Anthony",
        "-XMP-iptcExt:PersonInImage+=Bernard", 
        "-XMP-iptcExt:PersonInImage+=Anthony",  # Doublon volontaire
        str(test_file)
    ]
    subprocess.run(cmd1, capture_output=True)
    
    # Lecture état initial
    print("\n2. État initial:")
    cmd_read = ["exiftool", "-a", "-s", "-s", "-s", "-XMP-iptcExt:PersonInImage", str(test_file)]
    result = subprocess.run(cmd_read, capture_output=True, text=True, encoding='utf-8')
    print(f"PersonInImage: '{result.stdout.strip()}'")
    
    # Stratégie 1: Vider puis ajouter un par un
    print("\n3. Stratégie 1: Vider puis ajouter un par un")
    cmd2 = [
        "exiftool", "-overwrite_original",
        "-XMP-iptcExt:PersonInImage=",  # Vider
        "-XMP-iptcExt:PersonInImage=Anthony",  # Premier
        "-XMP-iptcExt:PersonInImage+=Bernard",  # Deuxième
        "-XMP-iptcExt:PersonInImage+=Cindy",   # Troisième
        str(test_file)
    ]
    subprocess.run(cmd2, capture_output=True)
    
    result = subprocess.run(cmd_read, capture_output=True, text=True, encoding='utf-8')
    print(f"Résultat stratégie 1: '{result.stdout.strip()}'")
    
    # Réinitialiser
    shutil.copy("test_assets/test_clean.jpg", test_file)
    subprocess.run(cmd1, capture_output=True)
    
    # Stratégie 2: Assignation directe avec liste concaténée
    print("\n4. Stratégie 2: Assignation directe avec liste")
    cmd3 = [
        "exiftool", "-overwrite_original",
        "-XMP-iptcExt:PersonInImage=Anthony,Bernard,Cindy",
        str(test_file)
    ]
    subprocess.run(cmd3, capture_output=True)
    
    result = subprocess.run(cmd_read, capture_output=True, text=True, encoding='utf-8')
    print(f"Résultat stratégie 2: '{result.stdout.strip()}'")
    
    # Réinitialiser
    shutil.copy("test_assets/test_clean.jpg", test_file)
    subprocess.run(cmd1, capture_output=True)
    
    # Stratégie 3: Assignations multiples directes
    print("\n5. Stratégie 3: Assignations multiples directes")
    cmd4 = [
        "exiftool", "-overwrite_original",
        "-XMP-iptcExt:PersonInImage=Anthony",
        "-XMP-iptcExt:PersonInImage=Bernard", 
        "-XMP-iptcExt:PersonInImage=Cindy",
        str(test_file)
    ]
    subprocess.run(cmd4, capture_output=True)
    
    result = subprocess.run(cmd_read, capture_output=True, text=True, encoding='utf-8')
    print(f"Résultat stratégie 3: '{result.stdout.strip()}'")
    
    # Nettoyer
    test_file.unlink()

if __name__ == "__main__":
    test_tag_replacement_strategies()

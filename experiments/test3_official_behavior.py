#!/usr/bin/env python3
"""
Test 3: Appliquer les bonnes pratiques officielles d'exiftool pour les tags de liste
Basé sur la documentation officielle "List-type tags do not behave as expected"
"""

import subprocess
import shutil
from pathlib import Path

def test_official_list_behavior():
    print("=== Test 3: Comportement officiel des tags de liste ===")
    
    # Préparer fichier de test
    test_file = Path("experiments/test3.jpg")
    shutil.copy("test_assets/test_clean.jpg", test_file)
    
    # Test 1: Méthode officielle pour écrire plusieurs mots-clés
    print("\n1. Méthode officielle: assignations multiples avec =")
    cmd1 = [
        "exiftool", "-overwrite_original",
        "-keywords=Anthony",
        "-keywords=Bernard", 
        "-keywords=Album: Vacances",
        str(test_file)
    ]
    subprocess.run(cmd1, capture_output=True)
    
    cmd_read = ["exiftool", "-a", "-s", "-s", "-s", "-IPTC:Keywords", str(test_file)]
    result = subprocess.run(cmd_read, capture_output=True, text=True, encoding='utf-8')
    print(f"Résultat assignations multiples: '{result.stdout.strip()}'")
    
    # Test 2: Ajouter des éléments avec +=
    print("\n2. Ajout avec += (sans dupliquer)")
    cmd2 = [
        "exiftool", "-overwrite_original",
        "-keywords-=Anthony",    # Supprimer d'abord
        "-keywords+=Anthony",    # Puis re-ajouter 
        "-keywords-=Cindy",      # Supprimer (même si n'existe pas)
        "-keywords+=Cindy",      # Puis ajouter
        str(test_file)
    ]
    subprocess.run(cmd2, capture_output=True)
    
    result = subprocess.run(cmd_read, capture_output=True, text=True, encoding='utf-8')
    print(f"Après ajout dédupliqué: '{result.stdout.strip()}'")
    
    # Test 3: Utiliser l'option -sep pour splitter une chaîne
    print("\n3. Utilisation de -sep pour splitter")
    test_file2 = Path("experiments/test3b.jpg")
    shutil.copy("test_assets/test_clean.jpg", test_file2)
    
    cmd3 = [
        "exiftool", "-overwrite_original",
        "-sep", ", ",
        "-keywords=Anthony, Bernard, Album: Vacances",
        str(test_file2)
    ]
    subprocess.run(cmd3, capture_output=True)
    
    cmd_read2 = ["exiftool", "-a", "-s", "-s", "-s", "-IPTC:Keywords", str(test_file2)]
    result = subprocess.run(cmd_read2, capture_output=True, text=True, encoding='utf-8')
    print(f"Avec -sep: '{result.stdout.strip()}'")
    
    # Test 4: API NoDups pour éviter les doublons
    print("\n4. Test API NoDups")
    test_file3 = Path("experiments/test3c.jpg")
    shutil.copy("test_assets/test_clean.jpg", test_file3)
    
    # D'abord ajouter des métadonnées avec doublons
    cmd4a = [
        "exiftool", "-overwrite_original",
        "-keywords=Anthony",
        "-keywords=Bernard",
        "-keywords=Anthony",  # Doublon
        str(test_file3)
    ]
    subprocess.run(cmd4a, capture_output=True)
    
    # Puis utiliser NoDups pour nettoyer
    cmd4b = [
        "exiftool", "-overwrite_original",
        "-api", "NoDups=1",
        "-keywords+=Cindy",  # Ajouter nouvelle valeur
        str(test_file3)
    ]
    subprocess.run(cmd4b, capture_output=True)
    
    cmd_read3 = ["exiftool", "-a", "-s", "-s", "-s", "-IPTC:Keywords", str(test_file3)]
    result = subprocess.run(cmd_read3, capture_output=True, text=True, encoding='utf-8')
    print(f"Avec API NoDups: '{result.stdout.strip()}'")
    
    # Nettoyer
    test_file.unlink()
    test_file2.unlink()
    test_file3.unlink()

if __name__ == "__main__":
    test_official_list_behavior()

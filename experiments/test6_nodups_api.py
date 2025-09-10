#!/usr/bin/env python3
"""
Test 6: Utilisation de l'API NoDups d'ExifTool pour gérer les doublons
"""

import subprocess
import shutil
from pathlib import Path

def test_nodups_api():
    print("=== Test 6: API NoDups d'ExifTool ===")
    
    # Préparer fichier de test
    test_file = Path("experiments/test6.jpg")
    shutil.copy("test_assets/test_clean.jpg", test_file)
    
    # Créer un état initial avec doublons volontaires
    print("\n1. Créer état initial avec doublons:")
    cmd1 = [
        "exiftool", "-overwrite_original",
        "-XMP-iptcExt:PersonInImage=Anthony",
        "-XMP-iptcExt:PersonInImage=Bernard",
        "-XMP-iptcExt:PersonInImage=Anthony",  # Doublon volontaire
        "-XMP-dc:Subject=Anthony", 
        "-XMP-dc:Subject=Bernard",
        "-XMP-dc:Subject=Album: Vacances",
        "-XMP-dc:Subject=Anthony",  # Doublon volontaire
        str(test_file)
    ]
    subprocess.run(cmd1, capture_output=True)
    
    # Lire l'état avec doublons
    def read_tags():
        cmd = ["exiftool", "-a", "-s", "-s", "-s", 
               "-XMP-iptcExt:PersonInImage", "-XMP-dc:Subject", 
               str(test_file)]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        lines = result.stdout.strip().split('\n')
        return {
            'persons': lines[0] if len(lines) > 0 and lines[0] else '',
            'subject': lines[1] if len(lines) > 1 and lines[1] else ''
        }
    
    initial_state = read_tags()
    print(f"PersonInImage avec doublons: '{initial_state['persons']}'")
    print(f"Subject avec doublons: '{initial_state['subject']}'")
    
    # Test 1: Utiliser l'API NoDups pour nettoyer
    print("\n2. Test API NoDups pour nettoyer les doublons:")
    cmd2 = [
        "exiftool", "-overwrite_original",
        "-api", "NoDups=1",
        "-tagsfromfile", "@",
        "-XMP-iptcExt:PersonInImage",
        "-XMP-dc:Subject",
        str(test_file)
    ]
    subprocess.run(cmd2, capture_output=True)
    
    cleaned_state = read_tags()
    print(f"PersonInImage après NoDups: '{cleaned_state['persons']}'")
    print(f"Subject après NoDups: '{cleaned_state['subject']}'")
    
    # Test 2: Ajouter nouvelles valeurs avec API NoDups
    print("\n3. Ajouter nouvelles valeurs avec NoDups:")
    cmd3 = [
        "exiftool", "-overwrite_original",
        "-api", "NoDups=1",
        "-XMP-iptcExt:PersonInImage+=Anthony",  # Doublon à ignorer
        "-XMP-iptcExt:PersonInImage+=Cindy",    # Nouveau à ajouter
        "-XMP-dc:Subject+=Anthony",             # Doublon à ignorer
        "-XMP-dc:Subject+=Cindy",               # Nouveau à ajouter
        "-XMP-dc:Subject+=Album: Famille",      # Nouveau à ajouter
        str(test_file)
    ]
    subprocess.run(cmd3, capture_output=True)
    
    final_state = read_tags()
    print(f"PersonInImage final: '{final_state['persons']}'")
    print(f"Subject final: '{final_state['subject']}'")
    
    # Vérifications
    print("\n4. Vérifications:")
    
    # Compter les occurrences
    anthony_count = final_state['persons'].count("Anthony")
    bernard_count = final_state['persons'].count("Bernard")
    cindy_present = "Cindy" in final_state['persons']
    famille_present = "Album: Famille" in final_state['subject']
    
    print(f"Anthony apparaît {anthony_count} fois (attendu: 1)")
    print(f"Bernard apparaît {bernard_count} fois (attendu: 1)")
    print(f"Cindy présent: {cindy_present}")
    print(f"Album Famille présent: {famille_present}")
    
    success = (anthony_count == 1 and bernard_count == 1 and 
               cindy_present and famille_present)
    
    print(f"\n🎯 Test API NoDups: {'✅ SUCCÈS' if success else '❌ ÉCHEC'}")
    
    # Test 3: Comparaison avec fonction NoDups classique
    print("\n5. Test fonction NoDups classique:")
    
    # Réinitialiser avec doublons
    subprocess.run(cmd1, capture_output=True)
    
    # Utiliser la fonction NoDups avec -sep
    cmd4 = [
        "exiftool", "-overwrite_original",
        "-sep", "##",
        "-XMP-iptcExt:PersonInImage<${XMP-iptcExt:PersonInImage;NoDups}",
        "-XMP-dc:Subject<${XMP-dc:Subject;NoDups}",
        str(test_file)
    ]
    subprocess.run(cmd4, capture_output=True)
    
    nodups_function_state = read_tags()
    print(f"PersonInImage avec fonction NoDups: '{nodups_function_state['persons']}'")
    print(f"Subject avec fonction NoDups: '{nodups_function_state['subject']}'")
    
    # Nettoyer
    test_file.unlink()
    
    return success

if __name__ == "__main__":
    test_nodups_api()

#!/usr/bin/env python3
"""
Test 4: Simulation complète du cas d'usage réel avec technique officielle de déduplication
"""

import subprocess
import shutil
from pathlib import Path

def test_real_world_scenario():
    print("=== Test 4: Simulation cas d'usage réel ===")
    
    # Préparer fichier de test
    test_file = Path("experiments/test4.jpg")
    shutil.copy("test_assets/test_clean.jpg", test_file)
    
    # Scenario: Photo provenant d'un ancien takeout avec Anthony et Bernard
    print("\n1. État initial (ancien takeout):")
    cmd1 = [
        "exiftool", "-overwrite_original",
        "-XMP-iptcExt:PersonInImage=Anthony",
        "-XMP-iptcExt:PersonInImage=Bernard",
        "-XMP-dc:Subject=Anthony", 
        "-XMP-dc:Subject=Bernard",
        "-XMP-dc:Subject=Album: Vacances",
        "-IPTC:Keywords=Anthony",
        "-IPTC:Keywords=Bernard", 
        "-IPTC:Keywords=Album: Vacances",
        str(test_file)
    ]
    subprocess.run(cmd1, capture_output=True)
    
    # Lire l'état initial
    def read_all_tags():
        cmd_read = ["exiftool", "-a", "-s", "-s", "-s", 
                   "-XMP-iptcExt:PersonInImage", "-XMP-dc:Subject", "-IPTC:Keywords", 
                   str(test_file)]
        result = subprocess.run(cmd_read, capture_output=True, text=True, encoding='utf-8')
        lines = result.stdout.strip().split('\n')
        return {
            'persons': lines[0] if len(lines) > 0 else '',
            'subject': lines[1] if len(lines) > 1 else '',
            'keywords': lines[2] if len(lines) > 2 else ''
        }
    
    initial_state = read_all_tags()
    print(f"PersonInImage: {initial_state['persons']}")
    print(f"Subject: {initial_state['subject']}")
    print(f"Keywords: {initial_state['keywords']}")
    
    # Scenario: Nouveau takeout avec Anthony, Bernard, Cindy
    print("\n2. Nouveau takeout avec toutes les personnes (Anthony, Bernard, Cindy):")
    
    # Simulation de notre logique: lire existant, combiner, dédupliquer
    existing_persons = set(initial_state['persons'].split(', ')) if initial_state['persons'] else set()
    existing_subject = set(initial_state['subject'].split(', ')) if initial_state['subject'] else set()
    existing_keywords = set(initial_state['keywords'].split(', ')) if initial_state['keywords'] else set()
    
    # Nouvelles données du JSON
    new_persons = {"Anthony", "Bernard", "Cindy"}
    new_albums = {"Vacances", "Famille"}
    new_subject = new_persons | {f"Album: {a}" for a in new_albums}
    new_keywords = new_subject
    
    # Combiner et dédupliquer
    final_persons = existing_persons | new_persons
    final_subject = existing_subject | new_subject  
    final_keywords = existing_keywords | new_keywords
    
    print(f"Existant - Persons: {existing_persons}")
    print(f"Nouveau - Persons: {new_persons}")
    print(f"Final - Persons: {final_persons}")
    
    # Méthode 1: Réécriture complète avec assignations multiples
    print("\n3. Méthode 1: Réécriture complète")
    cmd_args = ["exiftool", "-overwrite_original"]
    
    # Ajouter les assignations pour PersonInImage
    for person in sorted(final_persons):
        cmd_args.extend(["-XMP-iptcExt:PersonInImage=" + person])
    
    # Ajouter les assignations pour Subject  
    for item in sorted(final_subject):
        cmd_args.extend(["-XMP-dc:Subject=" + item])
        
    # Ajouter les assignations pour Keywords
    for item in sorted(final_keywords):
        cmd_args.extend(["-IPTC:Keywords=" + item])
    
    cmd_args.append(str(test_file))
    subprocess.run(cmd_args, capture_output=True)
    
    result1 = read_all_tags()
    print(f"PersonInImage: {result1['persons']}")
    print(f"Subject: {result1['subject']}")
    print(f"Keywords: {result1['keywords']}")
    
    # Réinitialiser pour test méthode 2
    shutil.copy("test_assets/test_clean.jpg", test_file)
    subprocess.run(cmd1, capture_output=True)  # Remettre état initial
    
    # Méthode 2: Technique officielle de déduplication
    print("\n4. Méthode 2: Technique officielle (-= puis +=)")
    cmd_args2 = ["exiftool", "-overwrite_original"]
    
    # Pour PersonInImage: supprimer puis ajouter chaque élément final
    for person in sorted(final_persons):
        cmd_args2.extend([f"-XMP-iptcExt:PersonInImage-={person}", f"-XMP-iptcExt:PersonInImage+={person}"])
    
    # Pour Subject
    for item in sorted(final_subject):
        cmd_args2.extend([f"-XMP-dc:Subject-={item}", f"-XMP-dc:Subject+={item}"])
        
    # Pour Keywords
    for item in sorted(final_keywords):
        cmd_args2.extend([f"-IPTC:Keywords-={item}", f"-IPTC:Keywords+={item}"])
    
    cmd_args2.append(str(test_file))
    subprocess.run(cmd_args2, capture_output=True)
    
    result2 = read_all_tags()
    print(f"PersonInImage: {result2['persons']}")
    print(f"Subject: {result2['subject']}")
    print(f"Keywords: {result2['keywords']}")
    
    # Nettoyer
    test_file.unlink()
    
    # Comparaison
    print("\n5. Comparaison des méthodes:")
    print(f"Méthode 1 - Persons: {result1['persons']}")
    print(f"Méthode 2 - Persons: {result2['persons']}")
    
    success1 = "Cindy" in result1['persons'] and result1['persons'].count("Anthony") == 1
    success2 = "Cindy" in result2['persons'] and result2['persons'].count("Anthony") == 1
    
    print(f"Méthode 1 succès: {success1}")
    print(f"Méthode 2 succès: {success2}")

if __name__ == "__main__":
    test_real_world_scenario()

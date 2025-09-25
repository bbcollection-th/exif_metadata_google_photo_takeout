#!/usr/bin/env python3
"""Script de test pour diagnostiquer et corriger les problèmes de format de fichier."""

import sys
import subprocess
from pathlib import Path

def test_file_with_exiftool(file_path):
    """Tester un fichier avec ExifTool pour diagnostiquer les problèmes de format."""
    file_path = Path(file_path)
    
    if not file_path.exists():
        print(f"❌ Fichier non trouvé : {file_path}")
        return
    
    print(f"🔍 Test du fichier : {file_path}")
    print(f"📁 Extension actuelle : {file_path.suffix}")
    
    # Test 1: Obtenir le type de fichier détecté par ExifTool
    try:
        result = subprocess.run(
            ['exiftool', '-FileType', '-FileTypeExtension', str(file_path)],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print("✅ Détection du type par ExifTool :")
            print(result.stdout)
        else:
            print("❌ Erreur lors de la détection du type :")
            print(result.stderr)
    except Exception as e:
        print(f"❌ Erreur ExifTool : {e}")
        return
    
    # Test 2: Tenter d'écrire une métadonnée simple
    try:
        result = subprocess.run(
            ['exiftool', '-Description=Test diagnostic', '-charset', 'utf8', str(file_path)],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print("✅ Test d'écriture de métadonnées : Succès")
            print(result.stdout)
        else:
            print("❌ Test d'écriture de métadonnées : Échec")
            print(result.stderr)
            
            # Si l'erreur mentionne PNG/JPEG, proposer une solution
            if "not a valid png" in result.stderr.lower() and "jpeg" in result.stderr.lower():
                print("\n🔧 SOLUTION DÉTECTÉE : Extension incorrecte")
                print("Le fichier semble être un JPEG avec une extension .PNG")
                
                # Proposer le renommage
                new_path = file_path.with_suffix('.jpg')
                print(f"💡 Renommage suggéré : {file_path.name} → {new_path.name}")
                
                response = input("Voulez-vous renommer le fichier ? (o/n): ")
                if response.lower() in ['o', 'oui', 'y', 'yes']:
                    try:
                        file_path.rename(new_path)
                        print(f"✅ Fichier renommé avec succès : {new_path}")
                        
                        # Test avec le nouveau nom
                        test_result = subprocess.run(
                            ['exiftool', '-Description=Test après renommage', str(new_path)],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        
                        if test_result.returncode == 0:
                            print("✅ Le fichier renommé fonctionne maintenant !")
                        else:
                            print("❌ Problème persiste après renommage")
                            print(test_result.stderr)
                            
                    except Exception as e:
                        print(f"❌ Erreur lors du renommage : {e}")
                        
    except Exception as e:
        print(f"❌ Erreur lors du test d'écriture : {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python diagnostic_format.py <chemin_du_fichier>")
        print("Exemple: python diagnostic_format.py 'C:/path/to/IMG_2519.PNG'")
        sys.exit(1)
    
    test_file_with_exiftool(sys.argv[1])
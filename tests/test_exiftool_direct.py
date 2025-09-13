#!/usr/bin/env python3

import json
import tempfile
import shutil
from pathlib import Path
from PIL import Image
import subprocess

def test_exiftool_direct():
    """Tester ExifTool directement."""
    
    # Créer une image de test
    temp_dir = Path(tempfile.mkdtemp())
    media_path = temp_dir / "test.jpg"
    img = Image.new('RGB', (100, 100), color='blue')
    img.save(media_path)
    
    try:
        print("=== TEST EXIFTOOL DIRECT ===\n")
        
        # 1. Ajouter des keywords initiaux
        print("1. Ajout keywords initiaux...")
        subprocess.run([
            "exiftool", "-overwrite_original",
            "-IPTC:Keywords=Original Person",
            "-IPTC:Keywords=Album: Original Album",
            str(media_path)
        ], check=True)
        
        # Lire
        result = subprocess.run([
            "exiftool", "-json", str(media_path)
        ], capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)[0]
        print(f"   Keywords après ajout initial: {data.get('Keywords', 'AUCUN')}")
        
        # 2. Essayer -=, +=
        print("\n2. Test avec -= puis +=...")
        try:
            result = subprocess.run([
                "exiftool", "-overwrite_original",
                "-IPTC:Keywords-=New Person",  # Supprime (ne devrait rien faire)
                "-IPTC:Keywords+=New Person",  # Ajoute
                str(media_path)
            ], capture_output=True, text=True, check=True)
            print(f"   ExifTool stdout: {result.stdout}")
            print(f"   ExifTool stderr: {result.stderr}")
        except subprocess.CalledProcessError as e:
            print(f"   ERREUR: {e.stderr}")
        
        # Lire résultat
        result = subprocess.run([
            "exiftool", "-json", str(media_path)
        ], capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)[0]
        print(f"   Keywords après -= +=: {data.get('Keywords', 'AUCUN')}")
        
        # 3. Essayer juste +=
        print("\n3. Test avec += seulement...")
        subprocess.run([
            "exiftool", "-overwrite_original",
            "-IPTC:Keywords+=Another Person",
            str(media_path)
        ], check=True)
        
        # Lire résultat
        result = subprocess.run([
            "exiftool", "-json", str(media_path)
        ], capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)[0]
        print(f"   Keywords après += seul: {data.get('Keywords', 'AUCUN')}")
        
    finally:
        # Nettoyer
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    test_exiftool_direct()

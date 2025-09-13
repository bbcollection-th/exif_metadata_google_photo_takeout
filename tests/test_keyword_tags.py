#!/usr/bin/env python3

import sys
import json
import tempfile
import shutil
from pathlib import Path
from PIL import Image

# Ajouter le chemin du module
sys.path.insert(0, str(Path(__file__).parent / "src"))

import subprocess

def _run_exiftool_read(file_path: Path) -> dict:
    """Lire les métadonnées avec exiftool."""
    try:
        result = subprocess.run([
            "exiftool", "-json", "-charset", "utf8", str(file_path)
        ], capture_output=True, text=True, check=True, timeout=30)
        
        data = json.loads(result.stdout)
        return data[0] if data else {}
    except (subprocess.CalledProcessError, json.JSONDecodeError, subprocess.TimeoutExpired, FileNotFoundError):
        return {}

def test_keyword_tags():
    """Tester quels tags keyword fonctionnent."""
    
    # Créer une image de test
    temp_dir = Path(tempfile.mkdtemp())
    media_path = temp_dir / "test.jpg"
    img = Image.new('RGB', (100, 100), color='blue')
    img.save(media_path)
    
    try:
        # Tester différents tags Keywords
        test_tags = [
            "Keywords",
            "IPTC:Keywords", 
            "XMP-dc:Subject",
            "XMP:Keywords",
            "EXIF:Keywords"
        ]
        
        for tag in test_tags:
            print(f"\n=== Test tag: {tag} ===")
            
            # Écrire avec ce tag
            try:
                subprocess.run([
                    "exiftool", "-overwrite_original",
                    f"-{tag}=Test Person",
                    str(media_path)
                ], capture_output=True, text=True, check=True, timeout=30)
                
                # Lire les métadonnées
                metadata = _run_exiftool_read(media_path)
                
                print(f"Écriture réussie avec {tag}")
                print(f"Keywords trouvés: {metadata.get('Keywords', 'AUCUN')}")
                print(f"Subject trouvé: {metadata.get('Subject', 'AUCUN')}")
                
                # Nettoyer pour le test suivant
                subprocess.run([
                    "exiftool", "-overwrite_original",
                    f"-{tag}=",
                    str(media_path)
                ], capture_output=True, text=True, timeout=30)
                
            except subprocess.CalledProcessError as e:
                print(f"Erreur avec {tag}: {e.stderr}")
    
    finally:
        # Nettoyer
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    test_keyword_tags()

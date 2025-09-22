#!/usr/bin/env python3
"""
Debug très détaillé du traitement favorited dans build_exiftool_args.
"""
import sys
import logging
from pathlib import Path

# Ajouter le module au path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from google_takeout_metadata.sidecar import SidecarData
from google_takeout_metadata.config_loader import ConfigLoader
from google_takeout_metadata.exif_writer import build_exiftool_args

def debug_build_args_detailed():
    """Debug détaillé de build_exiftool_args."""
    print("=== Debug détaillé build_exiftool_args ===")
    
    # Activer le logging debug
    logging.basicConfig(level=logging.DEBUG)
    
    # Créer des données de test avec favori
    meta = SidecarData(title="Photo Favorite Test")
    meta.favorited = True
    
    print(f"meta.favorited = {meta.favorited} (type: {type(meta.favorited)})")
    
    # Charger la configuration
    config_loader = ConfigLoader()
    config_loader.load_config()
    
    # Examiner les mappings favorited avant génération
    mappings = config_loader.config.get('exif_mapping', {})
    print(f"\nMappings favorited dans config:")
    for name, config in mappings.items():
        if 'favorited' in name:
            print(f"  {name}: strategy={config.get('default_strategy')}, tags={config.get('target_tags_image')}")
    
    # Générer les arguments avec debug
    try:
        args = build_exiftool_args(meta, Path("test.jpg"), False, config_loader)
        
        print(f"\n✅ Arguments générés ({len(args)}):")
        for i, arg in enumerate(args, 1):
            print(f"  {i:2d}. {arg}")
        
        # Analyser spécifiquement les arguments favorited
        favorited_args = [arg for arg in args if any(keyword in arg for keyword in ['Rating', 'Label', 'favorited', 'Favorite'])]
        print(f"\n🔍 Arguments favorited ({len(favorited_args)}):")
        for arg in favorited_args:
            print(f"  • {arg}")
            
    except Exception as e:
        print(f"\n❌ Erreur lors de la génération: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_build_args_detailed()
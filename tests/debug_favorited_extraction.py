#!/usr/bin/env python3
"""
Debug détaillé du traitement favorited.
"""
import sys
from pathlib import Path

# Ajouter le module au path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from google_takeout_metadata.sidecar import SidecarData
from google_takeout_metadata.config_loader import ConfigLoader

def debug_favorited_extraction():
    """Debug de l'extraction des valeurs favorited."""
    print("=== Debug extraction favorited ===")
    
    # Créer des données de test avec favori
    meta = SidecarData(title="Photo Favorite Test")
    meta.favorited = True
    
    # Charger la configuration
    config_loader = ConfigLoader()
    config_loader.load_config()
    
    mappings = config_loader.config.get('exif_mapping', {})
    
    print(f"meta.favorited = {meta.favorited} (type: {type(meta.favorited)})")
    
    # Tester l'extraction pour chaque mapping favorited
    for name, mapping_config in mappings.items():
        if 'favorited' in name:
            print(f"\n📋 Mapping: {name}")
            
            source_fields = mapping_config.get('source_fields', [])
            print(f"   source_fields: {source_fields}")
            
            # Simuler l'extraction de valeur
            value = None
            for field in source_fields:
                if hasattr(meta, field):
                    value = getattr(meta, field)
                    break
                    
            print(f"   Valeur extraite: {value} (type: {type(value)})")
            
            # Appliquer value_mapping
            value_mapping = mapping_config.get('value_mapping', {})
            if value_mapping:
                str_value = str(value).lower()
                if str_value in value_mapping:
                    mapped_value = value_mapping[str_value]
                    print(f"   Valeur mappée: {mapped_value} (original: {str_value})")
                else:
                    print(f"   Pas de mapping pour: {str_value}")
                    print(f"   Mappings disponibles: {list(value_mapping.keys())}")

if __name__ == "__main__":
    debug_favorited_extraction()
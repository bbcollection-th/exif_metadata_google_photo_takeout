#!/usr/bin/env python3
"""
Debug du mapping favorited_label dans la configuration.
"""
import sys
from pathlib import Path

# Ajouter le module au path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from google_takeout_metadata.config_loader import ConfigLoader

def debug_config():
    """Debug de la configuration."""
    print("=== Debug configuration favorited_label ===")
    
    config_loader = ConfigLoader()
    config_loader.load_config()
    
    mappings = config_loader.config.get('exif_mapping', {})
    
    print(f"Nombre total de mappings: {len(mappings)}")
    
    # Vérifier les mappings liés à favorited
    favorited_mappings = {k: v for k, v in mappings.items() if 'favorited' in k}
    
    print(f"\nMappings 'favorited' trouvés: {len(favorited_mappings)}")
    for name, config in favorited_mappings.items():
        print(f"\n📋 Mapping: {name}")
        print(f"   source_fields: {config.get('source_fields')}")
        print(f"   target_tags_image: {config.get('target_tags_image')}")
        print(f"   default_strategy: {config.get('default_strategy')}")
        print(f"   value_mapping: {config.get('value_mapping')}")
    
    # Vérifier les stratégies
    strategies = config_loader.config.get('strategies', {})
    preserve_positive = strategies.get('preserve_positive_rating', {})
    
    print(f"\n📋 Stratégie preserve_positive_rating:")
    print(f"   description: {preserve_positive.get('description')}")
    print(f"   condition_template: {preserve_positive.get('condition_template')}")
    print(f"   special_logic: {preserve_positive.get('special_logic')}")

if __name__ == "__main__":
    debug_config()
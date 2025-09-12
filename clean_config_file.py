#!/usr/bin/env python3
"""
Script pour nettoyer un fichier de configuration EXIF en supprimant les informations de debug.

Usage:
    python clean_config_file.py exif_mapping_config.json
"""

import json
import argparse
from pathlib import Path

def clean_config_file(input_file: Path, output_file: Path = None):
    """Nettoie un fichier de configuration en supprimant les infos de debug"""
    
    if not input_file.exists():
        print(f"❌ Fichier introuvable : {input_file}")
        return False
    
    # Charger la configuration existante
    with open(input_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    print(f"📖 Lecture de : {input_file}")
    
    # Créer la version épurée
    clean_config = {
        "metadata_mappings": {},
        "strategies": config.get("strategies", {}),
        "global_settings": config.get("global_settings", {})
    }
    
    # Nettoyer les stratégies (supprimer icons et infos techniques)
    for strategy_name, strategy in clean_config["strategies"].items():
        # Garder seulement les propriétés essentielles
        cleaned_strategy = {
            "description": strategy.get("description", ""),
        }
        
        # Ajouter les propriétés techniques nécessaires
        for key in ["exiftool_args", "condition_template", "pattern"]:
            if key in strategy:
                cleaned_strategy[key] = strategy[key]
        
        clean_config["strategies"][strategy_name] = cleaned_strategy
    
    # Nettoyer les mappings (supprimer _discovery_info et autres infos de debug)
    original_count = len(config.get("metadata_mappings", {}))
    cleaned_count = 0
    
    for name, mapping in config.get("metadata_mappings", {}).items():
        clean_mapping = {}
        
        # Copier seulement les propriétés essentielles
        essential_props = [
            "source_fields", "target_tags", "default_strategy",
            "sanitize", "format", "data_transformer", "list_separator",
            "normalize", "value_mapping", "processing"
        ]
        
        for prop in essential_props:
            if prop in mapping:
                clean_mapping[prop] = mapping[prop]
        
        # Ajouter seulement si le mapping a du contenu utile
        if clean_mapping and "source_fields" in clean_mapping and "target_tags" in clean_mapping:
            clean_config["metadata_mappings"][name] = clean_mapping
            cleaned_count += 1
    
    # Déterminer le fichier de sortie
    if output_file is None:
        output_file = input_file
    
    # Sauvegarder la version nettoyée
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(clean_config, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Configuration nettoyée sauvée dans : {output_file}")
    print(f"📊 Mappings conservés : {cleaned_count}/{original_count}")
    
    # Sauvegarder l'original si on écrase
    if output_file == input_file:
        backup_file = input_file.with_name(f"{input_file.stem}_backup{input_file.suffix}")
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"💾 Original sauvé dans : {backup_file}")
    
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Nettoyer un fichier de configuration EXIF"
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Fichier de configuration à nettoyer"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Fichier de sortie (par défaut: écrase l'original)"
    )
    
    args = parser.parse_args()
    
    success = clean_config_file(args.input_file, args.output)
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())

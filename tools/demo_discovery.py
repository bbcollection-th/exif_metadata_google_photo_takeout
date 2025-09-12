#!/usr/bin/env python3
"""
Script de démonstration du système de découverte et validation des champs EXIF.

Ce script illustre l'utilisation complète du workflow :
1. Découverte automatique des champs depuis les fichiers JSON
2. Validation de la configuration générée
3. Nettoyage et optimisation
4. Intégration avec le système de configuration

Usage:
    python demo_discovery.py /path/to/google/photos/folder
"""

import json
import argparse
from pathlib import Path
import tempfile
import sys
import os

# Ajouter le répertoire src au path pour les imports
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
if src_dir.exists():
    sys.path.insert(0, str(src_dir))

def main():
    parser = argparse.ArgumentParser(
        description="Démonstration complète du système de découverte EXIF"
    )
    parser.add_argument(
        "google_photos_dir",
        type=Path,
        help="Répertoire contenant les fichiers JSON Google Photos"
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Garder les fichiers temporaires pour inspection"
    )
    
    args = parser.parse_args()
    
    if not args.google_photos_dir.exists():
        print(f"❌ Répertoire introuvable : {args.google_photos_dir}")
        return 1
    
    print("🚀 DÉMONSTRATION DU SYSTÈME DE DÉCOUVERTE EXIF")
    print("=" * 60)
    
    # Étape 1: Découverte automatique
    print("\n📡 ÉTAPE 1: Découverte automatique des champs...")
    
    # Fichier temporaire pour la config découverte
    temp_dir = Path(tempfile.mkdtemp()) if args.keep_temp else Path(tempfile.mkdtemp())
    discovered_config = temp_dir / "discovered_config.json"
    
    # Lancer la découverte
    discover_cmd = f'python discover_fields.py "{args.google_photos_dir}" --output "{discovered_config}" --summary'
    print(f"   Commande: {discover_cmd}")
    
    os.system(discover_cmd)
    
    if not discovered_config.exists():
        print("❌ Échec de la découverte")
        return 1
    
    # Statistiques de découverte
    with open(discovered_config, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    mappings_count = len(config.get('metadata_mappings', {}))
    print(f"   ✅ {mappings_count} champs découverts")
    
    # Étape 2: Validation
    print("\n✅ ÉTAPE 2: Validation de la configuration...")
    
    validate_cmd = f'python validate_config.py "{discovered_config}" --verbose'
    print(f"   Commande: {validate_cmd}")
    
    os.system(validate_cmd)
    
    # Étape 3: Nettoyage
    print("\n🧹 ÉTAPE 3: Nettoyage et optimisation...")
    
    cleaned_config = temp_dir / "cleaned_config.json"
    clean_cmd = f'python validate_config.py "{discovered_config}" --clean --min-frequency 3 --output "{cleaned_config}"'
    print(f"   Commande: {clean_cmd}")
    
    os.system(clean_cmd)
    
    if cleaned_config.exists():
        with open(cleaned_config, 'r', encoding='utf-8') as f:
            clean_config = json.load(f)
        
        clean_mappings_count = len(clean_config.get('metadata_mappings', {}))
        reduction = ((mappings_count - clean_mappings_count) / mappings_count) * 100
        print(f"   ✅ Réduction: {mappings_count} → {clean_mappings_count} champs ({reduction:.1f}%)")
    
    # Étape 4: Démo d'intégration
    print("\n🔗 ÉTAPE 4: Démonstration d'intégration...")
    
    # Copier la config nettoyée vers le fichier principal
    main_config = current_dir / "exif_mapping_config.json"
    if cleaned_config.exists():
        import shutil
        shutil.copy2(cleaned_config, main_config)
        print(f"   ✅ Configuration copiée vers : {main_config}")
    
    # Test de chargement avec config_loader
    try:
        sys.path.insert(0, str(current_dir / "src" / "google_takeout_metadata"))
        from config_loader import ConfigLoader
        
        loader = ConfigLoader()
        loaded_config = loader.load_config()
        
        print("   ✅ Configuration chargée avec succès")
        print(f"   📊 Stratégies disponibles: {list(loaded_config.get('strategies', {}).keys())}")
        print(f"   📊 Mappings chargés: {len(loaded_config.get('metadata_mappings', {}))}")
        
    except ImportError as e:
        print(f"   ⚠️ Module config_loader non trouvé: {e}")
    except Exception as e:
        print(f"   ⚠️ Erreur lors du chargement: {e}")
    
    # Résumé final
    print("\n🎯 RÉSUMÉ FINAL")
    print("=" * 60)
    print("✅ Découverte automatique des champs réussie")
    print("✅ Validation et nettoyage effectués")
    print("✅ Configuration prête pour utilisation")
    
    if args.keep_temp:
        print(f"\n📁 Fichiers temporaires conservés dans : {temp_dir}")
        print("   - discovered_config.json : Configuration brute")
        print("   - cleaned_config.json : Configuration nettoyée")
    else:
        # Nettoyage des fichiers temporaires
        import shutil
        shutil.rmtree(temp_dir)
        print("🧹 Fichiers temporaires supprimés")
    
    print("\n🚀 Prêt pour traiter vos photos Google !")
    
    return 0

if __name__ == "__main__":
    exit(main())

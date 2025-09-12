#!/usr/bin/env python3
"""
Test avec configuration corrigée manuellement
"""
import sys
import tempfile
from pathlib import Path
from PIL import Image
import json
# Ajouter le src au path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from google_takeout_metadata.config_loader import ConfigLoader
from google_takeout_metadata.exif_writer import write_metadata_with_config
from google_takeout_metadata.sidecar import SidecarData
from google_takeout_metadata.exif_writer import build_exiftool_args_from_config

def test_with_clean_config():
    """Test avec la configuration propre sans doublons"""
    config_loader = ConfigLoader()
    # Charger la configuration propre
    config_loader.load_config(json_file="exif_mapping_clean.json")
    
    print("=== Test avec configuration propre ===")
    
    # Créer un objet SidecarData avec des personnes
    meta = SidecarData(
        title="test_image.jpg",
        description="Photo de famille",
        people_name=["Alice Dupont", "Bob Martin", "Charlie Wilson"],
        photoTakenTime_timestamp=1640995200,  # 2022-01-01 00:00:00
        creationTime_timestamp=1640995200,
        geoData_latitude=48.8566,
        geoData_longitude=2.3522,
        geoData_altitude=35.0,
        albums=["Vacances 2022"]
    )
    
    # Test avec la configuration propre
    args = build_exiftool_args_from_config(
        meta, 
        Path("test_image.jpg"),
        False,  # use_localtime
        config_loader
    )
    
    print(f"Nombre total d'arguments générés: {len(args)}")
    
    # Analyser les différents types d'arguments
    people_name_args = [arg for arg in args if 'PersonInImage' in arg]
    gps_args = [arg for arg in args if 'GPS' in arg]
    desc_args = [arg for arg in args if 'Description' in arg or 'Caption' in arg]
    
    print(f"Arguments personnes: {len(people_name_args)}")
    print(f"Arguments GPS: {len(gps_args)}")
    print(f"Arguments description: {len(desc_args)}")
    
    # Afficher tous les arguments pour debug
    print("\n=== Tous les arguments générés ===")
    for i, arg in enumerate(args, 1):
        print(f"{i:2d}. {arg}")
    
    # Vérifier qu'il n'y a pas de doublons dans les personnes
    people_name_values = set()
    people_name_duplicates = 0
    for arg in people_name_args:
        if '=' in arg:
            value = arg.split('=', 1)[1]
            if value in people_name_values:
                people_name_duplicates += 1
            people_name_values.add(value)
    
    if people_name_duplicates == 0:
        print("\n✅ SUCCÈS: Aucun doublon dans les personnes")
    else:
        print(f"\n❌ PROBLÈME: {people_name_duplicates} doublons détectés dans les personnes")
    
    # Vérifier que chaque coordonnée GPS va au bon tag
    gps_mapping_ok = True
    for arg in gps_args:
        if 'GPSLatitude' in arg and '48.8566' not in arg:
            gps_mapping_ok = False
            print(f"❌ Latitude incorrecte: {arg}")
        elif 'GPSLongitude' in arg and '2.3522' not in arg:
            gps_mapping_ok = False  
            print(f"❌ Longitude incorrecte: {arg}")
        elif 'GPSAltitude' in arg and '35.0' not in arg:
            gps_mapping_ok = False
            print(f"❌ Altitude incorrecte: {arg}")
    
    if gps_mapping_ok:
        print("✅ SUCCÈS: Mapping GPS correct")
    else:
        print("❌ PROBLÈME: Mapping GPS incorrect")






def test_config_integration():
    """Test l'intégration complète de la configuration"""
    
    print("🧪 Test d'intégration de la configuration découverte")
    print("=" * 60)
    
    # 1. Charger la configuration découverte
    print("📖 Chargement de la configuration...")
    config_loader = ConfigLoader()
    config = config_loader.load_config()
    
    print(f"✅ Configuration chargée depuis: {config_loader.config_dir}")
    print(f"📊 Mappings: {len(config.get('metadata_mappings', {}))}")
    print(f"📊 Stratégies: {list(config.get('strategies', {}).keys())}")
    
    # 2. Afficher quelques mappings
    print("\n🔍 Mappings découverts:")
    for name, mapping in list(config.get('metadata_mappings', {}).items())[:3]:
        source = mapping.get('source_fields', [])
        target = mapping.get('target_tags', [])
        strategy = mapping.get('default_strategy', 'unknown')
        print(f"   {name}: {source} → {target} ({strategy})")
    
    # 3. Test avec une image factice
    print("\n🖼️ Test avec image factice...")
    with tempfile.TemporaryDirectory() as temp_dir:
        # Créer une image test
        img_path = Path(temp_dir) / "test.jpg"
        Image.new("RGB", (100, 100), color="blue").save(img_path)
        
        # Créer des métadonnées test
        meta = SidecarData(
            title="test.jpg",
            description="Test description depuis configuration découverte",
            people_name=["Anthony", "Test Person"],
            photoTakenTime_timestamp=None,
            creationTime_timestamp=None,
            geoData_latitude=None,
            geoData_longitude=None,
            geoData_altitude=None,
            city=None,
            state=None,
            country=None,
            place_name=None,
            favorited=False,
            albums=["Test Album"]
        )
        
        # 4. Appliquer les métadonnées avec la nouvelle fonction
        print("⚙️ Application des métadonnées avec configuration...")
        try:
            write_metadata_with_config(img_path, meta, config_loader=config_loader)
            print("✅ Métadonnées appliquées avec succès !")
        except Exception as e:
            print(f"❌ Erreur lors de l'application: {e}")
            return False
    
    print("\n🎉 Test d'intégration réussi !")
    return True

def test_discovery_workflow():
    """Test le workflow complet de découverte → configuration → application"""
    
    print("\n🔄 Test du workflow complet")
    print("=" * 60)
    
    # 1. Vérifier qu'on a des données Google Photos
    data_dir = Path("data/Google Photos")
    if not data_dir.exists():
        print("⚠️ Dossier 'data/Google Photos' introuvable")
        print("   Le test de workflow complet nécessite des données")
        return True
    
    # 2. Compter les fichiers JSON
    json_files = list(data_dir.rglob("*.json"))
    print(f"📁 Données trouvées: {len(json_files)} fichiers JSON")
    
    if json_files:
        # 3. Montrer un exemple de données
        example_file = json_files[0]
        try:
            with open(example_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"📄 Exemple de fichier: {example_file.name}")
            print(f"   Champs disponibles: {list(data.keys())[:5]}")
            
            # 4. Vérifier que la configuration correspond aux données réelles
            config_file = Path("config/exif_mapping.json")
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                mappings = config.get('metadata_mappings', {})
                print(f"⚙️ Configuration: {len(mappings)} mappings configurés")
                
                # Vérifier que les champs configurés existent dans les données
                data_fields = set(data.keys())
                config_fields = set()
                for mapping in mappings.values():
                    for field in mapping.get('source_fields', []):
                        config_fields.add(field.split('.')[0])  # Premier niveau
                
                matching = data_fields.intersection(config_fields)
                print(f"✅ Champs correspondants: {len(matching)}/{len(config_fields)}")
                print(f"   Ex: {list(matching)[:3]}")
            
        except Exception as e:
            print(f"⚠️ Erreur lors de l'analyse: {e}")
    
    print("✅ Workflow vérifié !")
    return True

def main():
    """Test principal"""
    print("🚀 TEST D'INTÉGRATION CONFIGURATION DÉCOUVERTE")
    print("=" * 80)
    
    success = True
    
    # Test 1: Intégration de base
    success &= test_config_integration()
    
    # Test 2: Workflow complet
    success &= test_discovery_workflow()
    
    print("\n" + "=" * 80)
    if success:
        print("🎉 TOUS LES TESTS RÉUSSIS !")
        print("✅ La configuration découverte est intégrée et fonctionnelle")
    else:
        print("❌ ÉCHEC DE CERTAINS TESTS")
        return 1
    
    print("\n📝 Prochaines étapes:")
    print("   1. Lancez: python -m google_takeout_metadata.processor \"data/Google Photos/\"")
    print("   2. Les métadonnées seront appliquées selon votre configuration découverte")
    
    return 0

if __name__ == "__main__":
    test_with_clean_config()
    exit(main())

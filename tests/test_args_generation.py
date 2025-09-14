#!/usr/bin/env python3
"""
Test simple de génération d'arguments ExifTool depuis la configuration découverte
"""

import sys
from pathlib import Path

# Ajouter le src au path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from google_takeout_metadata.config_loader import ConfigLoader
from google_takeout_metadata.exif_writer import build_exiftool_args
from google_takeout_metadata.sidecar import SidecarData

def test_args_generation():
    """Test la génération d'arguments sans ExifTool"""
    
    print("🧪 Test de génération d'arguments ExifTool")
    print("=" * 60)
    
    # 1. Charger la configuration
    config_loader = ConfigLoader()
    config = config_loader.load_config()
    print(f"✅ Configuration chargée: {len(config.get('exif_mapping', {}))} mappings")
    
    # 2. Créer des métadonnées test
    meta = SidecarData(
        title="test.jpg",
        description="Description de test",
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
    
    # 3. Générer les arguments
    print("\n⚙️ Génération des arguments ExifTool...")
    try:
        args = build_exiftool_args(meta, Path("test.jpg"), False, config_loader)
        
        print(f"✅ {len(args)} arguments générés:")
        for i, arg in enumerate(args[:10]):  # Afficher les 10 premiers
            print(f"   {i+1:2d}. {arg}")
        
        if len(args) > 10:
            print(f"   ... et {len(args) - 10} autres")
            
        # 4. Analyser les arguments
        print("\n🔍 Analyse des arguments:")
        tag_args = [arg for arg in args if arg.startswith('-') and '=' in arg]
        condition_args = [arg for arg in args if arg.startswith('-if')]
        mode_args = [arg for arg in args if arg in ['-wm', 'cg', '-overwrite_original']]
        
        print(f"   📝 Tags à écrire: {len(tag_args)}")
        print(f"   🔍 Conditions: {len(condition_args)}")
        print(f"   ⚙️ Options de mode: {len(mode_args)}")
        
        # 5. Vérifier les tags critiques
        people_name_tags = [arg for arg in tag_args if 'PersonInImage' in arg]
        desc_tags = [arg for arg in tag_args if 'ImageDescription' in arg or 'Description' in arg]
        
        print("\n✅ Tags trouvés:")
        print(f"   👥 Personnes: {len(people_name_tags)} arguments")
        for tag in people_name_tags[:3]:
            print(f"      {tag}")
        
        print(f"   📄 Description: {len(desc_tags)} arguments")
        for tag in desc_tags[:3]:
            print(f"      {tag}")
            
        # Assertions pour pytest
        assert len(args) > 0, "Aucun argument généré"
        assert len(tag_args) > 0, "Aucun tag à écrire généré"
        assert len(people_name_tags) > 0, "Aucun argument PersonInImage généré"
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        raise  # Re-lancer l'exception pour pytest

def main():
    """Test principal"""
    print("🚀 TEST DE GÉNÉRATION D'ARGUMENTS EXIFTOOL")
    print("=" * 80)
    
    try:
        test_args_generation()
        success = True
    except Exception:
        success = False
    
    print("\n" + "=" * 80)
    if success:
        print("🎉 TEST RÉUSSI !")
        print("✅ La génération d'arguments fonctionne avec la configuration découverte")
    else:
        print("❌ ÉCHEC DU TEST")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())

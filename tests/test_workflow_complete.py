#!/usr/bin/env python3
"""
Test complet du workflow avec correction de timezone activée.
"""

import sys
import tempfile
import shutil
from pathlib import Path

# Ajouter le module au path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from google_takeout_metadata.sidecar import SidecarData
from google_takeout_metadata.config_loader import ConfigLoader
from google_takeout_metadata.exif_writer import build_exiftool_args

def test_full_workflow_with_timezone():
    """Test du workflow complet avec correction de timezone."""
    print("=== Test workflow complet avec timezone ===")
    
    # Créer des données de test
    meta = SidecarData(title="Photo de Test Paris")
    meta.description = "Une belle photo prise à Paris"
    meta.geoData_latitude = 48.8566  # Paris
    meta.geoData_longitude = 2.3522
    meta.photoTakenTime_timestamp = 1658760600  # 25 juillet 2022 14:30 UTC
    meta.people_name = ["John Doe", "Jane Smith"]
    meta.favorited = True
    meta.city = "Paris"
    meta.country = "France"
    
    # Charger la configuration
    config_loader = ConfigLoader()
    config_loader.load_config()
    
    # Activer temporairement la correction de timezone
    original_tz_config = config_loader.config.get('timezone_correction', {})
    config_loader.config['timezone_correction'] = {
        'enabled': True,
        'use_absolute_values': True,
        'fallback_to_utc': False
    }
    
    try:
        # Créer un fichier temporaire pour le test
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
            test_asset = Path(__file__).parent / "test_assets" / "test_clean.jpg"
            if test_asset.exists():
                shutil.copy2(test_asset, tmp_file.name)
            tmp_path = Path(tmp_file.name)
        
        # Générer les arguments ExifTool complets
        args = build_exiftool_args(meta, tmp_path, use_localTime=False, config_loader=config_loader)
        
        print(f"Arguments ExifTool générés ({len(args)} arguments):")
        for i, arg in enumerate(args, 1):
            print(f"  {i:2d}. {arg}")
        
        # Vérifications des fonctionnalités principales
        checks = {
            'Description présente': any('Description=' in arg for arg in args),
            'GPS présent': any('GPSLatitude=' in arg for arg in args),
            'Timezone correction': any('DateTimeOriginal=' in arg and ('16:50:00' in arg or '16:30:00' in arg) for arg in args),
            'Offset timezone': any('OffsetTime=' in arg and '+02:00' in arg for arg in args),
            'Personnes': any('PersonInImage' in arg for arg in args),
            'Ville': any('City=' in arg for arg in args),
            'Rating favoris': any('Rating=' in arg for arg in args),
        }
        
        print("\n=== Vérifications ===")
        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            print(f"{status} {check_name}: {'OK' if result else 'MANQUANT'}")
        
        # Test spécifique de la correction timezone
        timezone_args = [arg for arg in args if any(keyword in arg for keyword in 
                        ['DateTimeOriginal=', 'OffsetTime=', 'CreateDate='])]
        
        if timezone_args:
            print("\n=== Arguments timezone détectés ===")
            for arg in timezone_args:
                print(f"  • {arg}")
        
        all_checks_passed = all(checks.values())
        if all_checks_passed:
            print("\n🎉 Tous les tests du workflow complet sont passés !")
        else:
            print(f"\n⚠️  Certaines vérifications ont échoué : {sum(not v for v in checks.values())}/{len(checks)}")
        
        return all_checks_passed
        
    finally:
        # Restaurer la configuration originale
        config_loader.config['timezone_correction'] = original_tz_config
        
        # Nettoyer le fichier temporaire
        if 'tmp_path' in locals() and tmp_path.exists():
            tmp_path.unlink()

if __name__ == "__main__":
    try:
        success = test_full_workflow_with_timezone()
        if not success:
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur dans le test complet: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
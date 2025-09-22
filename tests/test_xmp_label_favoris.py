#!/usr/bin/env python3
"""
Test pour vérifier le support XMP:Label pour les favoris.
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

def test_xmp_label_favoris():
    """Test du nouveau support XMP:Label pour favoris."""
    print("=== Test XMP:Label pour favoris ===")
    
    # Créer des données de test avec favori
    meta = SidecarData(title="Photo Favorite Test")
    meta.favorited = True
    
    # Charger la configuration
    config_loader = ConfigLoader()
    config_loader.load_config()
    
    try:
        # Créer un fichier temporaire pour le test
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
            test_asset = Path(__file__).parent / "test_assets" / "test_clean.jpg"
            if test_asset.exists():
                shutil.copy2(test_asset, tmp_file.name)
            tmp_path = Path(tmp_file.name)
        
        # Générer les arguments ExifTool
        args = build_exiftool_args(meta, tmp_path, use_localTime=False, config_loader=config_loader)
        
        print(f"Arguments ExifTool générés ({len(args)} arguments):")
        for i, arg in enumerate(args, 1):
            print(f"  {i:2d}. {arg}")
        
        # Vérifications spécifiques
        checks = {
            'Rating=5 présent': any('Rating=5' in arg for arg in args),
            'Label=Favorite présent': any('Label=Favorite' in arg for arg in args),
            'Conditions preserve_positive_rating': any('-if' in args and ('Rating' in arg or 'Label' in arg) for arg in args),
        }
        
        print("\n=== Vérifications ===")
        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            print(f"{status} {check_name}: {'OK' if result else 'MANQUANT'}")
        
        # Vérifier les arguments spécifiques
        rating_args = [arg for arg in args if 'Rating' in arg]
        label_args = [arg for arg in args if 'Label' in arg]
        
        print(f"\n=== Arguments Rating ({len(rating_args)}) ===")
        for arg in rating_args:
            print(f"  • {arg}")
            
        print(f"\n=== Arguments Label ({len(label_args)}) ===")
        for arg in label_args:
            print(f"  • {arg}")
        
        all_checks_passed = all(checks.values())
        if all_checks_passed:
            print("\n🎉 Test XMP:Label pour favoris réussi !")
        else:
            print(f"\n⚠️  Certaines vérifications ont échoué : {sum(not v for v in checks.values())}/{len(checks)}")
        
        return all_checks_passed
        
    finally:
        # Nettoyer le fichier temporaire
        if 'tmp_path' in locals() and tmp_path.exists():
            tmp_path.unlink()

if __name__ == "__main__":
    try:
        success = test_xmp_label_favoris()
        if not success:
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur dans le test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
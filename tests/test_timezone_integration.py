#!/usr/bin/env python3
"""
Test d'intégration de la correction de fuseau horaire avec ExifTool.
"""

import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Ajouter le module au path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from google_takeout_metadata.timezone_calculator import TimezoneCalculator, TimezoneExifArgsGenerator
from google_takeout_metadata.sidecar import SidecarData
from google_takeout_metadata.exif_writer import enhance_args_with_timezone_correction

def test_timezone_integration():
    """Test d'intégration de la correction de fuseau horaire."""
    print("=== Test d'intégration timezone ===")
    
    # Créer des données de test avec GPS et timestamp
    meta = SidecarData(title="Test Photo Paris")
    meta.geoData_latitude = 48.8566  # Paris
    meta.geoData_longitude = 2.3522
    meta.photoTakenTime_timestamp = 1658760600  # 25 juillet 2022 14:30 UTC
    
    # Créer un fichier temporaire pour le test
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
        # Copier un fichier de test propre
        test_asset = Path(__file__).parent / "test_assets" / "test_clean.jpg"
        if test_asset.exists():
            shutil.copy2(test_asset, tmp_file.name)
        tmp_path = Path(tmp_file.name)
    
    try:
        # Arguments ExifTool de base
        base_args = [
            "-charset", "utf8", 
            "-codedcharacterset=utf8",
            "-EXIF:ImageDescription=Test Photo Paris"
        ]
        
        # Configuration de test pour timezone
        timezone_config = {
            'enabled': True,
            'use_absolute_values': True,
            'fallback_to_utc': False
        }
        
        # Test de l'amélioration des arguments avec timezone
        enhanced_args = enhance_args_with_timezone_correction(
            base_args, meta, tmp_path, timezone_config
        )
        
        print(f"Arguments de base: {base_args}")
        print(f"Arguments améliorés: {enhanced_args}")
        
        # Vérifications
        assert len(enhanced_args) > len(base_args), "Les arguments devraient être étendus"
        
        # Chercher les arguments de timezone dans les arguments améliorés
        timezone_found = False
        for arg in enhanced_args:
            if any(keyword in arg for keyword in ['-DateTimeOriginal=', '-OffsetTime=', '-globalTimeShift']):
                timezone_found = True
                print(f"Argument timezone trouvé: {arg}")
                break
        
        assert timezone_found, "Aucun argument de correction timezone trouvé"
        
        print("✅ Test d'intégration réussi!")
        
    finally:
        # Nettoyer le fichier temporaire
        if tmp_path.exists():
            tmp_path.unlink()

def test_timezone_args_generation():
    """Test de génération d'arguments spécifiques timezone."""
    print("\n=== Test génération arguments timezone ===")
    
    # Calculateur et générateur
    calc = TimezoneCalculator()
    generator = TimezoneExifArgsGenerator(calc)
    
    # Données GPS Paris été
    lat, lon = 48.8566, 2.3522
    test_time = datetime(2023, 7, 15, 14, 30, 0)  # Été - DST actif
    
    # Obtenir l'info timezone
    tz_info = calc.get_timezone_info(lat, lon, test_time)
    assert tz_info is not None, "Info timezone ne devrait pas être None"
    assert tz_info.is_dst, "Devrait être en DST en juillet"
    assert tz_info.offset_string == '+02:00', f"Offset devrait être +02:00, reçu: {tz_info.offset_string}"
    
    # Générer les arguments pour une image
    test_path = Path("test_photo.jpg")
    image_args = generator.generate_image_args(test_path, tz_info, use_absolute_values=True)
    
    print(f"Arguments image générés: {image_args}")
    
    # Vérifications des arguments image
    assert any('-DateTimeOriginal=' in arg for arg in image_args), "DateTimeOriginal manquant"
    assert any('-OffsetTime=' in arg for arg in image_args), "OffsetTime manquant"
    assert any('+02:00' in arg for arg in image_args), "Offset +02:00 manquant"
    
    # Test pour vidéo - utiliser un timestamp UTC
    utc_timestamp = 1658760600  # 25 juillet 2022 14:30 UTC
    video_args = generator.generate_video_args(Path("test_video.mp4"), utc_timestamp)
    
    print(f"Arguments vidéo générés: {video_args}")
    
    # Vérifications des arguments vidéo
    assert any('-QuickTime:CreateDate=' in arg for arg in video_args), "CreateDate manquant"
    assert any('-api' in arg for arg in video_args), "API QuickTime manquante"
    
    print("✅ Test génération arguments réussi!")

if __name__ == "__main__":
    try:
        test_timezone_integration()
        test_timezone_args_generation()
        print("\n🎉 Tous les tests d'intégration sont passés!")
    except Exception as e:
        print(f"\n❌ Erreur dans les tests d'intégration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
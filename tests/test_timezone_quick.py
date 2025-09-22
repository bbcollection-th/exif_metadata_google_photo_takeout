#!/usr/bin/env python3
"""
Test rapide de la fonctionnalité de correction de fuseau horaire.
"""

import sys
from pathlib import Path
from datetime import datetime

# Ajouter le module au path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from google_takeout_metadata.timezone_calculator import TimezoneCalculator
from google_takeout_metadata.sidecar import SidecarData

def test_timezone_basic():
    """Test de base de la correction de fuseau horaire."""
    print("=== Test de correction de fuseau horaire ===")
    
    # Coordonnées GPS de Paris
    paris_lat = 48.8566
    paris_lon = 2.3522
    
    # Date de test (été - DST actif)
    test_timestamp = datetime(2023, 7, 15, 14, 30, 0)  # UTC
    
    # Créer le calculateur
    calc = TimezoneCalculator()
    
    # Obtenir les informations de fuseau
    tz_info = calc.get_timezone_info(paris_lat, paris_lon, test_timestamp)
    
    print(f"Coordonnées GPS: {paris_lat}, {paris_lon}")
    print(f"Timestamp UTC: {test_timestamp}")
    print(f"Timezone ID: {tz_info.timezone_name}")
    print(f"Offset UTC: {tz_info.utc_offset_seconds}")
    print(f"Est DST: {tz_info.is_dst}")
    print(f"Heure locale: {tz_info.local_datetime}")
    print(f"Format EXIF offset: {tz_info.offset_string}")
    
    # Vérifications de base
    assert tz_info.timezone_name == 'Europe/Paris'
    assert tz_info.is_dst  # Juillet = été en Europe
    assert tz_info.offset_string == '+02:00'  # DST en été
    
    print("✅ Test de base réussi!")

def test_timezone_winter():
    """Test en hiver (pas de DST)."""
    print("\n=== Test en hiver (pas de DST) ===")
    
    # Coordonnées GPS de Paris
    paris_lat = 48.8566
    paris_lon = 2.3522
    
    # Date de test (hiver - pas de DST)
    test_timestamp = datetime(2023, 1, 15, 14, 30, 0)  # UTC
    
    # Créer le calculateur
    calc = TimezoneCalculator()
    
    # Obtenir les informations de fuseau
    tz_info = calc.get_timezone_info(paris_lat, paris_lon, test_timestamp)
    
    print(f"Timestamp UTC hiver: {test_timestamp}")
    print(f"Est DST: {tz_info.is_dst}")
    print(f"Format EXIF offset: {tz_info.offset_string}")
    
    # Vérifications
    assert tz_info.timezone_name == 'Europe/Paris'
    assert not tz_info.is_dst  # Janvier = hiver en Europe
    assert tz_info.offset_string == '+01:00'  # Heure standard en hiver
    
    print("✅ Test hiver réussi!")

def test_timezone_with_sidecar():
    """Test avec des données SidecarData."""
    print("\n=== Test avec SidecarData ===")
    
    # Créer des données de test
    meta = SidecarData(title="Test Photo")
    meta.geoData_latitude = 48.8566  # Paris
    meta.geoData_longitude = 2.3522
    meta.photoTakenTime_timestamp = 1658760600  # 25 juillet 2022 14:30 UTC
    
    # Convertir le timestamp en datetime
    photo_time = datetime.fromtimestamp(meta.photoTakenTime_timestamp)
    
    calc = TimezoneCalculator()
    tz_info = calc.get_timezone_info(meta.geoData_latitude, meta.geoData_longitude, photo_time)
    
    print(f"Photo prise le: {photo_time} UTC")
    print(f"Heure locale calculée: {tz_info.local_datetime}")
    print(f"Offset EXIF: {tz_info.offset_string}")
    
    print("✅ Test avec SidecarData réussi!")

if __name__ == "__main__":
    try:
        test_timezone_basic()
        test_timezone_winter()
        test_timezone_with_sidecar()
        print("\n🎉 Tous les tests sont passés!")
    except Exception as e:
        print(f"\n❌ Erreur dans les tests: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
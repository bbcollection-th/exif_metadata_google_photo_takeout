#!/usr/bin/env python3
"""
Test avec configuration corrigée manuellement
"""

from pathlib import Path
from google_takeout_metadata.config_loader import ConfigLoader
from google_takeout_metadata.exif_writer import build_exiftool_args_from_config
from google_takeout_metadata.sidecar import SidecarData

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

if __name__ == "__main__":
    test_with_clean_config()

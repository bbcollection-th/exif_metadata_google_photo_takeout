#!/usr/bin/env python3
"""
Test avec des données de personnes pour valider la génération d'arguments ExifTool
"""

import json
from pathlib import Path
from google_takeout_metadata.config_loader import ConfigLoader
from google_takeout_metadata.exif_writer import build_exiftool_args_from_config
from google_takeout_metadata.sidecar import SidecarData

def test_people_name_arguments():
    """Test que les personnes génèrent bien des arguments ExifTool"""
    config_loader = ConfigLoader()
    config_loader.load_config()
    
    print("=== Test avec données de personnes ===")
    
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
    
    # Test avec des vraies données de personnes
    args = build_exiftool_args_from_config(
        meta, 
        Path("test_image.jpg"),
        False,  # use_localtime
        config_loader
    )
    
    print(f"Nombre total d'arguments générés: {len(args)}")
    
    # Compter les arguments liés aux personnes
    people_name_args = [arg for arg in args if 'PersonInImage' in arg or 'people' in arg.lower()]
    print(f"Arguments liés aux personnes: {len(people_name_args)}")
    
    # Afficher tous les arguments pour debug
    print("\n=== Tous les arguments générés ===")
    for i, arg in enumerate(args, 1):
        print(f"{i:2d}. {arg}")
    
    # Focus sur les personnes
    if people_name_args:
        print(f"\n=== Arguments personnes ({len(people_name_args)}) ===")
        for arg in people_name_args:
            print(f"  {arg}")
    else:
        print("\n⚠️ AUCUN argument de personne généré")
        
        # Debug: vérifier le mapping des personnes
        mapping = config_loader.get_config().get('exif_mapping', {})
        people_name_mapping = None
        for field, config in mapping.items():
            if 'people' in field.lower() or 'person' in field.lower():
                people_name_mapping = config
                print(f"\n=== Mapping trouvé pour personnes: {field} ===")
                print(json.dumps(config, indent=2, ensure_ascii=False))
                break
        
        if not people_name_mapping:
            print("\n❌ Aucun mapping de personnes trouvé dans la configuration")

if __name__ == "__main__":
    test_people_name_arguments()

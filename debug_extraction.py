#!/usr/bin/env python3
"""
Debug de la configuration et extraction
"""

from src.google_takeout_metadata.config_loader import ConfigLoader
from src.google_takeout_metadata.sidecar import SidecarData

def debug_config_and_extraction():
    """Debug de la configuration et extraction"""
    config_loader = ConfigLoader()
    config_loader.load_config(json_file="exif_mapping_clean.json")
    
    print("=== Debug Configuration ===")
    config = config_loader.config
    
    # Afficher la structure de la configuration
    print("Structure de la configuration:")
    for key in config.keys():
        print(f"  - {key}: {type(config[key])}")
        
    # Afficher les mappings
    mappings = config.get('exif_mapping', {})
    print(f"\nMappings trouvés: {len(mappings)}")
    for mapping_name, mapping_config in mappings.items():
        source_fields = mapping_config.get('source_fields', [])
        target_tags = mapping_config.get('target_tags', [])
        print(f"  - {mapping_name}: {source_fields} → {target_tags}")
    
    # Test des données  
    print("\n=== Debug Métadonnées ===")
    meta = SidecarData(
        title="test_image.jpg",
        description="Photo de famille",
        people_name=["Alice Dupont", "Bob Martin"],
        photoTakenTime_timestamp=1640995200,
        creationTime_timestamp=1640995200,
        geoData_latitude=48.8566,
        geoData_longitude=2.3522,
        geoData_altitude=35.0,
        albums=["Vacances 2022"]
    )
    
    print(f"Meta.description: {meta.description}")
    print(f"Meta.people_name: {meta.people_name}")
    print(f"Meta.photoTakenTime_timestamp: {meta.photoTakenTime_timestamp}")
    print(f"Meta.geoData_latitude: {meta.geoData_latitude}")
    
    # Test manuel d'extraction
    print("\n=== Test Extraction Manuelle ===")
    from src.google_takeout_metadata.exif_writer import _extract_value_from_meta
    
    for mapping_name, mapping_config in mappings.items():
        source_fields = mapping_config.get('source_fields', [])
        value = _extract_value_from_meta(meta, source_fields)
        print(f"{mapping_name}: {source_fields} → {value}")

if __name__ == "__main__":
    debug_config_and_extraction()

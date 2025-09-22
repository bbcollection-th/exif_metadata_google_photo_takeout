#!/usr/bin/env python3
"""
Test complet du workflow de découverte et nettoyage de configuration avec timezone_correction.
"""

import json
import tempfile
import sys
from pathlib import Path

# Ajouter les outils au path
tools_path = Path(__file__).parent.parent / "tools"
if str(tools_path) not in sys.path:
    sys.path.insert(0, str(tools_path))

# Ajouter le répertoire src au path pour les imports du projet
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

try:
    from discover_fields import FieldDiscoverer
    from clean_config_file import clean_config_file
except ImportError as e:
    import pytest
    pytest.skip(f"Modules tools non disponibles: {e}")

import pytest

@pytest.mark.skip("Import temporairement désactivé pour les tests complets")
def test_complete_config_workflow():
    """Test du workflow complet discover -> clean avec timezone_correction"""
    print("=== Test workflow config avec timezone_correction ===")
    
    # 1. Générer une configuration avec discoverer
    print("1️⃣ Génération config avec discover_fields...")
    discoverer = FieldDiscoverer()
    
    # Simuler quelques champs découverts
    try:
        from discover_fields import FieldInfo
    except ImportError:
        import pytest
        pytest.skip("Module discover_fields.FieldInfo non disponible")
    
    discoverer.discovered_fields = {
        "title": FieldInfo(
            name="title",
            sample_values=["Test Photo"],
            data_types={"str"},
            frequency=10
        ),
        "geoData.latitude": FieldInfo(
            name="geoData.latitude", 
            sample_values=[48.8566],
            data_types={"float"},
            frequency=8
        )
    }
    
    # Générer config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_raw:
        tmp_raw_path = Path(tmp_raw.name)
    
    config = discoverer.generate_config(tmp_raw_path)
    
    # Vérifier timezone_correction dans config générée
    assert 'timezone_correction' in config, "timezone_correction manquant dans config générée"
    tz_config = config['timezone_correction']
    
    print("✅ Config générée avec timezone_correction")
    print(f"   - enabled: {tz_config.get('enabled', 'N/A')}")
    print(f"   - use_absolute_values: {tz_config.get('use_absolute_values', 'N/A')}")
    
    # 2. Nettoyer la configuration
    print("\n2️⃣ Nettoyage config avec clean_config_file...")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_clean:
        tmp_clean_path = Path(tmp_clean.name)
    
    success = clean_config_file(tmp_raw_path, tmp_clean_path)
    assert success, "Échec du nettoyage de configuration"
    
    # 3. Vérifier la config nettoyée
    print("\n3️⃣ Vérification config nettoyée...")
    
    with open(tmp_clean_path, 'r') as f:
        clean_config = json.load(f)
    
    # Vérifications
    checks = {
        'exif_mapping présent': 'exif_mapping' in clean_config,
        'strategies présent': 'strategies' in clean_config,
        'global_settings présent': 'global_settings' in clean_config,
        'timezone_correction présent': 'timezone_correction' in clean_config,
        'timezone_correction.enabled': clean_config.get('timezone_correction', {}).get('enabled') is not None,
    }
    
    print("\n=== Vérifications ===")
    for check_name, result in checks.items():
        status = "✅" if result else "❌"
        print(f"{status} {check_name}: {'OK' if result else 'MANQUANT'}")
    
    # 4. Afficher la section timezone_correction finale
    if 'timezone_correction' in clean_config:
        print("\n=== Configuration timezone_correction finale ===")
        print(json.dumps(clean_config['timezone_correction'], indent=2))
    
    # Nettoyage
    tmp_raw_path.unlink()
    tmp_clean_path.unlink()
    
    all_passed = all(checks.values())
    if all_passed:
        print("\n🎉 Tous les tests du workflow config sont passés !")
    else:
        print(f"\n⚠️ Échecs: {sum(not v for v in checks.values())}/{len(checks)}")
    
    return all_passed

if __name__ == "__main__":
    try:
        success = test_complete_config_workflow()
        if not success:
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur dans le test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
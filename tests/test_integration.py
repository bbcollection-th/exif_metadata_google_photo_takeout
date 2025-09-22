
"""Tests d'intégration qui exécutent réellement exiftool et vérifient que les métadonnées sont écrites correctement."""
from pathlib import Path
import json
import subprocess
import pytest
from google_takeout_metadata.processor import process_sidecar_file
from google_takeout_metadata.config_loader import ConfigLoader
from google_takeout_metadata.exif_writer import _run_exiftool_command, write_metadata
from google_takeout_metadata.sidecar import SidecarData

from test_asset_manager import test_asset_manager

def _copy_test_asset(asset_name: str, dest_path: Path) -> None:
    """
    Fonction de compatibilité qui utilise le nouveau gestionnaire d'assets.
    Copie un asset de test propre vers le chemin de destination.
    """
    # S'assurer que l'asset source est propre
    test_asset_manager.ensure_clean_asset(asset_name)
    
    # Copier vers l'environnement de test  
    test_asset_manager.copy_clean_asset(asset_name, dest_path)
    
    # Vérifier que la copie est propre
    if not test_asset_manager.verify_asset_is_clean(dest_path):
        raise AssertionError(f"Asset copié {dest_path} n'est pas propre")

def _create_clean_test_environment(temp_dir: Path, asset_name: str = "test_clean.jpg") -> Path:
    """
    Crée un environnement de test propre avec l'asset spécifié.
    Vérifie que l'asset est vraiment propre avant de le copier.
    """
    dest_path = temp_dir / asset_name  
    _copy_test_asset(asset_name, dest_path)
    return dest_path

def _run_exiftool_read(media_path: Path) -> dict:
    """Exécuter exiftool pour lire les métadonnées depuis un fichier image."""
    cmd = [
        "exiftool", 
        "-json",
        "-charset", "utf8",
        "-MWG:Description",
        "-IPTC:ObjectName",
        "-XMP-iptcExt:PersonInImage",
        "-XMP:Rating",  # Pour favorited
        "-GPS:GPSLatitude",  # Pour GPS tests
        "-GPS:GPSLongitude",
        "-GPS:GPSLatitudeRef",
        "-GPS:GPSLongitudeRef",
        str(media_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        data = json.loads(result.stdout)
        metadata = data[0] if data else {}
        
        # Normaliser PersonInImage : toujours retourner une liste
        # ExifTool retourne une chaîne pour 1 élément, une liste pour plusieurs éléments
        if "PersonInImage" in metadata:
            person_value = metadata["PersonInImage"]
            if isinstance(person_value, str):
                metadata["PersonInImage"] = [person_value]
        
        return metadata
    except FileNotFoundError:
        pytest.skip("exiftool introuvable - skipping integration tests")
    except subprocess.CalledProcessError as e:
        pytest.fail(f"exiftool failed: {e.stderr}")

@pytest.mark.integration
def test_realistic_workflow_with_default_strategies(tmp_path: Path) -> None:
    """
    Teste un workflow réaliste avec les stratégies par défaut de la configuration :
    - description: write_if_blank_or_missing
    - people_name: clean_duplicates 
    - favorited: preserve_positive_rating
    """
    media_path = tmp_path / "test.jpg"
    _copy_test_asset("test_clean.jpg", media_path)

    # Étape 1: Traiter un premier sidecar avec des métadonnées initiales
    sidecar_data_1 = {
        "title": "test.jpg",
        "description": "First Description",
        "people": [{"name": "Person A"}],
        "favorited": True
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data_1), encoding="utf-8")
    process_sidecar_file(json_path)

    # Vérifier l'état après première écriture
    metadata_1 = _run_exiftool_read(media_path)
    assert metadata_1.get("Description") == "First Description"
    assert "Person A" in metadata_1.get("PersonInImage", [])
    assert metadata_1.get("Rating") == 5  # favorited=true

    # Étape 2: Traiter un deuxième sidecar avec nouvelles données
    sidecar_data_2 = {
        "title": "test.jpg", 
        "description": "Second Description (should be ignored)",
        "people": [{"name": "Person A"}, {"name": "Person B"}],  # Person A en doublon
        "favorited": True  # Rating déjà à 5, devrait être préservé
    }
    json_path.write_text(json.dumps(sidecar_data_2), encoding="utf-8")
    process_sidecar_file(json_path)

    # Vérifier le résultat final avec les stratégies par défaut
    final_metadata = _run_exiftool_read(media_path)
    
    # Description préservée (write_if_blank_or_missing sur champ non vide)
    assert final_metadata.get("Description") == "First Description"
    
    # Personnes déduplicées et ajoutées (clean_duplicates)
    final_people = final_metadata.get("PersonInImage", [])
    assert set(final_people) == {"Person A", "Person B"}
    
    # Rating préservé à 5 (preserve_positive_rating)
    assert final_metadata.get("Rating") == 5

@pytest.mark.integration
def test_integration_end_to_end_workflow(tmp_path: Path) -> None:
    """
    Test d'intégration complet simulant un workflow réel de traitement
    de photos Google Takeout avec différents types de métadonnées.
    """
    media_path = tmp_path / "photo.jpg"
    _copy_test_asset("test_clean.jpg", media_path)

    # Simuler un sidecar Google Takeout complet
    full_sidecar_data = {
        "title": "photo.jpg",
        "description": "Family vacation photo",
        "geoData": {
            "latitude": 45.5017, 
            "longitude": -73.5673,
            "altitude": 50.0
        },
        "people": [
            {"name": "John Doe"},
            {"name": "jane smith"}  # Test normalisation
        ],
        "albums": ["Summer 2024", "family photos"],
        "favorited": True,
        "creationTime": {"timestamp": 1609459200}  # 2021-01-01 00:00:00 UTC
    }
    
    json_path = tmp_path / "photo.jpg.json"
    json_path.write_text(json.dumps(full_sidecar_data), encoding="utf-8")
    process_sidecar_file(json_path)

    # Vérifier tous les types de métadonnées
    metadata = _run_exiftool_read(media_path)
    
    # Texte et personnes
    assert metadata.get("Description") == "Family vacation photo"
    people = metadata.get("PersonInImage", [])
    assert "John Doe" in people
    assert "Jane Smith" in people  # Normalisation majuscule
    
    # GPS
    assert "45 deg" in str(metadata.get("GPSLatitude", ""))
    assert "73 deg" in str(metadata.get("GPSLongitude", ""))
    
    # Rating
    assert metadata.get("Rating") == 5

# Conserver les autres tests d'intégration qui sont toujours pertinents
# (ceux qui testent des fonctionnalités spécifiques comme le GPS, les favoris, etc.)
@pytest.mark.integration
def test_write_and_read_gps(tmp_path: Path) -> None:
    media_path = tmp_path / "test.jpg"
    _copy_test_asset("test_clean.jpg", media_path)
    sidecar_data = {
        "title": "test.jpg",
        "geoData": {"latitude": 48.8566, "longitude": 2.3522, "altitude": 35.0}
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    process_sidecar_file(json_path)
    metadata = _run_exiftool_read(media_path)
    assert "48 deg" in str(metadata.get("GPSLatitude"))
    assert "2 deg" in str(metadata.get("GPSLongitude"))

@pytest.mark.integration
def test_write_and_read_favorited(tmp_path: Path) -> None:
    media_path = tmp_path / "test.jpg"
    _copy_test_asset("test_clean.jpg", media_path)
    sidecar_data = {"title": "test.jpg", "favorited": True}
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    process_sidecar_file(json_path)
    metadata = _run_exiftool_read(media_path)
    assert int(metadata.get("Rating", 0)) == 5

# === TESTS SPÉCIFIQUES PAR STRATÉGIE ===

@pytest.mark.integration
def test_preserve_existing_strategy_pure(tmp_path: Path) -> None:
    """Teste uniquement la stratégie preserve_existing."""
    media_path = tmp_path / "test.jpg"
    _copy_test_asset("test_clean.jpg", media_path)

    # Étape 1: Écrire une description initiale
    initial_meta = SidecarData(title="test.jpg", description="Initial Description")
    
    config_loader = ConfigLoader()
    config_loader.load_config()
    config_loader.config['exif_mapping']['description']['default_strategy'] = 'replace_all'
    
    write_metadata(media_path, initial_meta, config_loader=config_loader)
    
    # Vérifier l'état initial
    metadata_after_init = _run_exiftool_read(media_path)
    assert metadata_after_init.get("Description") == "Initial Description"

    # Étape 2: Essayer d'écrire avec preserve_existing
    new_meta = SidecarData(title="test.jpg", description="New Description")
    
    config_loader.config['exif_mapping']['description']['default_strategy'] = 'preserve_existing'
    write_metadata(media_path, new_meta, config_loader=config_loader)

    # Vérifier que la description n'a PAS changé (preserve_existing)
    final_metadata = _run_exiftool_read(media_path)
    assert final_metadata.get("Description") == "Initial Description"

@pytest.mark.integration  
def test_write_if_missing_strategy_pure(tmp_path: Path) -> None:
    """Teste uniquement la stratégie write_if_missing."""
    media_path = tmp_path / "test.jpg"
    _copy_test_asset("test_clean.jpg", media_path)

    # Étape 1: Écrire avec write_if_missing sur image vierge
    meta1 = SidecarData(title="test.jpg", description="First Description")
    
    config_loader = ConfigLoader()
    config_loader.load_config()
    config_loader.config['exif_mapping']['description']['default_strategy'] = 'write_if_missing'

    write_metadata(media_path, meta1, use_localTime=False, config_loader=config_loader)

    # Vérifier que l'écriture a réussi
    metadata_after_first = _run_exiftool_read(media_path)
    assert metadata_after_first.get("Description") == "First Description"

    # Étape 2: Essayer d'écrire à nouveau avec write_if_missing
    meta2 = SidecarData(title="test.jpg", description="Second Description")
    write_metadata(media_path, meta2, use_localTime=False, config_loader=config_loader)

    # Vérifier que la description n'a PAS changé (write_if_missing sur champ existant)
    final_metadata = _run_exiftool_read(media_path)
    assert final_metadata.get("Description") == "First Description"

@pytest.mark.integration
def test_write_if_blank_or_missing_strategy_pure(tmp_path: Path) -> None:
    """Teste uniquement la stratégie write_if_blank_or_missing."""
    media_path = tmp_path / "test.jpg"
    _copy_test_asset("test_clean.jpg", media_path)

    # Étape 1: Écrire avec write_if_blank_or_missing sur image vierge
    meta1 = SidecarData(title="test.jpg", description="First Description")
    
    config_loader = ConfigLoader()
    config_loader.load_config()
    config_loader.config['exif_mapping']['description']['default_strategy'] = 'write_if_blank_or_missing'

    write_metadata(media_path, meta1, use_localTime=False, config_loader=config_loader)

    # Vérifier que l'écriture a réussi
    metadata_after_first = _run_exiftool_read(media_path)
    assert metadata_after_first.get("Description") == "First Description"

    # Étape 2: Essayer d'écrire à nouveau avec write_if_blank_or_missing
    meta2 = SidecarData(title="test.jpg", description="Second Description")
    write_metadata(media_path, meta2, use_localTime=False, config_loader=config_loader)

    # Vérifier que la description n'a PAS changé (write_if_blank_or_missing sur champ non vide)
    final_metadata = _run_exiftool_read(media_path)
    assert final_metadata.get("Description") == "First Description"

@pytest.mark.integration
def test_replace_all_strategy_pure(tmp_path: Path) -> None:
    """Teste uniquement la stratégie replace_all."""
    media_path = tmp_path / "test.jpg"
    _copy_test_asset("test_clean.jpg", media_path)

    # Étape 1: Écrire une description initiale
    initial_meta = SidecarData(title="test.jpg", description="Initial Description")
    
    config_loader = ConfigLoader()
    config_loader.load_config()
    config_loader.config['exif_mapping']['description']['default_strategy'] = 'replace_all'

    write_metadata(media_path, initial_meta, use_localTime=False, config_loader=config_loader)

    # Vérifier l'état initial
    metadata_after_init = _run_exiftool_read(media_path)
    assert metadata_after_init.get("Description") == "Initial Description"

    # Étape 2: Remplacer avec replace_all
    new_meta = SidecarData(title="test.jpg", description="Replaced Description")
    write_metadata(media_path, new_meta, use_localTime=False, config_loader=config_loader)

    # Vérifier que la description A changé (replace_all)
    final_metadata = _run_exiftool_read(media_path)
    assert final_metadata.get("Description") == "Replaced Description"

@pytest.mark.integration
def test_clean_duplicates_strategy_pure(tmp_path: Path) -> None:
    """Teste uniquement la stratégie clean_duplicates pour les personnes."""
    media_path = tmp_path / "test.jpg"
    _copy_test_asset("test_clean.jpg", media_path)

    # Étape 1: Ajouter des personnes initiales
    initial_meta = SidecarData(title="test.jpg", people_name=["Person A", "Person B"])
    
    config_loader = ConfigLoader()
    config_loader.load_config()
    config_loader.config['exif_mapping']['people_name']['default_strategy'] = 'clean_duplicates'

    write_metadata(media_path, initial_meta, use_localTime=False, config_loader=config_loader)

    # Vérifier l'état initial
    metadata_after_init = _run_exiftool_read(media_path)
    initial_people = metadata_after_init.get("PersonInImage", [])
    assert set(initial_people) == {"Person A", "Person B"}

    # Étape 2: Ajouter avec clean_duplicates (inclut un doublon)
    new_meta = SidecarData(title="test.jpg", people_name=["Person B", "Person C"])  # Person B en doublon
    write_metadata(media_path, new_meta, use_localTime=False, config_loader=config_loader)

    # Vérifier que les personnes sont bien déduplicées et ajoutées
    final_metadata = _run_exiftool_read(media_path)
    final_people = final_metadata.get("PersonInImage", [])
    assert set(final_people) == {"Person A", "Person B", "Person C"}  # Person B pas dupliquée

@pytest.mark.integration
def test_preserve_positive_rating_strategy_pure(tmp_path: Path) -> None:
    """Teste uniquement la stratégie preserve_positive_rating pour favorited/Rating."""
    media_path = tmp_path / "test.jpg"
    _copy_test_asset("test_clean.jpg", media_path)

    config_loader = ConfigLoader()
    config_loader.load_config()
    # Vérifier que favorited utilise bien preserve_positive_rating
    assert config_loader.config['exif_mapping']['favorited']['default_strategy'] == 'preserve_positive_rating'

    # Test 1: favorited=true sur image vierge → doit créer Rating=5
    # Utiliser un titre unique pour éviter les conflits avec d'autres tests
    meta1 = SidecarData(title="test_rating.jpg", favorited=True)
    write_metadata(media_path, meta1, use_localTime=False, config_loader=config_loader)
    
    metadata_after_1 = _run_exiftool_read(media_path)
    # Note: ExifTool lit Rating comme entier
    assert metadata_after_1.get("Rating") == 5

    # Test 2: favorited=true à nouveau → doit préserver Rating=5 (pas de changement)
    meta2 = SidecarData(title="test_rating.jpg", favorited=True)
    write_metadata(media_path, meta2, use_localTime=False, config_loader=config_loader)
    
    metadata_after_2 = _run_exiftool_read(media_path)
    assert metadata_after_2.get("Rating") == 5  # Preserved

    # Test 3: Simuler Rating=0 puis favorited=true → doit changer à Rating=5
    # D'abord forcer Rating=0
    _run_exiftool_command(media_path, ["-XMP:Rating=0"])
    metadata_check = _run_exiftool_read(media_path)
    assert metadata_check.get("Rating") == 0
    
    # Puis favorited=true → doit changer à 5
    meta3 = SidecarData(title="test_rating.jpg", favorited=True)
    write_metadata(media_path, meta3, use_localTime=False, config_loader=config_loader)
    
    metadata_after_3 = _run_exiftool_read(media_path)
    assert metadata_after_3.get("Rating") == 5  # Changed from 0 to 5

    # Test 4: favorited=false → ne doit jamais toucher à Rating
    meta4 = SidecarData(title="test_rating.jpg", favorited=False)
    write_metadata(media_path, meta4, use_localTime=False, config_loader=config_loader)
    
    final_metadata = _run_exiftool_read(media_path)
    assert final_metadata.get("Rating") == 5  # Still 5, unchanged

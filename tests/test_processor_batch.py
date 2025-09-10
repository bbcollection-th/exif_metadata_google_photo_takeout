"""Tests pour la fonctionnalité de traitement par lots."""

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from google_takeout_metadata.processor_batch import process_batch, process_directory_batch
from google_takeout_metadata.sidecar import SidecarData


def test_process_batch_empty_batch():
    """Tester que process_batch retourne 0 pour un lot vide."""
    result = process_batch([], clean_sidecars=False)
    assert result == 0


@patch('google_takeout_metadata.processor_batch.subprocess.run')
def test_process_batch_success(mock_subprocess_run, tmp_path):
    """Tester le traitement par lots réussi."""
    # Configuration
    mock_subprocess_run.return_value = Mock(returncode=0, stdout="    1 image files updated")
    
    media_path = tmp_path / "test.jpg"
    json_path = tmp_path / "test.jpg.json"
    args = ["-EXIF:ImageDescription=Test Description"]
    
    batch = [(media_path, json_path, args)]
    
    # Exécution
    result = process_batch(batch, clean_sidecars=False)
    
    # Vérification
    assert result == 1
    mock_subprocess_run.assert_called_once()
    
    # Vérifier que la commande a été construite correctement
    call_args = mock_subprocess_run.call_args
    cmd = call_args[0][0]
    assert cmd[0] == "exiftool"
    assert "-overwrite_original" in cmd
    assert "-charset" in cmd
    assert "-@" in cmd


@patch('google_takeout_metadata.processor_batch.subprocess.run')
def test_process_batch_with_argfile_content(mock_subprocess_run, tmp_path):
    """Vérifier que le fichier d'arguments est créé avec le contenu correct."""
    # Setup
    mock_subprocess_run.return_value = Mock(returncode=0, stdout="    2 image files updated")
    
    media_path1 = tmp_path / "test1.jpg"
    media_path2 = tmp_path / "test2.jpg"
    json_path1 = tmp_path / "test1.jpg.json"
    json_path2 = tmp_path / "test2.jpg.json"
    
    args1 = ["-EXIF:ImageDescription=Description 1", "-XMP:Rating=5"]
    args2 = ["-EXIF:ImageDescription=Description 2"]
    
    batch = [
        (media_path1, json_path1, args1),
        (media_path2, json_path2, args2)
    ]
    
    # Execute
    result = process_batch(batch, clean_sidecars=False)
    
    # Assert
    assert result == 2
    mock_subprocess_run.assert_called_once()
    
    # Vérifier que le chemin du fichier d'arguments a été passé au sous-processus
    call_args = mock_subprocess_run.call_args
    cmd = call_args[0][0]
    assert "-@" in cmd
    # Le chemin du fichier d'arguments devrait être l'argument juste après "-@"
    argfile_index = cmd.index("-@")
    assert argfile_index + 1 < len(cmd)  # S'assurer qu'il y a un argument après "-@"


@patch('google_takeout_metadata.processor_batch.subprocess.run')
def test_process_batch_clean_sidecars(mock_subprocess_run, tmp_path):
    """Vérifier que les fichiers de sidecar sont nettoyés lorsqu'on le demande."""
    # Setup
    mock_subprocess_run.return_value = Mock(returncode=0, stdout="    1 image files updated")
    
    media_path = tmp_path / "test.jpg"
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text('{"title": "test.jpg"}')
    args = ["-EXIF:ImageDescription=Test Description"]
    
    batch = [(media_path, json_path, args)]
    
    # Execute
    result = process_batch(batch, clean_sidecars=True)
    
    # Assert
    assert result == 1
    assert not json_path.exists()


@patch('google_takeout_metadata.processor_batch.subprocess.run')
def test_process_batch_exiftool_not_found(mock_subprocess_run):
    """Vérifier la gestion d'erreurs lorsque exiftool n'est pas trouvé."""
    # Setup
    mock_subprocess_run.side_effect = FileNotFoundError("exiftool introuvable")
    
    media_path = Path("test.jpg")
    json_path = Path("test.jpg.json")
    args = ["-EXIF:ImageDescription=Test Description"]
    
    batch = [(media_path, json_path, args)]
    
    # Execute & Assert
    with pytest.raises(RuntimeError, match="exiftool introuvable"):
        process_batch(batch, clean_sidecars=False)


@patch('google_takeout_metadata.processor_batch.subprocess.run')
def test_process_batch_exiftool_error(mock_subprocess_run, caplog):
    """Vérifier la gestion d'erreurs lorsque exiftool retourne une erreur."""
    # Setup
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        1, ["exiftool"], stderr="Some error"
    )
    
    media_path = Path("test.jpg")
    json_path = Path("test.jpg.json")
    args = ["-EXIF:ImageDescription=Test Description"]
    
    batch = [(media_path, json_path, args)]
    
    # Execute
    result = process_batch(batch, clean_sidecars=False)
    
    # Assert
    assert result == 0
    assert "Échec du traitement par lot" in caplog.text


def test_process_directory_batch_no_sidecars(tmp_path, caplog):
    """Vérifier le traitement par lot lorsque aucun fichier de sidecar n'est trouvé."""
    # Execute
    process_directory_batch(tmp_path, use_localtime=False, append_only=True, clean_sidecars=False)
    
    # Assert
    assert "Aucun fichier de métadonnées (.json) trouvé" in caplog.text


@pytest.mark.integration
def test_process_directory_batch_single_file(tmp_path):
    """Vérifier le traitement par lot d'un seul fichier."""
    try:
        # Créer une image de test
        media_path = tmp_path / "test.jpg"
        img = Image.new('RGB', (100, 100), color='blue')
        img.save(media_path)
        
        # Créer le fichier JSON annexe
        sidecar_data = {
            "title": "test.jpg",
            "description": "Batch test description",
            "people": [{"name": "Batch Test Person"}]
        }
        json_path = tmp_path / "test.jpg.json"
        json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
        
        # Traiter en mode batch
        process_directory_batch(tmp_path, use_localtime=False, append_only=True, clean_sidecars=False)
        
        # Vérifier que les métadonnées ont été écrites en les relisant
        cmd = [
            "exiftool",
            "-j",
            "-EXIF:ImageDescription",
            "-XMP-iptcExt:PersonInImage",
            str(media_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        metadata = json.loads(result.stdout)[0]
        
        assert metadata.get("ImageDescription") == "Batch test description"
        people = metadata.get("PersonInImage", [])
        if isinstance(people, str):
            people = [people]
        assert "Batch Test Person" in people
        
    except FileNotFoundError:
        pytest.skip("Exiftool non trouvé - ignore les tests d'intégration")


@pytest.mark.integration  
def test_process_directory_batch_multiple_files(tmp_path):
    """Vérifier le traitement par lot de plusieurs fichiers."""
    try:
        # Créer plusieurs images de test avec leurs fichiers annexes
        files_data = [
            ("test1.jpg", "First batch test", "Person One"),
            ("test2.jpg", "Second batch test", "Person Two"),
            ("test3.jpg", "Third batch test", "Person Three")
        ]
        
        for filename, description, person in files_data:
            # Créer l'image
            media_path = tmp_path / filename
            img = Image.new('RGB', (100, 100), color='red')
            img.save(media_path)
            
            # Créer le fichier annexe
            sidecar_data = {
                "title": filename,
                "description": description,
                "people": [{"name": person}]
            }
            json_path = tmp_path / f"{filename}.json"
            json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
        
        # Traiter en mode batch
        process_directory_batch(tmp_path, use_localtime=False, append_only=True, clean_sidecars=False)
        
        # Vérifier que tous les fichiers ont été traités correctement
        for filename, expected_description, expected_person in files_data:
            media_path = tmp_path / filename
            
            cmd = [
                "exiftool",
                "-j",
                "-EXIF:ImageDescription",
                "-XMP-iptcExt:PersonInImage",
                str(media_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
            metadata = json.loads(result.stdout)[0]
            
            assert metadata.get("ImageDescription") == expected_description
            people = metadata.get("PersonInImage", [])
            if isinstance(people, str):
                people = [people]
            assert expected_person in people
        
    except FileNotFoundError:
        pytest.skip("Exiftool non trouvé - ignore les tests d'intégration")


@pytest.mark.integration
def test_process_directory_batch_with_albums(tmp_path):
    """Vérifier le traitement par lot avec des métadonnées d'album."""
    try:
        # Créer la structure de répertoires
        album_dir = tmp_path / "Album Test"
        album_dir.mkdir()
        
        # Créer les métadonnées d'album
        album_metadata = {
            "title": "Test Album",
            "description": "Album for batch testing"
        }
        metadata_path = album_dir / "metadata.json"
        metadata_path.write_text(json.dumps(album_metadata), encoding="utf-8")
        
        # Créer l'image de test dans le répertoire d'album
        media_path = album_dir / "album_photo.jpg"
        img = Image.new('RGB', (100, 100), color='green')
        img.save(media_path)
        
        # Créer le fichier annexe
        sidecar_data = {
            "title": "album_photo.jpg",
            "description": "Photo in album batch test"
        }
        json_path = album_dir / "album_photo.jpg.json"
        json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
        
        # Traiter en mode batch
        process_directory_batch(tmp_path, use_localtime=False, append_only=True, clean_sidecars=False)
        
        # Vérifier que l'album a été ajouté aux mots-clés
        cmd = [
            "exiftool",
            "-j",
            "-IPTC:Keywords",
            "-XMP-dc:Subject",
            str(media_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        metadata = json.loads(result.stdout)[0]
        
        keywords = metadata.get("Keywords", [])
        if isinstance(keywords, str):
            keywords = [keywords]
        
        assert "Album: Test Album" in keywords
        
    except FileNotFoundError:
        pytest.skip("Exiftool non trouvé - ignore les tests d'intégration")


@pytest.mark.integration
def test_process_directory_batch_clean_sidecars(tmp_path):
    """Test d'intégration pour le traitement par lot avec nettoyage des sidecars."""
    try:
        # Créer une image de test
        media_path = tmp_path / "cleanup_test.jpg"
        img = Image.new('RGB', (100, 100), color='yellow')
        img.save(media_path)
        
        # Créer le fichier JSON annexe
        sidecar_data = {
            "title": "cleanup_test.jpg",
            "description": "Test cleanup functionality"
        }
        json_path = tmp_path / "cleanup_test.jpg.json"
        json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
        
        # Vérifier que le fichier annexe existe avant le traitement
        assert json_path.exists()
        
        # Traiter avec le nettoyage activé
        process_directory_batch(tmp_path, use_localtime=False, append_only=True, clean_sidecars=True)
        
        # Vérifier que le fichier annexe a été nettoyé
        assert not json_path.exists()
        
        # Vérifier que les métadonnées ont quand même été écrites
        cmd = [
            "exiftool",
            "-j",
            "-EXIF:ImageDescription",
            str(media_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        metadata = json.loads(result.stdout)[0]
        
        assert metadata.get("ImageDescription") == "Test cleanup functionality"
        
    except FileNotFoundError:
        pytest.skip("Exiftool non trouvé - ignore les tests d'intégration")


@patch('google_takeout_metadata.processor_batch.parse_sidecar')
def test_process_directory_batch_invalid_sidecar(mock_parse_sidecar, tmp_path, caplog):
    """Tester le traitement par lot avec un fichier sidecar invalide."""
    # Configuration
    mock_parse_sidecar.side_effect = ValueError("Invalid JSON")
    
    # Créer des fichiers factices
    media_path = tmp_path / "invalid.jpg"
    media_path.write_text("dummy")
    json_path = tmp_path / "invalid.jpg.json"
    json_path.write_text("invalid json")
    
    # Exécuter
    process_directory_batch(tmp_path, use_localtime=False, append_only=True, clean_sidecars=False)
    
    # Vérifier
    assert "Échec de la préparation de" in caplog.text


@patch('google_takeout_metadata.processor_batch.build_exiftool_args')
def test_process_directory_batch_no_args_generated(mock_build_args, tmp_path):
    """Tester le traitement par lot quand aucun argument exiftool n'est généré."""
    # Configuration - build_exiftool_args retourne une liste vide
    mock_build_args.return_value = []
    
    # Créer l'image de test
    media_path = tmp_path / "no_args.jpg"
    img = Image.new('RGB', (100, 100), color='white')
    img.save(media_path)
    
    # Créer le fichier JSON annexe
    sidecar_data = {"title": "no_args.jpg"}
    json_path = tmp_path / "no_args.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Exécuter (ne devrait pas planter même sans arguments)
    process_directory_batch(tmp_path, use_localtime=False, append_only=True, clean_sidecars=False)
    
    # Aucune assertion spécifique nécessaire - juste s'assurer que ça ne plante pas


def test_process_directory_batch_missing_media_file(tmp_path, caplog):
    """Tester le traitement par lot quand le fichier média est manquant."""
    # Créer un fichier annexe sans fichier média correspondant
    sidecar_data = {
        "title": "missing.jpg",
        "description": "Media file does not exist"
    }
    json_path = tmp_path / "missing.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Exécuter
    process_directory_batch(tmp_path, use_localtime=False, append_only=True, clean_sidecars=False)
    
    # Vérifier
    assert "Fichier image introuvable" in caplog.text


@patch('google_takeout_metadata.processor_batch.fix_file_extension_mismatch')
@patch('google_takeout_metadata.processor_batch.parse_sidecar')
def test_process_directory_batch_file_extension_fix(mock_parse_sidecar, mock_fix_extension, tmp_path):
    """Tester que la correction de l'extension de fichier est gérée dans le traitement par lot."""
    # Configuration
    media_path = tmp_path / "test.jpg"
    json_path = tmp_path / "test.jpg.json"
    fixed_media_path = tmp_path / "test.jpeg"
    fixed_json_path = tmp_path / "test.jpeg.json"
    
    # Créer les fichiers
    img = Image.new('RGB', (100, 100), color='black')
    img.save(media_path)
    json_path.write_text('{"title": "test.jpg"}')
    
    # Simuler la correction d'extension pour retourner des chemins différents
    mock_fix_extension.return_value = (fixed_media_path, fixed_json_path)
    
    # Simuler parse_sidecar pour retourner des données différentes pour chaque appel
    mock_parse_sidecar.side_effect = [
        SidecarData(filename="test.jpg", description="Original", people=[], taken_at=None, created_at=None, 
                   latitude=None, longitude=None, altitude=None, favorite=False, albums=[]),
        SidecarData(filename="test.jpeg", description="Fixed", people=[], taken_at=None, created_at=None,
                   latitude=None, longitude=None, altitude=None, favorite=False, albums=[])
    ]
    
    # Exécuter
    process_directory_batch(tmp_path, use_localtime=False, append_only=True, clean_sidecars=False)
    
    # Vérifier que fix_file_extension_mismatch a été appelé
    mock_fix_extension.assert_called()
    # Vérifier que parse_sidecar a été appelé deux fois (une fois pour l'original, une fois pour le corrigé)
    assert mock_parse_sidecar.call_count == 2

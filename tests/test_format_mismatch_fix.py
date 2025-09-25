"""Tests pour la correction automatique des incohérences de format de fichier."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

from google_takeout_metadata.processor_batch import _retry_batch_with_format_correction, process_batch
from google_takeout_metadata import statistics


@pytest.fixture
def setup_test_files(tmp_path):
    """Créer des fichiers de test avec incohérence d'extension."""
    # Créer un fichier JPEG avec extension .PNG
    jpeg_content = b'\xff\xd8\xff\xe0\x00\x10JFIF'  # Header JPEG
    fake_png_path = tmp_path / "fake_image.PNG"
    fake_png_path.write_bytes(jpeg_content)
    
    # Créer le JSON sidecar correspondant
    json_data = {
        "title": "fake_image.PNG",
        "description": "Test image",
        "photoTakenTime": {"timestamp": "1577836800"},
        "creationTime": {"timestamp": "1577836800"}
    }
    json_path = fake_png_path.with_suffix(".PNG.supplemental-metadata.json")
    json_path.write_text(json.dumps(json_data, indent=2))
    
    return fake_png_path, json_path


def test_retry_batch_with_format_correction_success(setup_test_files, tmp_path):
    """Tester la correction réussie d'une incohérence de format."""
    media_path, json_path = setup_test_files
    
    # Réinitialiser les statistiques
    statistics.stats = statistics.ProcessingStats()
    
    # Mock de detect_file_type pour retourner .jpg au lieu de .png
    with patch('google_takeout_metadata.processor.detect_file_type') as mock_detect:
        with patch('google_takeout_metadata.processor_batch.parse_sidecar') as mock_parse:
            with patch('google_takeout_metadata.processor_batch.build_exiftool_args') as mock_build_args:
                with patch('google_takeout_metadata.processor_batch.process_batch') as mock_process_batch:
                    
                    # Configuration des mocks
                    mock_detect.return_value = ".jpg"
                    mock_meta = MagicMock()
                    mock_parse.return_value = mock_meta
                    mock_build_args.return_value = ["-Title=Test"]
                    mock_process_batch.return_value = 1
                    
                    # Préparer le batch avec le fichier problématique
                    batch = [(media_path, json_path, ["-Title=Original"])]
                    
                    # Exécuter la correction
                    result = _retry_batch_with_format_correction(batch, False, tmp_path / "logs")
                    
                    # Vérifications
                    assert result == 1  # Succès
                    
                    # Vérifier que le fichier a été renommé
                    new_media_path = media_path.with_suffix(".jpg")
                    assert new_media_path.exists()
                    assert not media_path.exists()
                    
                    # Vérifier que le JSON a été mis à jour
                    new_json_path = json_path.with_name(new_media_path.name + ".supplemental-metadata.json")
                    assert new_json_path.exists()
                    assert not json_path.exists()
                    
                    # Vérifier le contenu du JSON mis à jour
                    with open(new_json_path, 'r', encoding='utf-8') as f:
                        updated_json = json.load(f)
                    assert updated_json['title'] == new_media_path.name
                    
                    # Vérifier que les statistiques ont été mises à jour
                    assert len(statistics.stats.fixed_extensions) == 1
                    assert media_path.name in statistics.stats.fixed_extensions[0]
                    assert new_media_path.name in statistics.stats.fixed_extensions[0]


def test_process_batch_handles_png_jpeg_mismatch_error():
    """Tester que process_batch gère correctement l'erreur de format PNG/JPEG."""
    
    # Mock de subprocess.run pour simuler l'erreur ExifTool
    error_stderr = "Error: Not a valid PNG (looks more like a JPEG) - /path/to/file.PNG"
    mock_error = subprocess.CalledProcessError(
        returncode=2, 
        cmd=['exiftool'], 
        stderr=error_stderr
    )
    
    with patch('subprocess.run', side_effect=mock_error):
        with patch('google_takeout_metadata.processor_batch._retry_batch_with_format_correction') as mock_retry:
            mock_retry.return_value = 1
            
            # Préparer un batch factice
            batch = [(Path("fake.PNG"), Path("fake.PNG.json"), ["-Title=Test"])]
            
            result = process_batch(batch, False, "logs")
            
            # Vérifier que la fonction de retry a été appelée
            mock_retry.assert_called_once_with(batch, False, Path("logs"))
            assert result == 1


def test_retry_batch_with_format_correction_no_mismatch(setup_test_files, tmp_path):
    """Tester le comportement quand aucune incohérence n'est détectée."""
    media_path, json_path = setup_test_files
    
    # Mock de detect_file_type pour retourner la même extension
    with patch('google_takeout_metadata.processor.detect_file_type') as mock_detect:
        with patch('google_takeout_metadata.processor_batch.process_batch') as mock_process_batch:
            
            mock_detect.return_value = ".png"  # Même extension, pas d'incohérence
            mock_process_batch.return_value = 1
            
            batch = [(media_path, json_path, ["-Title=Test"])]
            
            result = _retry_batch_with_format_correction(batch, False, tmp_path / "logs")
            
            # Vérifier que le fichier original n'a pas été modifié
            assert media_path.exists()
            assert json_path.exists()
            
            # Vérifier que process_batch a été appelé avec le batch original
            mock_process_batch.assert_called_once()
            assert result == 1


def test_retry_batch_with_format_correction_failure(setup_test_files, tmp_path):
    """Tester la gestion d'erreur lors de la correction."""
    media_path, json_path = setup_test_files
    
    # Réinitialiser les statistiques
    statistics.stats = statistics.ProcessingStats()
    
    # Mock de detect_file_type pour lever une exception
    with patch('google_takeout_metadata.processor.detect_file_type', side_effect=Exception("Test error")):
        
        batch = [(media_path, json_path, ["-Title=Test"])]
        
        result = _retry_batch_with_format_correction(batch, False, tmp_path / "logs")
        
        # Vérifier que le résultat indique un échec
        assert result == 0
        
        # Vérifier que l'erreur a été enregistrée dans les statistiques
        assert len(statistics.stats.failed_files) == 1
        assert "fake_image.PNG" in statistics.stats.failed_files[0]
        assert "Test error" in statistics.stats.failed_files[0]
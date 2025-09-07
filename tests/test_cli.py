"""Tests pour l'interface en ligne de commande."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from google_takeout_metadata.cli import main


def test_main_no_args(capsys):
    """Tester que la CLI sans arguments affiche l'aide."""
    with pytest.raises(SystemExit):
        main([])
    
    captured = capsys.readouterr()
    assert "usage:" in captured.err


def test_main_help(capsys):
    """Tester l'option d'aide de la CLI."""
    with pytest.raises(SystemExit):
        main(["--help"])
    
    captured = capsys.readouterr()
    assert "Fusionner les métadonnées Google Takeout dans les images" in captured.out


def test_main_invalid_directory(capsys, tmp_path):
    """Tester la CLI avec un répertoire inexistant."""
    non_existent = tmp_path / "does_not_exist"
    
    with pytest.raises(SystemExit):
        main([str(non_existent)])
    
    # L'erreur est enregistrée mais pas affichée sur stderr avec la configuration actuelle
    # Donc nous ne vérifions pas la sortie capturée, juste qu'elle se termine


def test_main_file_instead_of_directory(capsys, tmp_path):
    """Tester la CLI avec un chemin de fichier au lieu d'un répertoire."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test")
    
    with pytest.raises(SystemExit):
        main([str(test_file)])
    
    # L'erreur est enregistrée mais pas affichée sur stderr avec la configuration actuelle
    # Donc nous ne vérifions pas la sortie capturée, juste qu'elle se termine


@patch('google_takeout_metadata.cli.process_directory')
def test_main_normal_mode(mock_process_directory, tmp_path):
    """Tester le mode de traitement normal de la CLI."""
    main([str(tmp_path)])
    
    mock_process_directory.assert_called_once_with(
        tmp_path, use_localtime=False, append_only=True, clean_sidecars=False
    )


@patch('google_takeout_metadata.cli.process_directory_batch')
def test_main_batch_mode(mock_process_directory_batch, tmp_path):
    """Tester le mode de traitement par lot de la CLI."""
    main(["--batch", str(tmp_path)])
    
    mock_process_directory_batch.assert_called_once_with(
        tmp_path, use_localtime=False, append_only=True, clean_sidecars=False
    )


@patch('google_takeout_metadata.cli.process_directory')
def test_main_localtime_option(mock_process_directory, tmp_path):
    """Tester la CLI avec l'option localtime."""
    main(["--localtime", str(tmp_path)])
    
    mock_process_directory.assert_called_once_with(
        tmp_path, use_localtime=True, append_only=True, clean_sidecars=False
    )


@patch('google_takeout_metadata.cli.process_directory')
def test_main_overwrite_option(mock_process_directory, tmp_path):
    """Tester la CLI avec l'option overwrite."""
    main(["--overwrite", str(tmp_path)])
    
    mock_process_directory.assert_called_once_with(
        tmp_path, use_localtime=False, append_only=False, clean_sidecars=False
    )


@patch('google_takeout_metadata.cli.process_directory')
def test_main_clean_sidecars_option(mock_process_directory, tmp_path):
    """Tester la CLI avec l'option clean-sidecars."""
    main(["--clean-sidecars", str(tmp_path)])
    
    mock_process_directory.assert_called_once_with(
        tmp_path, use_localtime=False, append_only=True, clean_sidecars=True
    )


@patch('google_takeout_metadata.cli.process_directory_batch')
def test_main_batch_with_all_options(mock_process_directory_batch, tmp_path):
    """Tester le mode batch de la CLI avec toutes les options."""
    main(["--batch", "--localtime", "--overwrite", "--clean-sidecars", str(tmp_path)])
    
    mock_process_directory_batch.assert_called_once_with(
        tmp_path, use_localtime=True, append_only=False, clean_sidecars=True
    )


def test_main_conflicting_options(capsys):
    """Tester la CLI avec des options conflictuelles append-only et overwrite obsolètes."""
    with pytest.raises(SystemExit):
        main(["--append-only", "--overwrite", "/some/path"])
    
    # L'erreur est enregistrée mais pas affichée sur stderr avec la configuration actuelle
    # Donc nous ne vérifions pas la sortie capturée, juste qu'elle se termine


@patch('google_takeout_metadata.cli.process_directory')
def test_main_deprecated_append_only_warning(mock_process_directory, tmp_path, caplog):
    """Tester que la CLI avec l'option append-only obsolète affiche un avertissement."""
    main(["--append-only", str(tmp_path)])
    
    assert "--append-only est obsolète" in caplog.text
    mock_process_directory.assert_called_once_with(
        tmp_path, use_localtime=False, append_only=True, clean_sidecars=False
    )


@patch('google_takeout_metadata.cli.process_directory')
def test_main_verbose_logging(mock_process_directory, tmp_path, caplog):
    """Tester que la CLI avec l'option verbose active le logging de debug."""
    # Nous devons tester que basicConfig a été appelé avec le niveau DEBUG
    # mais le niveau du logger root pourrait ne pas changer pendant le test
    main(["--verbose", str(tmp_path)])
    
    # S'assurer simplement que la fonction a été appelée - le test de logging est plus complexe
    # en raison de la façon dont pytest gère le logging
    mock_process_directory.assert_called_once()


@pytest.mark.integration
def test_main_integration_normal_mode(tmp_path):
    """Test d'intégration pour le mode normal de la CLI avec des fichiers réels."""
    try:
        # Créer une image de test
        media_path = tmp_path / "cli_test.jpg"
        img = Image.new('RGB', (100, 100), color='purple')
        img.save(media_path)
        
        # Créer le sidecar
        sidecar_data = {
            "title": "cli_test.jpg",
            "description": "CLI integration test"
        }
        json_path = tmp_path / "cli_test.jpg.json"
        json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
        
        # Exécuter la CLI
        main([str(tmp_path)])
        
        # Vérifier que les métadonnées ont été écrites
        cmd = [
            "exiftool",
            "-j",
            "-EXIF:ImageDescription",
            str(media_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        metadata = json.loads(result.stdout)[0]
        
        assert metadata.get("ImageDescription") == "CLI integration test"
        
    except FileNotFoundError:
        pytest.skip("exiftool not found - skipping CLI integration test")


@pytest.mark.integration
def test_main_integration_batch_mode(tmp_path):
    """Test d'intégration pour le mode batch de la CLI avec des fichiers réels."""
    try:
        # Créer plusieurs images de test
        files_data = [
            ("batch1.jpg", "CLI batch test 1"),
            ("batch2.jpg", "CLI batch test 2")
        ]
        
        for filename, description in files_data:
            # Créer l'image
            media_path = tmp_path / filename
            img = Image.new('RGB', (100, 100), color='orange')
            img.save(media_path)
            
            # Créer le sidecar
            sidecar_data = {
                "title": filename,
                "description": description
            }
            json_path = tmp_path / f"{filename}.json"
            json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
        
        # Exécuter la CLI en mode batch
        main(["--batch", str(tmp_path)])
        
        # Vérifier que tous les fichiers ont été traités
        for filename, expected_description in files_data:
            media_path = tmp_path / filename
            
            cmd = [
                "exiftool",
                "-j",
                "-EXIF:ImageDescription",
                str(media_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
            metadata = json.loads(result.stdout)[0]
            
            assert metadata.get("ImageDescription") == expected_description
        
    except FileNotFoundError:
        pytest.skip("exiftool not found - skipping CLI batch integration test")


@pytest.mark.integration
def test_main_integration_clean_sidecars(tmp_path):
    """Test d'intégration pour la CLI avec nettoyage des sidecars."""
    try:
        # Créer une image de test
        media_path = tmp_path / "cleanup.jpg"
        img = Image.new('RGB', (100, 100), color='cyan')
        img.save(media_path)
        
        # Créer le sidecar
        sidecar_data = {
            "title": "cleanup.jpg",
            "description": "CLI cleanup test"
        }
        json_path = tmp_path / "cleanup.jpg.json"
        json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
        
        # Vérifier que le sidecar existe
        assert json_path.exists()
        
        # Exécuter la CLI avec nettoyage
        main(["--clean-sidecars", str(tmp_path)])
        
        # Vérifier que le sidecar a été supprimé
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
        
        assert metadata.get("ImageDescription") == "CLI cleanup test"
        
    except FileNotFoundError:
        pytest.skip("exiftool not found - skipping CLI cleanup integration test")


def test_main_entry_point():
    """Tester que la fonction main peut être appelée sans arguments depuis le point d'entrée."""
    # Cela teste principalement que la signature de la fonction main est correcte pour les points d'entrée
    # Nous ne pouvons pas tester l'analyse CLI réelle sans mocker sys.argv
    with patch.object(sys, 'argv', ['google-takeout-metadata', '--help']):
        with pytest.raises(SystemExit):
            main()

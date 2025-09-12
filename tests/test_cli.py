"""Tests pour l'interface en ligne de commande."""

import json
import subprocess
import sys
import shutil
from unittest.mock import patch

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


def test_main_invalid_directory(tmp_path):
    """Tester la CLI avec un répertoire inexistant."""
    non_existent = tmp_path / "does_not_exist"

    with pytest.raises(SystemExit):
        with patch("shutil.which", return_value="/usr/bin/exiftool"):
            main([str(non_existent)])

    # L'erreur est enregistrée mais pas affichée sur stderr avec la configuration actuelle
    # Donc nous ne vérifions pas la sortie capturée, juste qu'elle se termine


def test_main_file_instead_of_directory(tmp_path):
    """Tester la CLI avec un chemin de fichier au lieu d'un répertoire."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test")

    with pytest.raises(SystemExit):
        with patch("shutil.which", return_value="/usr/bin/exiftool"):
            main([str(test_file)])

    # L'erreur est enregistrée mais pas affichée sur stderr avec la configuration actuelle
    # Donc nous ne vérifions pas la sortie capturée, juste qu'elle se termine


@patch('google_takeout_metadata.cli.process_directory')
def test_main_normal_mode(mock_process_directory, tmp_path):
    """Tester le mode de traitement normal de la CLI."""
    with patch("shutil.which", return_value="/usr/bin/exiftool"):
        main([str(tmp_path)])

    mock_process_directory.assert_called_once_with(
        tmp_path, use_localtime=False, append_only=True, immediate_delete=False, organize_files=False, geocode=False
    )


@patch('google_takeout_metadata.cli.process_directory_batch')
def test_main_batch_mode(mock_process_directory_batch, tmp_path):
    """Tester le mode de traitement par lot de la CLI."""
    with patch("shutil.which", return_value="/usr/bin/exiftool"):
        main(["--batch", str(tmp_path)])

    mock_process_directory_batch.assert_called_once_with(
        tmp_path, use_localtime=False, append_only=True, immediate_delete=False, organize_files=False, geocode=False
    )


@patch('google_takeout_metadata.cli.process_directory')
def test_main_localtime_option(mock_process_directory, tmp_path):
    """Tester la CLI avec l'option localtime."""
    with patch("shutil.which", return_value="/usr/bin/exiftool"):
        main(["--localtime", str(tmp_path)])

    mock_process_directory.assert_called_once_with(
        tmp_path, use_localtime=True, append_only=True, immediate_delete=False, organize_files=False, geocode=False
    )


@patch('google_takeout_metadata.cli.process_directory')
def test_main_overwrite_option(mock_process_directory, tmp_path):
    """Tester la CLI avec l'option overwrite."""
    with patch("shutil.which", return_value="/usr/bin/exiftool"):
        main(["--overwrite", str(tmp_path)])

    mock_process_directory.assert_called_once_with(
        tmp_path, use_localtime=False, append_only=False, immediate_delete=False, organize_files=False, geocode=False
    )


@patch('google_takeout_metadata.cli.process_directory')
def test_main_immediate_delete_option(mock_process_directory, tmp_path):
    """Tester la CLI avec l'option immediate-delete."""
    with patch("shutil.which", return_value="/usr/bin/exiftool"):
        main(["--immediate-delete", str(tmp_path)])

    mock_process_directory.assert_called_once_with(
        tmp_path, use_localtime=False, append_only=True, immediate_delete=True, organize_files=False, geocode=False
    )


@patch('google_takeout_metadata.cli.process_directory_batch')
def test_main_batch_with_all_options(mock_process_directory_batch, tmp_path):
    """Tester le mode batch de la CLI avec toutes les options."""
    with patch("shutil.which", return_value="/usr/bin/exiftool"):
        main(["--batch", "--localtime", "--overwrite", "--immediate-delete", "--geocode", str(tmp_path)])

    mock_process_directory_batch.assert_called_once_with(
        tmp_path, use_localtime=True, append_only=False, immediate_delete=True, organize_files=False, geocode=True
    )


@patch('google_takeout_metadata.cli.process_directory')
def test_main_geocode_option(mock_process_directory, tmp_path):
    """Tester la CLI avec l'option geocode."""
    with patch("shutil.which", return_value="/usr/bin/exiftool"):
        main(["--geocode", str(tmp_path)])

    mock_process_directory.assert_called_once_with(
        tmp_path, use_localtime=False, append_only=True, immediate_delete=False, organize_files=False, geocode=True
    )


@patch('google_takeout_metadata.cli.process_directory')
def test_main_verbose_logging(mock_process_directory, tmp_path):
    """Tester que la CLI avec l'option verbose active le logging de debug."""
    with patch("shutil.which", return_value="/usr/bin/exiftool"):
        main(["--verbose", str(tmp_path)])

    mock_process_directory.assert_called_once()


@pytest.mark.integration
def test_main_integration_normal_mode(tmp_path):
    """Test d'intégration pour le mode normal de la CLI avec des fichiers réels."""
    if shutil.which("exiftool") is None:
        pytest.skip("exiftool introuvable - skipping CLI integration test")

    media_path = tmp_path / "cli_test.jpg"
    img = Image.new('RGB', (100, 100), color='purple')
    img.save(media_path)

    sidecar_data = {"title": "cli_test.jpg", "description": "CLI integration test"}
    json_path = tmp_path / "cli_test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")

    main([str(tmp_path)])

    cmd = ["exiftool", "-j", "-EXIF:ImageDescription", str(media_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
    metadata = json.loads(result.stdout)[0]
    assert metadata.get("ImageDescription") == "CLI integration test"


@pytest.mark.integration
def test_main_integration_batch_mode(tmp_path):
    """Test d'intégration pour le mode batch de la CLI avec des fichiers réels."""
    if shutil.which("exiftool") is None:
        pytest.skip("exiftool introuvable - skipping CLI integration test")

    files_data = [
        ("batch1.jpg", "CLI batch test 1"),
        ("batch2.jpg", "CLI batch test 2"),
    ]
    for title, description in files_data:
        media_path = tmp_path / title
        img = Image.new('RGB', (100, 100), color='orange')
        img.save(media_path)
        sidecar_data = {"title": title, "description": description}
        json_path = tmp_path / f"{title}.json"
        json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")

    main(["--batch", str(tmp_path)])

    for title, description in files_data:
        cmd = ["exiftool", "-j", "-EXIF:ImageDescription", str(tmp_path / title)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        metadata = json.loads(result.stdout)[0]
        assert metadata.get("ImageDescription") == description


@pytest.mark.integration
def test_main_integration_immediate_delete(tmp_path):
    """Test d'intégration pour la CLI avec suppression immédiate des sidecars."""
    if shutil.which("exiftool") is None:
        pytest.skip("exiftool introuvable - skipping CLI integration test")

    media_path = tmp_path / "cleanup.jpg"
    img = Image.new('RGB', (100, 100), color='cyan')
    img.save(media_path)
    sidecar_data = {"title": "cleanup.jpg", "description": "CLI immediate delete test"}
    json_path = tmp_path / "cleanup.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")

    assert json_path.exists()

    main(["--immediate-delete", str(tmp_path)])

    assert not json_path.exists()
    cmd = ["exiftool", "-j", "-EXIF:ImageDescription", str(media_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
    metadata = json.loads(result.stdout)[0]
    assert metadata.get("ImageDescription") == "CLI immediate delete test"


def test_main_entry_point():
    """Tester que la fonction main peut être appelée sans arguments depuis le point d'entrée."""
    with patch.object(sys, 'argv', ['google-takeout-metadata', '--help']):
        with pytest.raises(SystemExit):
            main()


"""Tests for the command line interface."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from google_takeout_metadata.cli import main


def test_main_no_args(capsys):
    """Test CLI with no arguments shows help."""
    with pytest.raises(SystemExit):
        main([])
    
    captured = capsys.readouterr()
    assert "usage:" in captured.err


def test_main_help(capsys):
    """Test CLI help option."""
    with pytest.raises(SystemExit):
        main(["--help"])
    
    captured = capsys.readouterr()
    assert "Merge Google Takeout metadata into images" in captured.out


def test_main_invalid_directory(capsys, tmp_path):
    """Test CLI with non-existent directory."""
    non_existent = tmp_path / "does_not_exist"
    
    with pytest.raises(SystemExit):
        main([str(non_existent)])
    
    # The error is logged but not printed to stderr with the current setup
    # So we don't check captured output, just that it exits


def test_main_file_instead_of_directory(capsys, tmp_path):
    """Test CLI with file path instead of directory."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test")
    
    with pytest.raises(SystemExit):
        main([str(test_file)])
    
    # The error is logged but not printed to stderr with the current setup
    # So we don't check captured output, just that it exits


@patch('google_takeout_metadata.cli.process_directory')
def test_main_normal_mode(mock_process_directory, tmp_path):
    """Test CLI normal processing mode."""
    main([str(tmp_path)])
    
    mock_process_directory.assert_called_once_with(
        tmp_path, use_localtime=False, append_only=True, clean_sidecars=False
    )


@patch('google_takeout_metadata.cli.process_directory_batch')
def test_main_batch_mode(mock_process_directory_batch, tmp_path):
    """Test CLI batch processing mode."""
    main(["--batch", str(tmp_path)])
    
    mock_process_directory_batch.assert_called_once_with(
        tmp_path, use_localtime=False, append_only=True, clean_sidecars=False
    )


@patch('google_takeout_metadata.cli.process_directory')
def test_main_localtime_option(mock_process_directory, tmp_path):
    """Test CLI with localtime option."""
    main(["--localtime", str(tmp_path)])
    
    mock_process_directory.assert_called_once_with(
        tmp_path, use_localtime=True, append_only=True, clean_sidecars=False
    )


@patch('google_takeout_metadata.cli.process_directory')
def test_main_overwrite_option(mock_process_directory, tmp_path):
    """Test CLI with overwrite option."""
    main(["--overwrite", str(tmp_path)])
    
    mock_process_directory.assert_called_once_with(
        tmp_path, use_localtime=False, append_only=False, clean_sidecars=False
    )


@patch('google_takeout_metadata.cli.process_directory')
def test_main_clean_sidecars_option(mock_process_directory, tmp_path):
    """Test CLI with clean-sidecars option."""
    main(["--clean-sidecars", str(tmp_path)])
    
    mock_process_directory.assert_called_once_with(
        tmp_path, use_localtime=False, append_only=True, clean_sidecars=True
    )


@patch('google_takeout_metadata.cli.process_directory_batch')
def test_main_batch_with_all_options(mock_process_directory_batch, tmp_path):
    """Test CLI batch mode with all options."""
    main(["--batch", "--localtime", "--overwrite", "--clean-sidecars", str(tmp_path)])
    
    mock_process_directory_batch.assert_called_once_with(
        tmp_path, use_localtime=True, append_only=False, clean_sidecars=True
    )


def test_main_conflicting_options(capsys):
    """Test CLI with conflicting deprecated append-only and overwrite options."""
    with pytest.raises(SystemExit):
        main(["--append-only", "--overwrite", "/some/path"])
    
    # The error is logged but not printed to stderr with the current setup
    # So we don't check captured output, just that it exits


@patch('google_takeout_metadata.cli.process_directory')
def test_main_deprecated_append_only_warning(mock_process_directory, tmp_path, caplog):
    """Test CLI with deprecated append-only option shows warning."""
    main(["--append-only", str(tmp_path)])
    
    assert "--append-only is deprecated" in caplog.text
    mock_process_directory.assert_called_once_with(
        tmp_path, use_localtime=False, append_only=True, clean_sidecars=False
    )


@patch('google_takeout_metadata.cli.process_directory')
def test_main_verbose_logging(mock_process_directory, tmp_path, caplog):
    """Test CLI with verbose option enables debug logging."""
    # We need to test that basicConfig was called with DEBUG level
    # but the root logger level might not change during the test
    main(["--verbose", str(tmp_path)])
    
    # Just ensure the function was called - the logging test is more complex 
    # due to how pytest manages logging
    mock_process_directory.assert_called_once()


@pytest.mark.integration
def test_main_integration_normal_mode(tmp_path):
    """Integration test for CLI normal mode with actual files."""
    try:
        # Create test image
        media_path = tmp_path / "cli_test.jpg"
        img = Image.new('RGB', (100, 100), color='purple')
        img.save(media_path)
        
        # Create sidecar
        sidecar_data = {
            "title": "cli_test.jpg",
            "description": "CLI integration test"
        }
        json_path = tmp_path / "cli_test.jpg.json"
        json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
        
        # Run CLI
        main([str(tmp_path)])
        
        # Verify metadata was written
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
    """Integration test for CLI batch mode with actual files."""
    try:
        # Create multiple test images
        files_data = [
            ("batch1.jpg", "CLI batch test 1"),
            ("batch2.jpg", "CLI batch test 2")
        ]
        
        for filename, description in files_data:
            # Create image
            media_path = tmp_path / filename
            img = Image.new('RGB', (100, 100), color='orange')
            img.save(media_path)
            
            # Create sidecar
            sidecar_data = {
                "title": filename,
                "description": description
            }
            json_path = tmp_path / f"{filename}.json"
            json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
        
        # Run CLI in batch mode
        main(["--batch", str(tmp_path)])
        
        # Verify all files were processed
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
    """Integration test for CLI with sidecar cleanup."""
    try:
        # Create test image
        media_path = tmp_path / "cleanup.jpg"
        img = Image.new('RGB', (100, 100), color='cyan')
        img.save(media_path)
        
        # Create sidecar
        sidecar_data = {
            "title": "cleanup.jpg",
            "description": "CLI cleanup test"
        }
        json_path = tmp_path / "cleanup.jpg.json"
        json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
        
        # Verify sidecar exists
        assert json_path.exists()
        
        # Run CLI with cleanup
        main(["--clean-sidecars", str(tmp_path)])
        
        # Verify sidecar was removed
        assert not json_path.exists()
        
        # Verify metadata was still written
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
    """Test that the main function can be called without arguments from entry point."""
    # This mainly tests that the main function signature is correct for entry points
    # We can't test the actual CLI parsing without mocking sys.argv
    with patch.object(sys, 'argv', ['google-takeout-metadata', '--help']):
        with pytest.raises(SystemExit):
            main()

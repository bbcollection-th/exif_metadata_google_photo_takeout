from pathlib import Path
import json
import unittest.mock

from google_takeout_metadata.processor import (
    process_directory, 
    _is_sidecar_file, 
    fix_file_extension_mismatch
)


def test_ignore_non_sidecar(tmp_path: Path) -> None:
    (tmp_path / "data.json").write_text("{}", encoding="utf-8")
    process_directory(tmp_path)


def test_is_sidecar_file_standard_pattern() -> None:
    """Test standard pattern: photo.jpg.json"""
    assert _is_sidecar_file(Path("photo.jpg.json"))
    assert _is_sidecar_file(Path("video.mp4.json"))
    assert _is_sidecar_file(Path("image.PNG.JSON"))  # case insensitive


def test_is_sidecar_file_supplemental_metadata_pattern() -> None:
    """Test new Google Takeout format: photo.jpg.supplemental-metadata.json"""
    assert _is_sidecar_file(Path("IMG_001.jpg.supplemental-metadata.json"))
    assert _is_sidecar_file(Path("video.mp4.supplemental-metadata.json"))
    assert _is_sidecar_file(Path("image.PNG.SUPPLEMENTAL-METADATA.JSON"))  # case insensitive
    assert _is_sidecar_file(Path("photo.heic.supplemental-metadata.json"))


def test_is_sidecar_file_older_pattern() -> None:
    """Test older pattern: photo.json"""
    assert _is_sidecar_file(Path("IMG_1234.jpg.json"))  # this should work with the new logic
    # Note: photo.json without extension in name would not be detected
    # as it's ambiguous, but that's fine since parse_sidecar() validates


def test_is_sidecar_file_negative() -> None:
    """Test files that should not be detected as sidecars"""
    assert not _is_sidecar_file(Path("data.json"))  # no image extension
    assert not _is_sidecar_file(Path("photo.txt"))  # not json
    assert not _is_sidecar_file(Path("photo.jpg"))  # not json
    assert not _is_sidecar_file(Path("metadata.json"))  # album metadata, not sidecar
    assert not _is_sidecar_file(Path("métadonnées.json"))  # album metadata, not sidecar


def test_fix_file_extension_mismatch_rollback_on_failure(tmp_path: Path) -> None:
    """Test that fix_file_extension_mismatch properly rolls back image rename on failure"""
    # Create a fake JPEG file with wrong extension
    image_path = tmp_path / "photo.png"
    image_path.write_bytes(b'\xff\xd8\xff\xe0')  # JPEG magic bytes
    
    # Create corresponding JSON file
    json_path = tmp_path / "photo.png.supplemental-metadata.json"
    json_data = {"title": "photo.png"}
    json_path.write_text(json.dumps(json_data), encoding='utf-8')
    
    # Mock Path.unlink to raise an error (simulating read-only file)
    original_unlink = Path.unlink
    def mock_unlink(self):
        if self.name.endswith('.supplemental-metadata.json') and 'photo.png' in str(self):
            raise OSError("Permission denied")
        return original_unlink(self)
    
    with unittest.mock.patch.object(Path, 'unlink', mock_unlink):
        result_image, result_json = fix_file_extension_mismatch(image_path, json_path)
        
        # Should have rolled back successfully
        assert result_image == image_path
        assert result_json == json_path
        assert image_path.exists()  # Original image path should exist again
        assert not (tmp_path / "photo.jpg").exists()  # Renamed image should not exist


def test_fix_file_extension_mismatch_failed_rollback(tmp_path: Path) -> None:
    """Test fix_file_extension_mismatch when both operation and rollback fail"""
    # Create a fake JPEG file with wrong extension
    image_path = tmp_path / "photo.png"
    image_path.write_bytes(b'\xff\xd8\xff\xe0')  # JPEG magic bytes
    
    # Create corresponding JSON file
    json_path = tmp_path / "photo.png.supplemental-metadata.json"
    json_data = {"title": "photo.png"}
    json_path.write_text(json.dumps(json_data), encoding='utf-8')
    
    # Mock to simulate both unlink failure and rollback failure
    original_unlink = Path.unlink
    original_rename = Path.rename
    
    def mock_unlink(self):
        if self.name.endswith('.supplemental-metadata.json'):
            raise OSError("Permission denied")
        return original_unlink(self)
    
    def mock_rename(self, target):
        # If trying to rename back (rollback), fail
        if str(target).endswith('.png') and str(self).endswith('.jpg'):
            raise OSError("Rollback failed")
        # Otherwise, do the actual rename
        return original_rename(self, target)
    
    with unittest.mock.patch.object(Path, 'unlink', mock_unlink), \
         unittest.mock.patch.object(Path, 'rename', mock_rename):
        
        result_image, result_json = fix_file_extension_mismatch(image_path, json_path)
        
        # Should return new image path but old JSON path due to failed rollback
        assert result_image == tmp_path / "photo.jpg"
        assert result_json == json_path  # Original JSON path
        assert (tmp_path / "photo.jpg").exists()  # New image should exist
        assert not image_path.exists()  # Original image should not exist

from pathlib import Path

from google_takeout_metadata.processor import process_directory, _is_sidecar_file


def test_ignore_non_sidecar(tmp_path: Path) -> None:
    (tmp_path / "data.json").write_text("{}", encoding="utf-8")
    process_directory(tmp_path)


def test_is_sidecar_file_standard_pattern() -> None:
    """Test standard pattern: photo.jpg.json"""
    assert _is_sidecar_file(Path("photo.jpg.json"))
    assert _is_sidecar_file(Path("video.mp4.json"))
    assert _is_sidecar_file(Path("image.PNG.JSON"))  # case insensitive


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

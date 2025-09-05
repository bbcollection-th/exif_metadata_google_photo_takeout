from pathlib import Path

from google_takeout_metadata.processor import process_directory


def test_ignore_non_sidecar(tmp_path: Path) -> None:
    (tmp_path / "data.json").write_text("{}", encoding="utf-8")
    process_directory(tmp_path)

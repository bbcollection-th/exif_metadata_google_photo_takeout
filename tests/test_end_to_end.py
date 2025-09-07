from pathlib import Path
import json
import subprocess
import shutil
import pytest
from PIL import Image

from google_takeout_metadata.processor import process_directory


@pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")
def test_end_to_end(tmp_path: Path) -> None:
    # créer une image factice
    img_path = tmp_path / "sample.jpg"
    Image.new("RGB", (10, 10), color="red").save(img_path)
    # créer le sidecar correspondant
    data = {
        "title": "sample.jpg",
        "description": 'Magicien "en" or',
        "photoTakenTime": {"timestamp": "1736719606"},
        "people": [{"name": "anthony vincent"}],
    }
    (tmp_path / "sample.jpg.json").write_text(json.dumps(data), encoding="utf-8")

    process_directory(tmp_path)

    exe = shutil.which("exiftool") or "exiftool"
    result = subprocess.run(
        [
            exe,
            "-j",
            "-XMP-iptcExt:PersonInImage",
            "-XMP-dc:Subject",
            "-IPTC:Keywords",
            "-EXIF:ImageDescription",
            str(img_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    tags = json.loads(result.stdout)[0]
    
    # exiftool retourne les valeurs uniques en chaînes, les valeurs multiples en listes
    # Normaliser en listes pour la comparaison
    def normalize_to_list(value):
        if value is None:
            return []
        elif isinstance(value, list):
            return value
        else:
            return [value]
    
    assert normalize_to_list(tags.get("PersonInImage")) == ["anthony vincent"]
    assert normalize_to_list(tags.get("Subject")) == ["anthony vincent"]
    assert normalize_to_list(tags.get("Keywords")) == ["anthony vincent"]
    assert tags.get("ImageDescription") == 'Magicien "en" or'

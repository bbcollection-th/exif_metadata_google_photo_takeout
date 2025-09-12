from pathlib import Path
import json
import subprocess
import shutil
import pytest
from PIL import Image

from google_takeout_metadata.processor import process_directory


@pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")
def test_end_to_end_image(tmp_path: Path) -> None:
    # créer une image factice
    img_path = tmp_path / "IMG_0123456789.jpg"
    Image.new("RGB", (10, 10), color="red").save(img_path)
    # créer le sidecar correspondant
    data = {
        "title": "IMG_0123456789.jpg",
        "description": 'Magicien "en" or',
        "photoTakenTime": {"timestamp": "1745370366", "formatted": "23 avr. 2025, 01:06:06 UTC"},
        "people": [{"name": "anthony vincent"}],
    }
    (tmp_path / "IMG_0123456789.jpg.supplemental-metadata.json").write_text(json.dumps(data), encoding="utf-8")
    # créer une image factice
    img_path = tmp_path / "sample.jpg"
    Image.new("RGB", (10, 10), color="red").save(img_path)
    # créer le sidecar correspondant
    data = {
        "title": "IMG_0123456789.jpg",
        "description": 'Magicien "en" or',
        "photoTakenTime": {"timestamp": "1745370366", "formatted": "23 avr. 2025, 01:06:06 UTC"},
        "people": [{"name": "anthony vincent"}],
    }
    (tmp_path / "IMG_0123456789.jpg.supplemental-data.json").write_text(json.dumps(data), encoding="utf-8")

    process_directory(root=tmp_path,
            use_localtime=False,
            append_only=True,
            immediate_delete=False,
            organize_files=True,
            geocode=False)

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
    
    assert normalize_to_list(tags.get("PersonInImage")) == ["Anthony Vincent"]
    assert normalize_to_list(tags.get("Subject")) == ["Anthony Vincent"]
    assert normalize_to_list(tags.get("Keywords")) == ["Anthony Vincent"]
    assert tags.get("ImageDescription") == 'Magicien "en" or'

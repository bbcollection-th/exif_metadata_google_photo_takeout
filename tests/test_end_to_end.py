from pathlib import Path
import json
import subprocess
from PIL import Image

from google_takeout_metadata.processor import process_directory


def test_end_to_end(tmp_path: Path) -> None:
    # create dummy image
    img_path = tmp_path / "sample.jpg"
    Image.new("RGB", (10, 10), color="red").save(img_path)

    # create matching sidecar
    data = {
        "title": "sample.jpg",
        "description": 'Magicien "en" or',
        "photoTakenTime": {"timestamp": "1736719606"},
        "people": [{"name": "anthony vincent"}],
    }
    (tmp_path / "sample.jpg.json").write_text(json.dumps(data), encoding="utf-8")

    process_directory(tmp_path)

    result = subprocess.run(
        [
            "exiftool",
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

    lines = {
        line.split(":", 1)[0].strip(): line.split(":", 1)[1].strip()
        for line in result.stdout.strip().splitlines()
    }
    assert lines.get("Person In Image") == "anthony vincent"
    assert lines.get("Subject") == "anthony vincent"
    assert lines.get("Keywords") == "anthony vincent"
    assert lines.get("Image Description") == 'Magicien "en" or'

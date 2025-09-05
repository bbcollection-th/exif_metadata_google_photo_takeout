from google_takeout_metadata.sidecar import SidecarData
from google_takeout_metadata.exif_writer import build_exiftool_args, write_metadata
import subprocess
import pytest


def test_build_args() -> None:
    meta = SidecarData(
        filename="a.jpg",
        description="desc",
        people=["alice"],
        taken_at=1736719606,
        created_at=None,
        latitude=-1.0,
        longitude=2.0,
        altitude=3.0,
    )

    args = build_exiftool_args(meta)
    assert "-EXIF:ImageDescription=desc" in args
    assert "-XMP-iptcExt:PersonInImage+=alice" in args
    assert "-GPSLatitude=1.0" in args
    assert "-GPSLatitudeRef=S" in args
    assert "-GPSLongitudeRef=E" in args
    assert "-GPSAltitude=3.0" in args


def test_write_metadata_error(tmp_path, monkeypatch):
    meta = SidecarData(
        filename="a.jpg",
        description="test",  # Add description to ensure args are generated
        people=[],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
    )
    img = tmp_path / "a.jpg"
    img.write_bytes(b"data")

    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "exiftool", stderr="bad")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError):
        write_metadata(img, meta)

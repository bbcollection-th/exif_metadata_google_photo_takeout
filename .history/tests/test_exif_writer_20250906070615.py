from google_takeout_metadata.sidecar import SidecarData
from google_takeout_metadata.exif_writer import build_exiftool_args, write_metadata
import subprocess
import pytest
from pathlib import Path


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
        favorite=False,
    )

    args = build_exiftool_args(meta)
    assert "-EXIF:ImageDescription=desc" in args
    assert "-XMP-iptcExt:PersonInImage+=alice" in args
    assert "-GPSLatitude=1.0" in args
    assert "-GPSLatitudeRef=S" in args
    assert "-GPSLongitudeRef=E" in args
    assert "-GPSAltitude=3.0" in args
    # Check charset parameters
    assert "-charset" in args
    assert "filename=UTF8" in args


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
        favorite=False,
    )
    img = tmp_path / "a.jpg"
    img.write_bytes(b"data")

    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "exiftool", stderr="bad")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError):
        write_metadata(img, meta)


def test_build_args_video():
    """Test video-specific tags are added for MP4/MOV files."""
    meta = SidecarData(
        filename="video.mp4",
        description="Video description",
        people=["alice"],
        taken_at=1736719606,
        created_at=None,
        latitude=48.8566,
        longitude=2.3522,
        altitude=None,
    )
    
    video_path = Path("video.mp4")
    args = build_exiftool_args(meta, video_path)
    
    # Check video-specific tags
    assert "-Keys:Title='Video description'" in args
    assert "-Keys:Description='Video description'" in args
    assert any("-QuickTime:CreateDate=" in arg for arg in args)
    assert any("-QuickTime:ModifyDate=" in arg for arg in args)
    assert "-Keys:Location=48.8566,2.3522" in args
    assert "-QuickTime:GPSCoordinates=48.8566,2.3522" in args
    assert "-api" in args
    assert "QuickTimeUTC=1" in args


def test_build_args_localtime():
    """Test that local time formatting works."""
    meta = SidecarData(
        filename="a.jpg",
        description=None,
        people=[],
        taken_at=1736719606,  # 2025-01-12 22:06:46 UTC
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        favorite=False,
    )

    # Test UTC (default)
    args_utc = build_exiftool_args(meta, Path("a.jpg"), use_localtime=False)
    # Test local time
    args_local = build_exiftool_args(meta, Path("a.jpg"), use_localtime=True)
    
    # The datetime strings will be different (unless running in UTC timezone)
    # but both should contain some form of DateTimeOriginal
    assert any("-DateTimeOriginal=" in arg for arg in args_utc)
    assert any("-DateTimeOriginal=" in arg for arg in args_local)


def test_build_args_append_only() -> None:
    """Test append-only mode uses correct exiftool syntax."""
    meta = SidecarData(
        filename="a.jpg",
        description="desc",
        people=["alice", "bob"],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        favorite=False,
    )

    # Normal mode
    args_normal = build_exiftool_args(meta, append_only=False)
    assert "-EXIF:ImageDescription=desc" in args_normal
    assert "-XMP-iptcExt:PersonInImage+=alice" in args_normal

    # Append-only mode
    args_append = build_exiftool_args(meta, append_only=True)
    assert "-EXIF:ImageDescription-=desc" in args_append
    assert "-XMP-iptcExt:PersonInImage-+=alice" in args_append


def test_build_args_favorite() -> None:
    """Test favorite photos get rating=5."""
    meta = SidecarData(
        filename="a.jpg",
        description=None,
        people=[],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        favorite=True,
    )

    args = build_exiftool_args(meta)
    assert "-XMP:Rating=5" in args

    # Test append-only mode
    args_append = build_exiftool_args(meta, append_only=True)
    assert "-XMP:Rating-=5" in args_append


def test_build_args_no_favorite() -> None:
    """Test non-favorite photos don't get rating."""
    meta = SidecarData(
        filename="a.jpg",
        description=None,
        people=[],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        favorite=False,
    )

    args = build_exiftool_args(meta)
    assert not any("Rating" in arg for arg in args)

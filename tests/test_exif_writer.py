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

    args = build_exiftool_args(meta, append_only=False)
    assert "-EXIF:ImageDescription=desc" in args
    assert "-XMP-iptcExt:PersonInImage+=alice" in args
    assert "-GPSLatitude=1.0" in args
    assert "-GPSLatitudeRef=S" in args
    assert "-GPSLongitudeRef=E" in args
    assert "-GPSAltitude=3.0" in args
    # Les options charset sont maintenant dans write_metadata() seulement


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
        favorite=False,
    )
    
    video_path = Path("video.mp4")
    args = build_exiftool_args(meta, video_path)
    
    # Check video-specific tags
    assert "-Keys:Description=Video description" in args
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
    # In append-only mode, we use -if conditions to only write if tag doesn't exist
    assert "-if" in args_append
    assert "not $EXIF:ImageDescription" in args_append
    assert "-EXIF:ImageDescription=desc" in args_append
    # People use += to add without removing existing values
    assert "-XMP-iptcExt:PersonInImage+=alice" in args_append
    assert "-XMP-iptcExt:PersonInImage+=bob" in args_append


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

    args = build_exiftool_args(meta, append_only=False)
    assert "-XMP:Rating=5" in args

    # Test append-only mode (now the default behavior)
    args_append = build_exiftool_args(meta, append_only=True)
    # Should use conditional writing with -if
    assert "-if" in args_append
    assert "not $XMP:Rating" in args_append
    assert "-XMP:Rating=5" in args_append


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


def test_build_args_albums() -> None:
    """Test that albums are written as keywords with Album: prefix."""
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
        albums=["Vacances 2024", "Famille"]
    )

    args = build_exiftool_args(meta, append_only=False)
    assert "-XMP-dc:Subject+=Album: Vacances 2024" in args
    assert "-IPTC:Keywords+=Album: Vacances 2024" in args
    assert "-XMP-dc:Subject+=Album: Famille" in args
    assert "-IPTC:Keywords+=Album: Famille" in args


def test_build_args_albums_append_only() -> None:
    """Test albums in append-only mode."""
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
        albums=["Test Album"]
    )

    args = build_exiftool_args(meta, append_only=True)
    # Albums use += to add without removing existing values
    assert "-XMP-dc:Subject+=Album: Test Album" in args
    assert "-IPTC:Keywords+=Album: Test Album" in args


def test_build_args_no_albums() -> None:
    """Test that empty albums list doesn't add any album tags."""
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
        albums=[]
    )

    args = build_exiftool_args(meta)
    assert not any("Album:" in arg for arg in args)


def test_build_args_default_behavior() -> None:
    """Test that default behavior is append-only (safe mode)."""
    meta = SidecarData(
        filename="a.jpg",
        description="Safe description",
        people=["Safe Person"],
        taken_at=1736719606,
        created_at=None,
        latitude=48.8566,
        longitude=2.3522,
        altitude=None,
        favorite=True,
    )

    # Default behavior should be append-only (safe)
    args = build_exiftool_args(meta)
    
    # Should use -if conditions for descriptions and ratings
    assert "-if" in args
    assert "not $EXIF:ImageDescription" in args
    assert "-EXIF:ImageDescription=Safe description" in args
    # Should use += for people (lists)
    assert "-XMP-iptcExt:PersonInImage+=Safe Person" in args
    # Should use -if condition for rating
    assert "not $XMP:Rating" in args
    assert "-XMP:Rating=5" in args
    # Should use -if condition for GPS
    assert "not $GPSLatitude" in args
    assert "-GPSLatitude=48.8566" in args


def test_build_args_overwrite_mode() -> None:
    """Test explicit overwrite mode (destructive)."""
    meta = SidecarData(
        filename="a.jpg",
        description="Overwrite description",
        people=["Overwrite Person"],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        favorite=True,
    )

    # Explicit overwrite mode
    args = build_exiftool_args(meta, append_only=False)
    
    # Should use direct assignment for descriptions and ratings
    assert "-EXIF:ImageDescription=Overwrite description" in args
    assert "-XMP-iptcExt:PersonInImage+=Overwrite Person" in args
    assert "-XMP:Rating=5" in args
    # Should NOT have -if conditions
    assert "-if" not in args
    assert "not $EXIF:ImageDescription" not in args
    assert "not $XMP-iptcExt:PersonInImage" not in args
    assert "not $XMP:Rating" not in args


def test_build_args_people_default() -> None:
    """Test that people are handled safely by default."""
    meta = SidecarData(
        filename="a.jpg",
        description=None,
        people=["Alice Dupont", "Bob Martin", "Charlie Bernard"],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        favorite=False,
    )

    # Default behavior (append-only)
    args = build_exiftool_args(meta)
    
    # Each person should use += (append to list)
    for person in ["Alice Dupont", "Bob Martin", "Charlie Bernard"]:
        assert f"-XMP-iptcExt:PersonInImage+={person}" in args
        assert f"-XMP-dc:Subject+={person}" in args
        assert f"-IPTC:Keywords+={person}" in args
    
    # Should NOT have -if conditions for people (they are lists, use +=)
    assert "not $XMP-iptcExt:PersonInImage" not in args
    assert "not $XMP-dc:Subject" not in args
    assert "not $IPTC:Keywords" not in args


def test_build_args_albums_default() -> None:
    """Test that albums are handled safely by default."""
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
        albums=["Vacances Été 2024", "Photos de Famille", "Événements Spéciaux"]
    )

    # Default behavior (append-only)
    args = build_exiftool_args(meta)
    
    # Each album should use += (append to list)
    for album in ["Vacances Été 2024", "Photos de Famille", "Événements Spéciaux"]:
        album_keyword = f"Album: {album}"
        assert f"-XMP-dc:Subject+={album_keyword}" in args
        assert f"-IPTC:Keywords+={album_keyword}" in args
    
    # Should NOT have -if conditions for albums (they are lists, use +=)
    assert "not $XMP-dc:Subject" not in args
    assert "not $IPTC:Keywords" not in args

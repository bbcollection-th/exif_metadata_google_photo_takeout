"""Integration tests that actually run exiftool and verify metadata is written correctly."""

from pathlib import Path
import json
import subprocess
import tempfile
import pytest
from PIL import Image

from google_takeout_metadata.processor import process_sidecar_file
from google_takeout_metadata.sidecar import SidecarData


def _run_exiftool_read(image_path: Path) -> dict:
    """Run exiftool to read metadata from an image file."""
    cmd = [
        "exiftool", 
        "-json",
        "-charset", "filename=UTF8",
        "-charset", "iptc=UTF8", 
        "-charset", "exif=UTF8",
        "-charset", "XMP=UTF8",
        str(image_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        data = json.loads(result.stdout)
        return data[0] if data else {}
    except FileNotFoundError:
        pytest.skip("exiftool not found - skipping integration tests")
    except subprocess.CalledProcessError as e:
        pytest.fail(f"exiftool failed: {e.stderr}")


@pytest.mark.integration
def test_write_and_read_description(tmp_path: Path) -> None:
    """Test that description is written and can be read back."""
    # Create a simple test image
    image_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='red')
    img.save(image_path)
    
    # Create sidecar JSON
    sidecar_data = {
        "title": "test.jpg",
        "description": "Test photo with ñ and émojis 🎉"
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Process the sidecar
    process_sidecar_file(json_path)
    
    # Read back metadata
    metadata = _run_exiftool_read(image_path)
    
    # Verify description was written
    assert metadata.get("Description") == "Test photo with ñ and émojis 🎉"
    assert metadata.get("ImageDescription") == "Test photo with ñ and émojis 🎉"


@pytest.mark.integration
def test_write_and_read_people(tmp_path: Path) -> None:
    """Test that people names are written and can be read back."""
    # Create a simple test image
    image_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='blue')
    img.save(image_path)
    
    # Create sidecar JSON with people
    sidecar_data = {
        "title": "test.jpg",
        "people": [
            {"name": "Alice Dupont"},
            {"name": "Bob Martin"}
        ]
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Process the sidecar
    process_sidecar_file(json_path)
    
    # Read back metadata
    metadata = _run_exiftool_read(image_path)
    
    # Verify people were written
    keywords = metadata.get("Keywords", [])
    if isinstance(keywords, str):
        keywords = [keywords]
    
    assert "Alice Dupont" in keywords
    assert "Bob Martin" in keywords


@pytest.mark.integration 
def test_write_and_read_gps(tmp_path: Path) -> None:
    """Test that GPS coordinates are written and can be read back."""
    # Create a simple test image
    image_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='green')
    img.save(image_path)
    
    # Create sidecar JSON with GPS data
    sidecar_data = {
        "title": "test.jpg",
        "geoData": {
            "latitude": 48.8566,
            "longitude": 2.3522,
            "altitude": 35.0
        }
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Process the sidecar
    process_sidecar_file(json_path)
    
    # Read back metadata
    metadata = _run_exiftool_read(image_path)
    
    # Verify GPS data was written
    # exiftool returns GPS coordinates in human-readable format, so we need to check differently
    gps_lat = metadata.get("GPSLatitude")
    gps_lon = metadata.get("GPSLongitude")
    
    # Check that GPS fields exist and contain expected degree values
    assert gps_lat is not None, "GPSLatitude should be set"
    assert gps_lon is not None, "GPSLongitude should be set"
    assert "48 deg" in str(gps_lat), f"Expected 48 degrees in latitude, got: {gps_lat}"
    assert "2 deg" in str(gps_lon), f"Expected 2 degrees in longitude, got: {gps_lon}"
    
    # GPS references can be "N"/"North" and "E"/"East" depending on exiftool version
    lat_ref = metadata.get("GPSLatitudeRef")
    lon_ref = metadata.get("GPSLongitudeRef")
    assert lat_ref in ["N", "North"], f"Expected N or North for latitude ref, got: {lat_ref}"
    assert lon_ref in ["E", "East"], f"Expected E or East for longitude ref, got: {lon_ref}"


@pytest.mark.integration
def test_write_and_read_favorite(tmp_path: Path) -> None:
    """Test that favorite status is written as rating."""
    # Create a simple test image
    image_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='yellow')
    img.save(image_path)
    
    # Create sidecar JSON with favorite
    sidecar_data = {
        "title": "test.jpg",
        "favorited": {"value": True}
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Process the sidecar
    process_sidecar_file(json_path)
    
    # Read back metadata
    metadata = _run_exiftool_read(image_path)
    
    # Verify rating was written
    assert int(metadata.get("Rating", 0)) == 5


@pytest.mark.integration
def test_append_only_mode(tmp_path: Path) -> None:
    """Test that append-only mode doesn't overwrite existing description."""
    # Create a simple test image
    image_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='purple')
    img.save(image_path)
    
    # First, manually add a description
    cmd = [
        "exiftool", 
        "-overwrite_original",
        "-EXIF:ImageDescription=Original description",
        str(image_path)
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
    except FileNotFoundError:
        pytest.skip("exiftool not found - skipping integration tests")
    
    # Create sidecar JSON with different description
    sidecar_data = {
        "title": "test.jpg", 
        "description": "New description from sidecar"
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Process the sidecar in append-only mode
    process_sidecar_file(json_path, append_only=True)
    
    # Read back metadata
    metadata = _run_exiftool_read(image_path)
    
    # In append-only mode, original description should be preserved
    # Note: exiftool's -= operator doesn't overwrite if field exists
    assert metadata.get("ImageDescription") == "Original description"


@pytest.mark.integration
def test_datetime_formats(tmp_path: Path) -> None:
    """Test that datetime is written in correct format."""
    # Create a simple test image
    image_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='orange')
    img.save(image_path)
    
    # Create sidecar JSON with timestamp
    sidecar_data = {
        "title": "test.jpg",
        "photoTakenTime": {"timestamp": "1736719606"}  # Unix timestamp
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Process the sidecar
    process_sidecar_file(json_path)
    
    # Read back metadata
    metadata = _run_exiftool_read(image_path)
    
    # Verify datetime format (should be YYYY:MM:DD HH:MM:SS)
    date_original = metadata.get("DateTimeOriginal")
    assert date_original is not None
    assert ":" in date_original
    # Should match EXIF datetime format
    import re
    assert re.match(r'\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2}', date_original)

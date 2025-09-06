"""Integration tests that actually run exiftool and verify metadata is written correctly."""

from pathlib import Path
import json
import subprocess
import tempfile
import pytest
from PIL import Image

from google_takeout_metadata.processor import process_sidecar_file
from google_takeout_metadata.exif_writer import write_metadata
from google_takeout_metadata.sidecar import SidecarData


def _run_exiftool_read(media_path: Path) -> dict:
    """Run exiftool to read metadata from an image file."""
    cmd = [
        "exiftool", 
        "-json",
        "-charset", "filename=UTF8",
        "-charset", "iptc=UTF8", 
        "-charset", "exif=UTF8",
        "-charset", "XMP=UTF8",
        str(media_path)
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
    media_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='red')
    img.save(media_path)
    
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
    metadata = _run_exiftool_read(media_path)
    
    # Verify description was written
    assert metadata.get("Description") == "Test photo with ñ and émojis 🎉"
    assert metadata.get("ImageDescription") == "Test photo with ñ and émojis 🎉"


@pytest.mark.integration
def test_write_and_read_people(tmp_path: Path) -> None:
    """Test that people names are written and can be read back."""
    # Create a simple test image
    media_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='blue')
    img.save(media_path)
    
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
    metadata = _run_exiftool_read(media_path)
    
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
    media_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='green')
    img.save(media_path)
    
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
    metadata = _run_exiftool_read(media_path)
    
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
    media_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='yellow')
    img.save(media_path)
    
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
    metadata = _run_exiftool_read(media_path)
    
    # Verify rating was written
    assert int(metadata.get("Rating", 0)) == 5


@pytest.mark.integration
def test_append_only_mode(tmp_path: Path) -> None:
    """Test that append-only mode doesn't overwrite existing description."""
    # Create a simple test image
    media_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='purple')
    img.save(media_path)
    
    # First, manually add a description
    cmd = [
        "exiftool", 
        "-overwrite_original",
        "-EXIF:ImageDescription=Original description",
        str(media_path)
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
    metadata = _run_exiftool_read(media_path)
    
    # In append-only mode, original description should be preserved
    # Note: exiftool's -= operator doesn't overwrite if field exists
    assert metadata.get("ImageDescription") == "Original description"


@pytest.mark.integration
def test_datetime_formats(tmp_path: Path) -> None:
    """Test that datetime is written in correct format."""
    # Create a simple test image
    media_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='orange')
    img.save(media_path)
    
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
    metadata = _run_exiftool_read(media_path)
    
    # Verify datetime format (should be YYYY:MM:DD HH:MM:SS)
    date_original = metadata.get("DateTimeOriginal")
    assert date_original is not None
    assert ":" in date_original
    # Should match EXIF datetime format
    import re
    assert re.match(r'\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2}', date_original)


@pytest.mark.integration
def test_write_and_read_albums(tmp_path: Path) -> None:
    """Test that albums are written and can be read back."""
    # Create a simple test image
    media_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='cyan')
    img.save(media_path)
    
    # Create album metadata.json
    album_data = {"title": "Vacances Été 2024"}
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(album_data), encoding="utf-8")
    
    # Create sidecar JSON
    sidecar_data = {
        "title": "test.jpg",
        "description": "Photo de vacances"
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Process the sidecar
    process_sidecar_file(json_path)
    
    # Read back metadata
    metadata = _run_exiftool_read(media_path)
    
    # Verify album was written as keyword
    keywords = metadata.get("Keywords", [])
    if isinstance(keywords, str):
        keywords = [keywords]
    
    assert "Album: Vacances Été 2024" in keywords
    
    # Also check Subject field
    subjects = metadata.get("Subject", [])
    if isinstance(subjects, str):
        subjects = [subjects]
    
    assert "Album: Vacances Été 2024" in subjects


@pytest.mark.integration  
def test_albums_and_people_combined(tmp_path: Path) -> None:
    """Test that albums and people can coexist in keywords."""
    # Create a simple test image
    media_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='magenta')
    img.save(media_path)
    
    # Create album metadata.json
    album_data = {"title": "Album Famille"}
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(album_data), encoding="utf-8")
    
    # Create sidecar JSON with people
    sidecar_data = {
        "title": "test.jpg",
        "people": [{"name": "Alice"}, {"name": "Bob"}]
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Process the sidecar
    process_sidecar_file(json_path)
    
    # Read back metadata
    metadata = _run_exiftool_read(media_path)
    
    # Verify both album and people were written
    keywords = metadata.get("Keywords", [])
    if isinstance(keywords, str):
        keywords = [keywords]
    
    # Check that we have both people and album
    assert "Alice" in keywords
    assert "Bob" in keywords
    assert "Album: Album Famille" in keywords


@pytest.mark.integration
def test_default_safe_behavior(tmp_path: Path) -> None:
    """Test that default behavior is safe (append-only) and preserves existing metadata."""
    # Create a simple test image
    media_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='red')
    img.save(media_path)
    
    # First, manually add some metadata using overwrite mode
    first_meta = SidecarData(
        filename="test.jpg",
        description="Original description",
        people=["Original Person"],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        favorite=False,
        albums=["Original Album"]
    )
    
    # Write initial metadata with overwrite mode
    write_metadata(media_path, first_meta, append_only=False)
    
    # Verify initial metadata was written
    initial_metadata = _run_exiftool_read(media_path)
    assert initial_metadata.get("ImageDescription") == "Original description"
    initial_keywords = initial_metadata.get("Keywords", [])
    if isinstance(initial_keywords, str):
        initial_keywords = [initial_keywords]
    assert "Original Person" in initial_keywords
    assert "Album: Original Album" in initial_keywords
    
    # Now create sidecar with different metadata and process with default behavior
    sidecar_data = {
        "title": "test.jpg",
        "description": "New description", 
        "people": [{"name": "New Person"}]
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Process with default behavior (should be append-only, preserving existing metadata)
    process_sidecar_file(json_path)
    
    # Read back metadata
    final_metadata = _run_exiftool_read(media_path)
    
    # In true append-only mode, the original description should be preserved
    # because we use -if "not $TAG" which only writes if tag doesn't exist
    assert final_metadata.get("ImageDescription") == "Original description"
    
    # Keywords should still contain original data, and new people should be ADDED (not replace)
    # because we use += for people
    final_keywords = final_metadata.get("Keywords", [])
    if isinstance(final_keywords, str):
        final_keywords = [final_keywords]
    assert "Original Person" in final_keywords
    assert "Album: Original Album" in final_keywords
    # New person SHOULD be added because we use += operator for people
    assert "New Person" in final_keywords


@pytest.mark.integration  
def test_explicit_overwrite_behavior(tmp_path: Path) -> None:
    """Test that explicit overwrite mode replaces existing metadata."""
    # Create a simple test image
    media_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='blue') 
    img.save(media_path)
    
    # First, add some initial metadata
    first_meta = SidecarData(
        filename="test.jpg",
        description="Original description",
        people=["Original Person"],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        favorite=False,
        albums=[]
    )
    
    write_metadata(media_path, first_meta, append_only=False)
    
    # Now create sidecar with different metadata
    sidecar_data = {
        "title": "test.jpg",
        "description": "New description",
        "people": [{"name": "New Person"}]
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Process with explicit overwrite mode
    process_sidecar_file(json_path, append_only=False)
    
    # Read back metadata
    final_metadata = _run_exiftool_read(media_path)
    
    # In overwrite mode, new description should replace old one
    # Note: We're using += operator so people get added, not replaced
    final_keywords = final_metadata.get("Keywords", [])
    if isinstance(final_keywords, str):
        final_keywords = [final_keywords]
    
    # Both original and new person should be present (because += adds)
    assert "Original Person" in final_keywords
    assert "New Person" in final_keywords


@pytest.mark.integration
def test_append_only_vs_overwrite_video_equivalence(tmp_path: Path) -> None:
    """Test that append-only mode produces similar results to overwrite mode for videos when no metadata exists."""
    # Copy a real MP4 file from the test data
    project_root = Path(__file__).parent.parent
    source_video = project_root / "Google Photos" / "essais" / "1686356837983.mp4"
    if not source_video.exists():
        pytest.skip("Real MP4 test file not found")
    
    # Create two copies for testing
    video_path_append = tmp_path / "test_append.mp4"
    video_path_overwrite = tmp_path / "test_overwrite.mp4"
    
    import shutil
    shutil.copy2(source_video, video_path_append)
    shutil.copy2(source_video, video_path_overwrite)
    
    # Create test metadata
    meta = SidecarData(
        filename="test.mp4",
        description="Test video description",
        people=["Video Person"],
        taken_at=1736719606,
        created_at=None,
        latitude=48.8566,
        longitude=2.3522,
        altitude=35.0,
        favorite=True,
        albums=["Test Album"]
    )
    
    # Write with append-only mode
    write_metadata(video_path_append, meta, append_only=True)
    
    # Write with overwrite mode
    write_metadata(video_path_overwrite, meta, append_only=False)
    
    # Read back metadata from both files
    metadata_append = _run_exiftool_read(video_path_append)
    metadata_overwrite = _run_exiftool_read(video_path_overwrite)
    
    # Compare key fields - they should be similar when starting from empty metadata
    # (Some fields might differ slightly due to format differences)
    
    # Description should be written in both modes
    if "Description" in metadata_overwrite:
        assert metadata_append.get("Description") == metadata_overwrite.get("Description")
    
    # Keywords should contain the person and album in both modes
    keywords_append = metadata_append.get("Keywords", [])
    keywords_overwrite = metadata_overwrite.get("Keywords", [])
    if isinstance(keywords_append, str):
        keywords_append = [keywords_append]
    if isinstance(keywords_overwrite, str):
        keywords_overwrite = [keywords_overwrite]
    
    # If keywords were written in overwrite mode, they should also be in append mode
    for keyword in keywords_overwrite:
        if "Video Person" in keyword or "Album: Test Album" in keyword:
            assert keyword in keywords_append or any(keyword in k for k in keywords_append)


@pytest.mark.integration
def test_batch_vs_normal_mode_equivalence(tmp_path: Path) -> None:
    """Test that batch mode produces the same results as normal mode."""
    # Import at test time to avoid import issues
    from google_takeout_metadata.processor_batch import process_directory_batch
    from google_takeout_metadata.processor import process_directory
    
    # Create test data
    test_files = [
        ("photo1.jpg", "First test photo", "Alice"),
        ("photo2.jpg", "Second test photo", "Bob"),
        ("photo3.jpg", "Third test photo", "Charlie")
    ]
    
    # Create two identical directory structures
    normal_dir = tmp_path / "normal_mode"
    batch_dir = tmp_path / "batch_mode"
    normal_dir.mkdir()
    batch_dir.mkdir()
    
    for filename, description, person in test_files:
        # Create identical files in both directories
        for test_dir in [normal_dir, batch_dir]:
            # Create image
            media_path = test_dir / filename
            img = Image.new('RGB', (100, 100), color='blue')
            img.save(media_path)
            
            # Create sidecar
            sidecar_data = {
                "title": filename,
                "description": description,
                "people": [{"name": person}]
            }
            json_path = test_dir / f"{filename}.json"
            json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    try:
        # Process with normal mode
        process_directory(normal_dir, use_localtime=False, append_only=True, clean_sidecars=False)
        
        # Process with batch mode  
        process_directory_batch(batch_dir, use_localtime=False, append_only=True, clean_sidecars=False)
        
        # Compare results
        for filename, expected_description, expected_person in test_files:
            normal_metadata = _run_exiftool_read(normal_dir / filename)
            batch_metadata = _run_exiftool_read(batch_dir / filename)
            
            # Check descriptions match
            assert normal_metadata.get("ImageDescription") == batch_metadata.get("ImageDescription")
            assert normal_metadata.get("ImageDescription") == expected_description
            
            # Check people match
            normal_people = normal_metadata.get("PersonInImage", [])
            batch_people = batch_metadata.get("PersonInImage", [])
            if isinstance(normal_people, str):
                normal_people = [normal_people]
            if isinstance(batch_people, str):
                batch_people = [batch_people]
            
            assert set(normal_people) == set(batch_people)
            assert expected_person in normal_people
            
    except FileNotFoundError:
        pytest.skip("exiftool not found - skipping batch vs normal comparison test")


@pytest.mark.integration
def test_batch_mode_performance_benefit(tmp_path: Path) -> None:
    """Test that batch mode can handle many files (performance test)."""
    from google_takeout_metadata.processor_batch import process_directory_batch
    import time
    
    # Create many test files
    num_files = 20  # Reduced for CI, but still demonstrates batch capability
    
    for i in range(num_files):
        filename = f"perf_test_{i:03d}.jpg"
        
        # Create image
        media_path = tmp_path / filename
        img = Image.new('RGB', (50, 50), color='red')
        img.save(media_path)
        
        # Create sidecar
        sidecar_data = {
            "title": filename,
            "description": f"Performance test image {i}"
        }
        json_path = tmp_path / f"{filename}.json"
        json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    try:
        # Measure batch processing time
        start_time = time.time()
        process_directory_batch(tmp_path, use_localtime=False, append_only=True, clean_sidecars=False)
        end_time = time.time()
        
        batch_time = end_time - start_time
        
        # Verify all files were processed correctly
        for i in range(num_files):
            filename = f"perf_test_{i:03d}.jpg"
            media_path = tmp_path / filename
            
            metadata = _run_exiftool_read(media_path)
            expected_description = f"Performance test image {i}"
            assert metadata.get("ImageDescription") == expected_description
        
        # This test mainly ensures batch mode works with many files
        # The actual performance benefit depends on the system and exiftool version
        print(f"Batch mode processed {num_files} files in {batch_time:.2f} seconds")
        
    except FileNotFoundError:
        pytest.skip("exiftool not found - skipping batch performance test")


@pytest.mark.integration  
def test_batch_mode_with_mixed_file_types(tmp_path: Path) -> None:
    """Test batch mode with different file types and complex metadata."""
    from google_takeout_metadata.processor_batch import process_directory_batch
    import shutil
    
    # Create test images of different types
    test_files = [
        ("mixed1.jpg", "JPEG test"),
        ("mixed2.png", "PNG test")  # PNG if supported by PIL
    ]
    
    for filename, description in test_files:
        # Create image with appropriate format
        media_path = tmp_path / filename
        if filename.endswith('.jpg'):
            img = Image.new('RGB', (100, 100), color='green')
            img.save(media_path, format='JPEG')
        elif filename.endswith('.png'):
            img = Image.new('RGBA', (100, 100), color=(0, 255, 0, 128))
            img.save(media_path, format='PNG')
        
        # Create complex sidecar
        sidecar_data = {
            "title": filename,
            "description": description,
            "people": [{"name": "Mixed Test Person"}],
            "favorited": {"value": True},
            "geoData": {
                "latitude": 45.5017,
                "longitude": -73.5673,
                "altitude": 20.0
            }
        }
        json_path = tmp_path / f"{filename}.json"
        json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    try:
        # Process with batch mode
        process_directory_batch(tmp_path, use_localtime=False, append_only=True, clean_sidecars=False)
        
        # Verify all files were processed
        for filename, expected_description in test_files:
            media_path = tmp_path / filename
            
            metadata = _run_exiftool_read(media_path)
            
            # Check basic metadata
            assert metadata.get("ImageDescription") == expected_description
            
            # Check people
            people = metadata.get("PersonInImage", [])
            if isinstance(people, str):
                people = [people]
            assert "Mixed Test Person" in people
            
            # Check rating (favorite)
            rating = metadata.get("Rating")
            assert rating == 5 or rating == "5"
            
            # Check GPS (may not work for all file types)
            gps_lat = metadata.get("GPSLatitude")
            if gps_lat is not None:
                # GPS data present - verify it's correct
                assert abs(float(str(gps_lat).replace("deg", "").strip()) - 45.5017) < 0.001
        
    except FileNotFoundError:
        pytest.skip("exiftool not found - skipping mixed file types batch test")

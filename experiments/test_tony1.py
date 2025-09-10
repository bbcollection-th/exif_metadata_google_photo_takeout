import subprocess
import tempfile
import shutil
from pathlib import Path

def run_exiftool_command(cmd_args, media_path):
    cmd = ["exiftool", "-overwrite_original", "-charset", "filename=UTF8", str(media_path)]
    cmd.extend(cmd_args)
    subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30, encoding='utf-8')

def read_exif_tag(media_path, tag):
    cmd = ["exiftool", "-s", "-s", "-s", tag, str(media_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, encoding='utf-8')
    if result.returncode == 0 and result.stdout.strip():
        return [p.strip() for p in result.stdout.strip().split(',')]
    return []

# Use existing test asset instead of creating a temporary file
test_assets_dir = Path(__file__).parent.parent / "test_assets"
if __name__ == "__main__":
    test_image_original = test_assets_dir / "test_clean.jpg"

    with tempfile.TemporaryDirectory() as temp_dir:
        test_image = Path(temp_dir) / "test_duplicate.jpg"
        # Copy the clean test image to temp directory
        shutil.copy2(test_image_original, test_image)

        # Test 1: Add duplicates in a single command
        print("--- Test 1: Add duplicates in a single command ---")
        run_exiftool_command(
            ["-XMP-dc:Subject=apple", "-XMP-dc:Subject+=banana", "-XMP-dc:Subject+=apple"],
            test_image,
        )
        subjects = read_exif_tag(test_image, "XMP-dc:Subject")
        print(f"Subjects after adding duplicates in one command: {subjects}")
        # Expected: ['apple', 'banana'] or ['apple', 'banana', 'apple'] depending on exiftool's internal deduplication
        # The test_hybrid_approach.py implies it should be deduplicated.
        # Test 2: Add duplicates in separate commands (simulating multiple runs)
        print("--- Test 2: Add duplicates in separate commands ---")
        # Clear previous subjects
        run_exiftool_command(["-XMP-dc:Subject="], test_image)
        run_exiftool_command(["-XMP-dc:Subject+=orange"], test_image)
        run_exiftool_command(["-XMP-dc:Subject+=grape"], test_image)
        run_exiftool_command(["-XMP-dc:Subject+=orange"], test_image) # Add duplicate again
        subjects = read_exif_tag(test_image, "XMP-dc:Subject")
        print(f"Subjects after adding duplicates in separate commands: {subjects}")
        # Expected: ['orange', 'grape', 'orange'] if no deduplication, or ['orange', 'grape'] if deduplicated.
    # Expected: ['orange', 'grape', 'orange'] if no deduplication, or ['orange', 'grape'] if deduplicated.

        # Test 3: Add duplicates with -api nodups
        print("--- Test 3: Add duplicates with -api nodups ---")
        run_exiftool_command(["-XMP-dc:Subject="], test_image) # Clear
        run_exiftool_command(["-XMP-dc:Subject+=kiwi", "-XMP-dc:Subject+=mango", "-XMP-dc:Subject+=kiwi", "-api", "nodups=1"], test_image)
        subjects = read_exif_tag(test_image, "XMP-dc:Subject")
        print(f"Subjects after adding duplicates with -api nodups: {subjects}")

        # Test 4: Add duplicates in separate commands with -api nodups
        print("--- Test 4: Add duplicates in separate commands with -api nodups ---")
        run_exiftool_command(["-XMP-dc:Subject="], test_image) # Clear
        run_exiftool_command(["-XMP-dc:Subject+=pear", "-api", "nodups=1"], test_image)
        run_exiftool_command(["-XMP-dc:Subject+=apple", "-api", "nodups=1"], test_image)
        run_exiftool_command(["-XMP-dc:Subject+=pear", "-api", "nodups=1"], test_image) # Add duplicate again
        subjects = read_exif_tag(test_image, "XMP-dc:Subject")
        print(f"Subjects after adding duplicates in separate commands with -api nodups: {subjects}")
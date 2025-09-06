#!/usr/bin/env python3
"""
Test script to demonstrate that append-only mode now properly handles video-specific metadata.

This script shows the fix for the issue where append-only mode (which is now the default) 
only wrote basic EXIF date fields but not QuickTime-specific video fields.
"""

import json
import tempfile
import shutil
from pathlib import Path

from src.google_takeout_metadata.exif_writer import write_metadata, build_exiftool_args
from src.google_takeout_metadata.sidecar import SidecarData


def test_video_metadata_append_only():
    """Demonstrate that append-only mode now generates video-specific arguments."""
    
    print("=== Testing Video Metadata Generation in Append-Only Mode ===\n")
    
    # Create sample video metadata
    meta = SidecarData(
        filename="test_video.mp4",
        description="Test video description",
        people=["Alice", "Bob"],
        taken_at=1736719606,
        created_at=None,
        latitude=48.8566,
        longitude=2.3522,
        altitude=35.0,
        favorite=True,
        albums=["Vacation 2024"]
    )
    
    video_path = Path("test_video.mp4")
    
    print("1. Testing build_exiftool_args for video in append-only mode:")
    args = build_exiftool_args(meta, video_path, append_only=True)
    
    # Check for video-specific QuickTime fields
    quicktime_create_args = [arg for arg in args if "QuickTime:CreateDate" in arg]
    quicktime_modify_args = [arg for arg in args if "QuickTime:ModifyDate" in arg]
    keys_description_args = [arg for arg in args if "Keys:Description" in arg]
    keys_location_args = [arg for arg in args if "Keys:Location" in arg]
    quicktime_gps_args = [arg for arg in args if "QuickTime:GPSCoordinates" in arg]
    
    print(f"   ✓ QuickTime:CreateDate arguments: {quicktime_create_args}")
    print(f"   ✓ QuickTime:ModifyDate arguments: {quicktime_modify_args}")
    print(f"   ✓ Keys:Description arguments: {keys_description_args}")
    print(f"   ✓ Keys:Location arguments: {keys_location_args}")
    print(f"   ✓ QuickTime:GPSCoordinates arguments: {quicktime_gps_args}")
    
    print("\n2. Testing that conditional logic is used (-if clauses):")
    if_args = [arg for arg in args if arg == "-if"]
    conditional_args = []
    for i, arg in enumerate(args):
        if arg == "-if" and i + 1 < len(args):
            conditional_args.append(args[i + 1])
    
    video_conditional_args = [arg for arg in conditional_args if any(field in arg for field in [
        "QuickTime:CreateDate", "QuickTime:ModifyDate", "Keys:Description", 
        "Keys:Location", "QuickTime:GPSCoordinates"
    ])]
    
    print(f"   ✓ Video-specific conditional checks: {video_conditional_args}")
    
    print("\n3. Testing video configuration:")
    api_args = [arg for arg in args if arg == "-api"]
    quicktime_utc_args = [arg for arg in args if "QuickTimeUTC=1" in arg]
    print(f"   ✓ API configuration: {api_args}")
    print(f"   ✓ QuickTimeUTC setting: {quicktime_utc_args}")
    
    # Verify all expected video-specific fields are present
    assert quicktime_create_args, "QuickTime:CreateDate should be included for videos"
    assert quicktime_modify_args, "QuickTime:ModifyDate should be included for videos"
    assert keys_description_args, "Keys:Description should be included for videos"
    assert keys_location_args, "Keys:Location should be included for videos"
    assert quicktime_gps_args, "QuickTime:GPSCoordinates should be included for videos"
    assert api_args, "API configuration should be included for videos"
    assert quicktime_utc_args, "QuickTimeUTC=1 should be set for videos"
    
    print("\n✅ SUCCESS: Append-only mode now properly generates video-specific metadata!")
    print("   This fixes the issue where video timestamps were not being updated")
    print("   in append-only mode, leaving players displaying wrong timestamps.")


def test_comparison_with_image():
    """Compare video args with image args to show the difference."""
    
    print("\n=== Comparison: Video vs Image Arguments ===\n")
    
    meta = SidecarData(
        filename="test.jpg",
        description="Test description",
        people=["Alice"],
        taken_at=1736719606,
        created_at=None,
        latitude=48.8566,
        longitude=2.3522,
        altitude=35.0,
        favorite=True,
        albums=[]
    )
    
    # Image arguments
    image_args = build_exiftool_args(meta, Path("test.jpg"), append_only=True)
    
    # Video arguments  
    meta.filename = "test.mp4"
    video_args = build_exiftool_args(meta, Path("test.mp4"), append_only=True)
    
    # Find video-specific arguments
    video_only_args = []
    for arg in video_args:
        if any(field in arg for field in [
            "QuickTime:", "Keys:", "QuickTimeUTC"
        ]) and arg not in image_args:
            video_only_args.append(arg)
    
    print("Video-specific arguments not present for images:")
    for arg in video_only_args:
        print(f"   • {arg}")
    
    if video_only_args:
        print(f"\n✅ Found {len(video_only_args)} video-specific arguments")
    else:
        print("\n❌ No video-specific arguments found!")


if __name__ == "__main__":
    test_video_metadata_append_only()
    test_comparison_with_image()

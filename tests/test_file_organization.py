#!/usr/bin/env python3
"""Test de la fonctionnalité d'organisation des fichiers."""

import tempfile
import json
import pytest
import shutil
from pathlib import Path
from PIL import Image

from google_takeout_metadata.sidecar import parse_sidecar
from google_takeout_metadata.file_organizer import FileOrganizer, should_organize_file, get_organization_status
from google_takeout_metadata.processor import process_sidecar_file


def test_sidecar_parsing_with_status():
    """Test que le parsing des sidecars extrait bien les statuts archived, inLockedFolder et trashed."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Test fichier normal
        normal_data = {
            "title": "normal.jpg",
            "description": "Fichier normal"
        }
        normal_sidecar = tmp_path / "normal.jpg.json"
        normal_sidecar.write_text(json.dumps(normal_data), encoding="utf-8")
        
        meta = parse_sidecar(normal_sidecar)
        assert not meta.archived
        assert not meta.trashed
        assert not meta.inLockedFolder

        # Test fichier archivé
        archived_data = {
            "title": "archived.jpg",
            "description": "Fichier archivé",
            "archived": True
        }
        archived_sidecar = tmp_path / "archived.jpg.json"
        archived_sidecar.write_text(json.dumps(archived_data), encoding="utf-8")
        
        meta = parse_sidecar(archived_sidecar)
        assert meta.archived
        assert not meta.trashed
        assert not meta.inLockedFolder

        # Test fichier supprimé
        trashed_data = {
            "title": "trashed.jpg",
            "description": "Fichier supprimé",
            "trashed": True
        }
        trashed_sidecar = tmp_path / "trashed.jpg.json"
        trashed_sidecar.write_text(json.dumps(trashed_data), encoding="utf-8")
        
        meta = parse_sidecar(trashed_sidecar)
        assert not meta.archived
        assert meta.trashed
        assert not meta.inLockedFolder

        # Test fichier verrouillé
        inLockedFolder_data = {
            "title": "inLockedFolder.jpg",
            "description": "Fichier verrouillé",
            "inLockedFolder": True
        }
        inLockedFolder_sidecar = tmp_path / "inLockedFolder.jpg.json"
        inLockedFolder_sidecar.write_text(json.dumps(inLockedFolder_data), encoding="utf-8")
        
        meta = parse_sidecar(inLockedFolder_sidecar)
        assert not meta.archived
        assert not meta.trashed
        assert meta.inLockedFolder

        # Test fichier avec les trois statuts (trashed doit l'emporter)
        both_data = {
            "title": "both.jpg",
            "description": "Fichier archivé ET supprimé",
            "archived": True,
            "trashed": True,
            "inLockedFolder": True
        }
        both_sidecar = tmp_path / "both.jpg.json"
        both_sidecar.write_text(json.dumps(both_data), encoding="utf-8")
        
        meta = parse_sidecar(both_sidecar)
        assert meta.archived
        assert meta.trashed
        assert meta.inLockedFolder
        # Vérifier la priorité
        assert get_organization_status(meta) == "trashed"
        
        # Test fichier avec tous les statuts (trashed doit l'emporter)
        all_data = {
            "title": "all.jpg",
            "description": "Fichier avec tous les statuts",
            "archived": True,
            "trashed": True,
            "inLockedFolder": True
        }
        all_sidecar = tmp_path / "all.jpg.json"
        all_sidecar.write_text(json.dumps(all_data), encoding="utf-8")
        
        meta = parse_sidecar(all_sidecar)
        assert meta.archived
        assert meta.trashed
        assert meta.inLockedFolder
        # Vérifier la priorité (trashed > inLockedFolder > archived)
        assert get_organization_status(meta) == "trashed"
        
        print("✅ Test parsing des statuts réussi !")


def test_file_organization_logic():
    """Test de la logique d'organisation des fichiers."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        organizer = FileOrganizer(tmp_path)
        
        # Test fichier normal - pas de déplacement
        from google_takeout_metadata.sidecar import SidecarData
        normal_meta = SidecarData(
            title="normal.jpg",
            description=None,
            people_name=[],
            photoTakenTime_timestamp=None,
            creationTime_timestamp=None,
            geoData_latitude=None,
            geoData_longitude=None,
            geoData_altitude=None
        )
        assert organizer.get_target_directory(normal_meta) is None
        assert not should_organize_file(normal_meta)
        
        # Test fichier archivé
        archived_meta = SidecarData(
            title="archived.jpg",
            description=None,
            people_name=[],
            photoTakenTime_timestamp=None,
            creationTime_timestamp=None,
            geoData_latitude=None,
            geoData_longitude=None,
            geoData_altitude=None,
            city=None,
            state=None,
            country=None,
            place_name=None,
            archived=True
        )
        assert organizer.get_target_directory(archived_meta) == organizer.archive_dir
        assert should_organize_file(archived_meta)
        
        # Test fichier supprimé
        trashed_meta = SidecarData(
            title="trashed.jpg",
            description=None,
            people_name=[],
            photoTakenTime_timestamp=None,
            creationTime_timestamp=None,
            geoData_latitude=None,
            geoData_longitude=None,
            geoData_altitude=None,
            city=None,
            state=None,
            country=None,
            place_name=None,
            trashed=True
        )
        assert organizer.get_target_directory(trashed_meta) == organizer.trash_dir
        assert should_organize_file(trashed_meta)
        
        # Test fichier verrouillé
        inLockedFolder_meta = SidecarData(
            title="inLockedFolder.jpg",
            description=None,
            people_name=[],
            photoTakenTime_timestamp=None,
            creationTime_timestamp=None,
            geoData_latitude=None,
            geoData_longitude=None,
            geoData_altitude=None,
            city=None,
            state=None,
            country=None,
            place_name=None,
            inLockedFolder=True
        )
        assert organizer.get_target_directory(inLockedFolder_meta) == organizer.inLockedFolder_dir
        assert should_organize_file(inLockedFolder_meta)

        # Test priorité: trashed l'emporte sur inLockedFolder qui l'emporte sur archived
        both_meta = SidecarData(
            title="both.jpg",
            description=None,
            people_name=[],
            photoTakenTime_timestamp=None,
            creationTime_timestamp=None,
            geoData_latitude=None,
            geoData_longitude=None,
            geoData_altitude=None,
            city=None,
            state=None,
            country=None,
            place_name=None,
            archived=True,
            inLockedFolder=True,
            trashed=True
        )
        assert organizer.get_target_directory(both_meta) == organizer.trash_dir
        assert should_organize_file(both_meta)
        
        # Test priorité: trashed > inLockedFolder > archived
        all_meta = SidecarData(
            title="all.jpg",
            description=None,
            people_name=[],
            photoTakenTime_timestamp=None,
            creationTime_timestamp=None,
            geoData_latitude=None,
            geoData_longitude=None,
            geoData_altitude=None,
            city=None,
            state=None,
            country=None,
            place_name=None,
            archived=True,
            trashed=True,
            inLockedFolder=True
        )
        assert organizer.get_target_directory(all_meta) == organizer.trash_dir
        assert should_organize_file(all_meta)
        
        # Test priorité: inLockedFolder > archived
        inLockedFolder_archived_meta = SidecarData(
            title="inLockedFolder_archived.jpg",
            description=None,
            people_name=[],
            photoTakenTime_timestamp=None,
            creationTime_timestamp=None,
            geoData_latitude=None,
            geoData_longitude=None,
            geoData_altitude=None,
            city=None,
            state=None,
            country=None,
            place_name=None,
            archived=True,
            inLockedFolder=True
        )
        assert organizer.get_target_directory(inLockedFolder_archived_meta) == organizer.inLockedFolder_dir
        assert should_organize_file(inLockedFolder_archived_meta)
        
        # Test get_organization_status pour le cas inLockedFolder + archived
        assert get_organization_status(inLockedFolder_archived_meta) == "inLockedFolder"
        
        print("✅ Test logique d'organisation réussi !")


@pytest.mark.integration
def test_file_organization_end_to_end():
    """Test end-to-end de l'organisation des fichiers."""
    # Vérifier que exiftool est installé
    if not shutil.which("exiftool"):
        pytest.skip("exiftool not installed")
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Créer une image de test
        img_path = tmp_path / "archived_photo.jpg"
        img = Image.new('RGB', (100, 100), color='blue')
        img.save(img_path)
        
        # Créer un sidecar pour fichier archivé
        sidecar_data = {
            "title": "archived_photo.jpg",
            "description": "Photo archivée",
            "archived": True
        }
        sidecar_path = tmp_path / "archived_photo.jpg.json"
        sidecar_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
        
        # Vérifier que les fichiers existent initialement
        assert img_path.exists()
        assert sidecar_path.exists()
        
        # Traiter avec organisation
        process_sidecar_file(sidecar_path, use_localTime=True, organize_files=True, immediate_delete=False, geocode=False)

        # Vérifier que les répertoires ont été créés
        archive_dir = tmp_path / "_Archive"
        assert archive_dir.exists()
        
        # Vérifier que les fichiers ont été déplacés
        moved_img = archive_dir / "archived_photo.jpg"
        moved_sidecar = archive_dir / "OK_archived_photo.jpg.json"
        
        assert moved_img.exists()
        assert moved_sidecar.exists()
        assert not img_path.exists()  # Fichier original déplacé
        
        print("✅ Test end-to-end d'organisation réussi !")


if __name__ == "__main__":
    # Vérifier que exiftool est installé pour les tests d'intégration
    if not shutil.which("exiftool"):
        print("⚠️ exiftool not installed, skipping integration tests")
    else:
        test_sidecar_parsing_with_status()
        test_file_organization_logic() 
        test_file_organization_end_to_end()
        print("\n🎉 Tous les tests d'organisation réussis !")

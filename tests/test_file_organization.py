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
    """Test que le parsing des sidecars extrait bien les statuts archived, locked et trashed."""
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
        assert not meta.locked

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
        assert not meta.locked

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
        assert not meta.locked

        # Test fichier verrouillé
        locked_data = {
            "title": "locked.jpg",
            "description": "Fichier verrouillé",
            "inLockedFolder": True
        }
        locked_sidecar = tmp_path / "locked.jpg.json"
        locked_sidecar.write_text(json.dumps(locked_data), encoding="utf-8")
        
        meta = parse_sidecar(locked_sidecar)
        assert not meta.archived
        assert not meta.trashed
        assert meta.locked

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
        assert meta.locked
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
        assert meta.locked
        # Vérifier la priorité (trashed > locked > archived)
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
            filename="normal.jpg",
            description=None,
            people=[],
            taken_at=None,
            created_at=None,
            latitude=None,
            longitude=None,
            altitude=None
        )
        assert organizer.get_target_directory(normal_meta) is None
        assert not should_organize_file(normal_meta)
        
        # Test fichier archivé
        archived_meta = SidecarData(
            filename="archived.jpg",
            description=None,
            people=[],
            taken_at=None,
            created_at=None,
            latitude=None,
            longitude=None,
            altitude=None,
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
            filename="trashed.jpg",
            description=None,
            people=[],
            taken_at=None,
            created_at=None,
            latitude=None,
            longitude=None,
            altitude=None,
            city=None,
            state=None,
            country=None,
            place_name=None,
            trashed=True
        )
        assert organizer.get_target_directory(trashed_meta) == organizer.trash_dir
        assert should_organize_file(trashed_meta)
        
        # Test fichier verrouillé
        locked_meta = SidecarData(
            filename="locked.jpg",
            description=None,
            people=[],
            taken_at=None,
            created_at=None,
            latitude=None,
            longitude=None,
            altitude=None,
            city=None,
            state=None,
            country=None,
            place_name=None,
            locked=True
        )
        assert organizer.get_target_directory(locked_meta) == organizer.locked_dir
        assert should_organize_file(locked_meta)

        # Test priorité: trashed l'emporte sur locked qui l'emporte sur archived
        both_meta = SidecarData(
            filename="both.jpg",
            description=None,
            people=[],
            taken_at=None,
            created_at=None,
            latitude=None,
            longitude=None,
            altitude=None,
            city=None,
            state=None,
            country=None,
            place_name=None,
            archived=True,
            locked=True,
            trashed=True
        )
        assert organizer.get_target_directory(both_meta) == organizer.trash_dir
        assert should_organize_file(both_meta)
        
        # Test priorité: trashed > locked > archived
        all_meta = SidecarData(
            filename="all.jpg",
            description=None,
            people=[],
            taken_at=None,
            created_at=None,
            latitude=None,
            longitude=None,
            altitude=None,
            city=None,
            state=None,
            country=None,
            place_name=None,
            archived=True,
            trashed=True,
            locked=True
        )
        assert organizer.get_target_directory(all_meta) == organizer.trash_dir
        assert should_organize_file(all_meta)
        
        # Test priorité: locked > archived
        locked_archived_meta = SidecarData(
            filename="locked_archived.jpg",
            description=None,
            people=[],
            taken_at=None,
            created_at=None,
            latitude=None,
            longitude=None,
            altitude=None,
            city=None,
            state=None,
            country=None,
            place_name=None,
            archived=True,
            locked=True
        )
        assert organizer.get_target_directory(locked_archived_meta) == organizer.locked_dir
        assert should_organize_file(locked_archived_meta)
        
        # Test get_organization_status pour le cas locked + archived
        assert get_organization_status(locked_archived_meta) == "locked"
        
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
        process_sidecar_file(sidecar_path, organize_files=True)
        
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

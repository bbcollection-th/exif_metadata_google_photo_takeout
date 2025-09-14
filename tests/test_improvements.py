"""Tests unitaires pour les améliorations des statistiques et de la recherche d'albums."""

import json
import pytest
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image

from google_takeout_metadata.processor_batch import process_batch
from google_takeout_metadata.sidecar import find_albums_for_directory
from google_takeout_metadata.statistics import ProcessingStats


class TestProcessingStats:
    """Tests pour la classe ProcessingStats."""
    
    def test_init(self):
        """Test de l'initialisation des statistiques."""
        stats = ProcessingStats()
        assert stats.total_sidecars_found == 0
        assert stats.total_processed == 0
        assert stats.total_failed == 0
        assert stats.total_skipped == 0
        assert stats.images_processed == 0
        assert stats.videos_processed == 0
        assert stats.files_fixed_extension == 0
        assert stats.sidecars_cleaned == 0
        assert stats.failed_files == []
        assert stats.skipped_files == []
        assert stats.fixed_extensions == []
        assert stats.errors_by_type == {}
        assert stats.start_time is None
        assert stats.end_time is None
    
    def test_add_processed_file(self):
        """Test de l'ajout de fichiers traités."""
        stats = ProcessingStats()
        
        # Test image
        stats.add_processed_file(is_image=True)
        assert stats.total_processed == 1
        assert stats.images_processed == 1
        assert stats.videos_processed == 0
        
        # Test vidéo
        stats.add_processed_file(is_image=False)
        assert stats.total_processed == 2
        assert stats.images_processed == 1
        assert stats.videos_processed == 1
    
    def test_add_failed_file(self):
        """Test de l'ajout de fichiers en échec."""
        stats = ProcessingStats()
        test_path = Path("test_file.jpg")
        
        stats.add_failed_file(test_path, "parse_error", "JSON invalide")
        
        assert stats.total_failed == 1
        assert len(stats.failed_files) == 1
        assert stats.failed_files[0] == "test_file.jpg: JSON invalide"
        assert stats.errors_by_type["parse_error"] == 1
        
        # Test comptage des erreurs par type
        stats.add_failed_file(test_path, "parse_error", "Autre erreur JSON")
        assert stats.errors_by_type["parse_error"] == 2
    
    def test_add_skipped_file(self):
        """Test de l'ajout de fichiers ignorés."""
        stats = ProcessingStats()
        test_path = Path("test_file.jpg")
        
        stats.add_skipped_file(test_path, "Fichier déjà traité")
        
        assert stats.total_skipped == 1
        assert len(stats.skipped_files) == 1
        assert stats.skipped_files[0] == "test_file.jpg: Fichier déjà traité"
    
    def test_add_fixed_extension(self):
        """Test de l'ajout de corrections d'extension."""
        stats = ProcessingStats()
        
        stats.add_fixed_extension("image.png", "image.jpg")
        
        assert stats.files_fixed_extension == 1
        assert len(stats.fixed_extensions) == 1
        assert stats.fixed_extensions[0] == "image.png → image.jpg"
    
    def test_success_rate(self):
        """Test du calcul du taux de réussite."""
        stats = ProcessingStats()
        
        # Aucun fichier
        assert stats.success_rate == 0.0
        
        # Quelques fichiers
        stats.total_sidecars_found = 10
        stats.total_processed = 8
        assert stats.success_rate == 80.0
        
        # Tous réussis
        stats.total_processed = 10
        assert stats.success_rate == 100.0
    
    def test_timing(self):
        """Test du système de timing."""
        stats = ProcessingStats()
        
        assert stats.duration is None
        
        stats.start_processing()
        assert stats.start_time is not None
        assert stats.duration is None
        
        stats.end_processing()
        assert stats.end_time is not None
        assert stats.duration is not None
        assert stats.duration >= 0


class TestFindAlbumsForDirectory:
    """Tests pour la fonction find_albums_for_directory améliorée."""
    
    def test_empty_directory(self):
        """Test avec un répertoire vide."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = find_albums_for_directory(Path(temp_dir))
            assert result == []
    
    def test_case_insensitive_metadata_files(self):
        """Test de la gestion insensible à la casse."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Créer des fichiers avec différentes casses
            (temp_path / "METADATA.JSON").write_text('{"title": "Album1"}', encoding='utf-8')
            (temp_path / "métadonnées.json").write_text('{"title": "Album2"}', encoding='utf-8')
            
            result = find_albums_for_directory(temp_path)
            
            # Doit trouver tous les albums
            assert len(result) == 2
            assert "Album1" in result
            assert "Album2" in result
    
    def test_numbered_variations_case_insensitive(self):
        """Test des variations numérotées insensibles à la casse."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Créer des fichiers avec variations numérotées et casses différentes
            (temp_path / "Métadonnées(1).JSON").write_text('{"title": "Album1"}', encoding='utf-8')
            (temp_path / "MÉTADONNÉES(2).json").write_text('{"title": "Album2"}', encoding='utf-8')
            
            result = find_albums_for_directory(temp_path)
            
            assert len(result) == 2
            assert "Album1" in result
            assert "Album2" in result
    
    def test_max_depth_limit(self):
        """Test de la limite de profondeur."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Créer une hiérarchie simple : temp_dir/parent/current
            parent_dir = temp_path / "parent"
            parent_dir.mkdir()
            
            current_dir = parent_dir / "current"
            current_dir.mkdir()
            
            # Ajouter un album au niveau parent
            (parent_dir / "metadata.json").write_text('{"title": "ParentAlbum"}', encoding='utf-8')
            
            # Ajouter un album au niveau racine (temp_dir)
            (temp_path / "métadonnées.json").write_text('{"title": "RootAlbum"}', encoding='utf-8')

            # Test avec max_depth=2 (permet de vérifier current_dir et parent_dir)
            result = find_albums_for_directory(current_dir, max_depth=2)
            assert "ParentAlbum" in result
            assert "RootAlbum" not in result  # temp_dir est à depth=2, donc exclu
            
            # Test avec max_depth=3 (permet de vérifier current_dir, parent_dir et temp_dir)
            result_full = find_albums_for_directory(current_dir, max_depth=3)
            assert "ParentAlbum" in result_full
            assert "RootAlbum" in result_full
            
            # Test avec max_depth=1 (ne vérifie que current_dir)
            result_limited = find_albums_for_directory(current_dir, max_depth=1)
            assert len(result_limited) == 0  # pas d'album dans current_dir
    
    def test_takeout_marker_detection(self):
        """Test de la détection des répertoires marqueurs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Créer une hiérarchie avec marqueur
            root_dir = temp_path / "root"
            root_dir.mkdir()
            
            takeout_dir = root_dir / "mon-takeout" 
            takeout_dir.mkdir()
            
            photos_dir = takeout_dir / "photos"
            photos_dir.mkdir()
            
            # Ajouter un album au niveau root (plus haut que le marqueur)
            (root_dir / "metadata.json").write_text('{"title": "RootAlbum"}', encoding='utf-8')
            
            result = find_albums_for_directory(photos_dir)
            
            # Doit s'arrêter au marqueur et ne pas remonter jusqu'au root
            assert "RootAlbum" not in result
    
    def test_order_preservation(self):
        """Test de la préservation de l'ordre de priorité."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Créer une hiérarchie avec albums à différents niveaux
            level1 = temp_path / "level1"
            level1.mkdir()
            
            # Album au niveau courant (priorité haute)
            (temp_path / "metadata.json").write_text('{"title": "CurrentLevel"}', encoding='utf-8')
            
            # Album au niveau parent (priorité basse)
            (level1 / "métadonnées.json").write_text('{"title": "ParentLevel"}', encoding='utf-8')

            result = find_albums_for_directory(temp_path)
            
            # L'album du niveau courant doit être en premier
            assert result[0] == "CurrentLevel"
    
    def test_error_handling(self):
        """Test de la gestion d'erreurs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Créer un fichier JSON invalide
            (temp_path / "metadata.json").write_text('{"invalid": json}', encoding='utf-8')
            
            # Créer un fichier JSON valide
            (temp_path / "album_metadata.json").write_text('{"title": "ValidAlbum"}', encoding='utf-8')
            # Patcher le logger pour capturer les erreurs
            with patch('google_takeout_metadata.sidecar.logger') as mock_logger:
                mock_logger.error = lambda msg: None  # Ignorer les erreurs dans le test
            # La fonction doit continuer malgré l'erreur
            result = find_albums_for_directory(temp_path)
            
            # Doit trouver l'album valide
            assert "ValidAlbum" in result

    @patch('google_takeout_metadata.sidecar.logger')
    def test_debug_logging(self, mock_logger):
        """Test des logs debug."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Créer une hiérarchie avec marqueur et album au-dessus
            root_dir = temp_path / "root"
            root_dir.mkdir()
            
            takeout_dir = root_dir / "Google Photos"  # Un marqueur sûr
            takeout_dir.mkdir()
            
            photos_dir = takeout_dir / "photos"
            photos_dir.mkdir()
            
            # Ajouter un album au niveau root pour forcer la remontée
            (root_dir / "metadata.json").write_text('{"title": "RootAlbum"}', encoding='utf-8')
            
            find_albums_for_directory(photos_dir)
            
            # Vérifier que le debug a été appelé (pour n'importe quel message debug)
            assert mock_logger.debug.called, "Aucun appel au logger.debug détecté"
            
            # Vérifier les appels debug pour trouver celui du marqueur
            debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
            
            # Chercher un message contenant "marqueur"
            marker_calls = [call for call in debug_calls if "marqueur" in call.lower()]
            assert len(marker_calls) > 0, f"Pas de log marqueur trouvé dans: {debug_calls}"
            calls = [call for call in mock_logger.debug.call_args_list 
                    if "répertoire marqueur" in str(call)]
            assert len(calls) > 0


@pytest.mark.integration 
def test_batch_sidecar_cleanup_with_real_failure(tmp_path: Path) -> None:
    """Tester que les sidecars NE SONT PAS supprimés quand exiftool échoue vraiment (erreur grave).
    
    LOGIQUE MÉTIER: On ne supprime le sidecar QUE si le traitement exiftool a réussi.
    Un échec exiftool signifie que les métadonnées n'ont pas été appliquées -> garder le sidecar pour retry ultérieur.
    """
    
    # Créer une image de test
    media_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='blue')
    img.save(media_path)
    
    # Créer le sidecar JSON avec des arguments invalides qui vont causer une vraie erreur exiftool
    sidecar_data = {
        "title": "test.jpg",
        "description": "Test description"
    }
    json_path = tmp_path / "test.jpg.supplemental-metadata.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Vérifier que le sidecar existe avant traitement
    assert json_path.exists()
    
    # Créer un lot avec des arguments invalides qui causeront un échec exiftool
    # Utilisons un fichier inexistant pour garantir un échec
    non_existent_file = tmp_path / "non_existent.jpg"
    invalid_args = ["-Comment=Test"]  # Arguments valides mais fichier inexistant
    batch = [(non_existent_file, json_path, invalid_args)]
    
    # Traiter le lot avec suppression immédiate activée (immediate_delete=True)
    # Ceci devrait échouer à cause des arguments invalides
    result = process_batch(batch, immediate_delete=True, efile_dir=tmp_path)

    # Vérifier que le traitement a échoué
    assert result == 0, "Le traitement aurait dû échouer avec des arguments invalides"
    
    # CORRECTION: Le sidecar ne doit PAS être supprimé car le traitement a échoué
    assert json_path.exists(), "Le sidecar ne doit PAS être supprimé si exiftool échoue - il faut le garder pour retry"


@pytest.mark.integration
def test_batch_sidecar_cleanup_with_condition_success(tmp_path: Path) -> None:
    """Tester que les sidecars SONT supprimés quand 'files failed condition' en mode append-only.
    
    CLARIFICATION: 'files failed condition' en mode append-only n'est PAS un échec exiftool,
    c'est le comportement normal quand les métadonnées existent déjà. Dans ce cas, on peut supprimer le sidecar.
    """
    
    # Créer une image de test
    media_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='blue')
    img.save(media_path)
    
    # Ajouter des métadonnées existantes (description EXIF)
    try:
        subprocess.run([
            "exiftool", "-overwrite_original",
            "-EXIF:ImageDescription=Existing description",
            str(media_path)
        ], capture_output=True, text=True, check=True, timeout=30)
    except FileNotFoundError:
        pytest.skip("exiftool introuvable - skipping integration test")
    
    # Créer le sidecar JSON avec une description (qui causera "files failed condition" en mode append-only)
    sidecar_data = {
        "title": "test.jpg", 
        "description": "New description that should not overwrite existing"
    }
    json_path = tmp_path / "test.jpg.supplemental-metadata.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Vérifier que le sidecar existe avant traitement
    assert json_path.exists()
    
    # Traiter avec process_sidecar_file en mode append-only (comportement normal)
    from google_takeout_metadata.processor import process_sidecar_file
    process_sidecar_file(json_path, use_localTime=False, immediate_delete=True, organize_files=False, geocode=False)
    
    # Vérifier que le sidecar a été supprimé car le traitement a "réussi" 
    # (même si condition failed, c'est le comportement normal en append-only)
    assert not json_path.exists(), "Le sidecar doit être supprimé après traitement append-only, même avec 'condition failed'"


def test_batch_cleanup_logic_unit() -> None:
    """Test unitaire pour vérifier la logique de nettoyage en cas de 'files failed condition'."""
    # Ce test vérifie que notre modification de code est cohérente
    # Il ne teste pas exiftool mais la logique interne
    
    from google_takeout_metadata.processor_batch import process_batch
    import tempfile
    from pathlib import Path
    import json
    from unittest.mock import patch
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Créer des fichiers factices
        media_path = tmp_path / "test.jpg"
        media_path.write_text("fake image content")
        
        json_path = tmp_path / "test.jpg.supplemental-metadata.json"
        sidecar_data = {"title": "test.jpg", "description": "Test description"}
        json_path.write_text(json.dumps(sidecar_data))
        
        batch = [(media_path, json_path, ["-description=test"])]
        
        # Mock subprocess.run pour simuler "files failed condition"
        mock_error = subprocess.CalledProcessError(2, "exiftool")
        mock_error.stderr = "2 files failed condition"
        mock_error.stdout = ""
        
        with patch('google_takeout_metadata.processor_batch.subprocess.run', side_effect=mock_error):
            # Vérifier que le fichier existe avant
            assert json_path.exists()
            
            # Appeler process_batch avec immediate_delete=True
            result = process_batch(batch, immediate_delete=True, efile_dir=tmp_path)
            
            # Vérifier le succès et la suppression
            assert result == 1, "Le batch devrait être considéré comme réussi"
            assert not json_path.exists(), "Le sidecar aurait dû être supprimé même avec 'files failed condition'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

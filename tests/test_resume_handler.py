# Fichier : tests/test_resume_handler.py

"""Tests pour le module de gestion de reprise des traitements."""

from pathlib import Path
from google_takeout_metadata.resume_handler import (
    should_resume, parse_efile_logs, build_resume_batch, 
    cleanup_efile_logs, _read_file_list
)


def test_should_resume_no_logs(tmp_path):
    """Tester qu'aucune reprise n'est détectée sans logs -efile."""
    assert should_resume(tmp_path) is False


def test_should_resume_with_logs(tmp_path):
    """Tester que la reprise est détectée avec des logs -efile."""
    # Créer un fichier de log factice
    error_log = tmp_path / "error_files.txt"
    error_log.write_text("test.jpg\n")
    
    assert should_resume(tmp_path) is True


def test_read_file_list_empty(tmp_path):
    """Tester la lecture d'un fichier de log inexistant."""
    non_existent = tmp_path / "non_existent.txt"
    result = _read_file_list(non_existent)
    assert result == []


def test_read_file_list_with_content(tmp_path):
    """Tester la lecture d'un fichier de log avec contenu."""
    log_file = tmp_path / "test_log.txt"
    log_file.write_text("image1.jpg\nimage2.jpg\n# Commentaire\n  \nimage3.jpg\n")
    
    result = _read_file_list(log_file)
    expected = [Path("image1.jpg"), Path("image2.jpg"), Path("image3.jpg")]
    assert result == expected


def test_parse_efile_logs_no_files(tmp_path):
    """Tester le parsing des logs -efile sans fichiers."""
    error_files, updated_files, unchanged_files, failed_condition_files = parse_efile_logs(tmp_path)
    
    assert error_files == []
    assert updated_files == []
    assert unchanged_files == []
    assert failed_condition_files == []


def test_parse_efile_logs_with_files(tmp_path):
    """Tester le parsing des logs -efile avec des fichiers."""
    # Créer les logs -efile
    (tmp_path / "error_files.txt").write_text("error1.jpg\nerror2.jpg\n")
    (tmp_path / "updated_files.txt").write_text("updated1.jpg\n")
    (tmp_path / "unchanged_files.txt").write_text("unchanged1.jpg\nunchanged2.jpg\n")
    (tmp_path / "failed_condition_files.txt").write_text("failed1.jpg\n")
    
    error_files, updated_files, unchanged_files, failed_condition_files = parse_efile_logs(tmp_path)
    
    assert len(error_files) == 2
    assert len(updated_files) == 1
    assert len(unchanged_files) == 2
    assert len(failed_condition_files) == 1
    
    assert Path("error1.jpg") in error_files
    assert Path("updated1.jpg") in updated_files
    assert Path("unchanged1.jpg") in unchanged_files
    assert Path("failed1.jpg") in failed_condition_files


def test_build_resume_batch_errors_only():
    """Tester la construction d'un lot de reprise en mode erreurs uniquement."""
    error_files = [Path("error1.jpg"), Path("error2.jpg")]
    unchanged_files = [Path("unchanged1.jpg"), Path("unchanged2.jpg")]
    
    result = build_resume_batch(error_files, unchanged_files, resume_mode="errors")
    
    assert result == error_files
    assert Path("unchanged1.jpg") not in result


def test_build_resume_batch_all_mode():
    """Tester la construction d'un lot de reprise en mode complet."""
    error_files = [Path("error1.jpg"), Path("error2.jpg")]
    unchanged_files = [Path("unchanged1.jpg"), Path("unchanged2.jpg")]
    
    result = build_resume_batch(error_files, unchanged_files, resume_mode="all")
    
    expected = error_files + unchanged_files
    assert result == expected


def test_cleanup_efile_logs(tmp_path):
    """Tester le nettoyage des logs -efile."""
    # Créer des logs factices
    log_files = ["error_files.txt", "updated_files.txt", "unchanged_files.txt", "failed_condition_files.txt"]
    for log_file in log_files:
        (tmp_path / log_file).write_text("test content\n")
    
    # Créer un fichier qui ne devrait pas être supprimé
    other_file = tmp_path / "other_file.txt"
    other_file.write_text("keep this\n")
    
    # Nettoyer
    cleanup_efile_logs(tmp_path)
    
    # Vérifier que les logs ont été supprimés
    for log_file in log_files:
        assert not (tmp_path / log_file).exists()
    
    # Vérifier que l'autre fichier existe toujours
    assert other_file.exists()


def test_edge_cases_empty_lists():
    """Tester les cas limites avec des listes vides."""
    result = build_resume_batch([], [], resume_mode="errors")
    assert result == []
    
    result = build_resume_batch([], [], resume_mode="all")
    assert result == []


def test_edge_cases_none_unchanged():
    """Tester les cas limites avec unchanged_files = None."""
    error_files = [Path("error1.jpg")]
    
    result = build_resume_batch(error_files, None, resume_mode="all")
    assert result == error_files
    
    result = build_resume_batch(error_files, None, resume_mode="errors")
    assert result == error_files


def test_log_file_with_unicode_content(tmp_path):
    """Tester la lecture de logs avec contenu Unicode."""
    log_file = tmp_path / "unicode_log.txt"
    log_file.write_text("image_été.jpg\nphoto_naïve.jpg\n北京.jpg\n", encoding='utf-8')
    
    result = _read_file_list(log_file)
    expected = [Path("image_été.jpg"), Path("photo_naïve.jpg"), Path("北京.jpg")]
    assert result == expected

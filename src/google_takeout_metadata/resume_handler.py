# Fichier : src/google_takeout_metadata/resume_handler.py

import logging
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)


def should_resume(output_dir: Path) -> bool:
    """Détecter si des fichiers de log -efile existent pour une reprise.
    
    Args:
        output_dir: Répertoire à vérifier pour les logs -efile
        
    Returns:
        True si des logs -efile existent et qu'une reprise est possible
    """
    log_files = [
        "error_files.txt",
        "unchanged_files.txt", 
        "failed_condition_files.txt",
        "updated_files.txt"
    ]
    
    return any((output_dir / log_file).exists() for log_file in log_files)


def parse_efile_logs(output_dir: Path) -> Tuple[List[Path], List[Path], List[Path], List[Path]]:
    """Parser les logs -efile pour extraire les listes de fichiers.
    
    Args:
        output_dir: Répertoire contenant les logs -efile
        
    Returns:
        Tuple de (error_files, updated_files, unchanged_files, failed_condition_files)
    """
    error_files = _read_file_list(output_dir / "error_files.txt")
    updated_files = _read_file_list(output_dir / "updated_files.txt") 
    unchanged_files = _read_file_list(output_dir / "unchanged_files.txt")
    failed_condition_files = _read_file_list(output_dir / "failed_condition_files.txt")
    
    logger.info(f"📊 Analyse des logs -efile: {len(error_files)} erreurs, "
                f"{len(updated_files)} mis à jour, {len(unchanged_files)} inchangés, "
                f"{len(failed_condition_files)} conditions échouées")
    
    return error_files, updated_files, unchanged_files, failed_condition_files


def build_resume_batch(error_files: List[Path], unchanged_files: List[Path] = None, resume_mode: str = "errors") -> List[Path]:
    """Construire un lot de reprise à partir des logs -efile.
    
    Args:
        error_files: Liste des fichiers en erreur
        unchanged_files: Liste des fichiers inchangés (optionnel)
        resume_mode: Mode de reprise ("errors" ou "all")
        
    Returns:
        Liste des fichiers à retraiter
    """
    files_to_resume = error_files.copy()  # Toujours reprendre les erreurs
    
    if resume_mode == "all" and unchanged_files:
        files_to_resume.extend(unchanged_files)  # Reprendre aussi les inchangés si policy modifiée
        logger.info(f"🔄 Mode reprise complète: {len(files_to_resume)} fichiers à retraiter")
    else:
        logger.info(f"🔄 Mode reprise erreurs: {len(files_to_resume)} fichiers à retraiter")
    
    return files_to_resume


def _read_file_list(log_file: Path) -> List[Path]:
    """Lire une liste de fichiers depuis un log -efile.
    
    Args:
        log_file: Fichier de log à lire
        
    Returns:
        Liste des chemins de fichiers trouvés dans le log
    """
    if not log_file.exists():
        return []
    
    files = []
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):  # Ignorer les commentaires
                    files.append(Path(line))
    except Exception as e:
        logger.warning(f"⚠️ Erreur lors de la lecture de {log_file}: {e}")
    
    return files


def cleanup_efile_logs(output_dir: Path) -> None:
    """Nettoyer les anciens logs -efile après un traitement réussi.
    
    Args:
        output_dir: Répertoire contenant les logs à nettoyer
    """
    log_files = [
        "error_files.txt",
        "unchanged_files.txt", 
        "failed_condition_files.txt",
        "updated_files.txt"
    ]
    
    cleaned = 0
    for log_file in log_files:
        log_path = output_dir / log_file
        if log_path.exists():
            try:
                log_path.unlink()
                cleaned += 1
            except Exception as e:
                logger.warning(f"⚠️ Impossible de nettoyer {log_file}: {e}")
    
    if cleaned > 0:
        logger.info(f"🧹 {cleaned} fichiers de log -efile nettoyés")

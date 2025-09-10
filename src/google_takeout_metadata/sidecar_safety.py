"""
Système de sas de sécurité pour les sidecars JSON.

Ce module implémente un mécanisme de sécurité pour éviter la suppression immédiate
des fichiers sidecar JSON après traitement. Au lieu de supprimer, on renomme
avec un préfixe 'OK_' pour permettre vérification manuelle et rollback.

Workflow:
1. Succès ExifTool → Sidecar renommé avec préfixe 'OK_'
2. Échec ExifTool → Sidecar conservé (pour retry ultérieur)
3. Génération de scripts de nettoyage/rollback pour l'utilisateur
"""

import logging
import os
from pathlib import Path
from typing import List, Tuple, Set
import platform

logger = logging.getLogger(__name__)

# Préfixe pour marquer les sidecars traités avec succès
PROCESSED_PREFIX = "OK_"


def mark_sidecar_as_processed(json_path: Path) -> bool:
    """
    Renomme un sidecar JSON avec le préfixe OK_ pour indiquer qu'il a été traité.
    
    Args:
        json_path: Chemin vers le fichier sidecar JSON
        
    Returns:
        True si le renommage a réussi, False sinon
        
    Example:
        photo.jpg.json → OK_photo.jpg.json
    """
    if not json_path.exists():
        logger.warning(f"Sidecar not found: {json_path}")
        return False
        
    if json_path.name.startswith(PROCESSED_PREFIX):
        logger.debug(f"Sidecar already marked as processed: {json_path}")
        return True
        
    new_name = PROCESSED_PREFIX + json_path.name
    new_path = json_path.parent / new_name
    
    try:
        json_path.rename(new_path)
        logger.info(f"Marked sidecar as processed: {json_path} → {new_path}")
        return True
    except OSError as e:
        logger.error(f"Failed to mark sidecar as processed: {json_path} - {e}")
        return False


def is_sidecar_processed(json_path: Path) -> bool:
    """
    Vérifie si un sidecar a déjà été marqué comme traité.
    
    Args:
        json_path: Chemin vers le fichier sidecar JSON
        
    Returns:
        True si le sidecar est marqué comme traité
    """
    return json_path.name.startswith(PROCESSED_PREFIX)


def get_processed_sidecars(directory: Path) -> List[Path]:
    """
    Trouve tous les sidecars marqués comme traités dans un répertoire.
    
    Args:
        directory: Répertoire à scanner
        
    Returns:
        Liste des chemins vers les sidecars traités
    """
    if not directory.is_dir():
        return []
        
    processed = []
    for file_path in directory.rglob(f"{PROCESSED_PREFIX}*.json"):
        processed.append(file_path)
        
    return processed


def get_original_sidecar_name(processed_path: Path) -> str:
    """
    Récupère le nom original d'un sidecar traité (sans le préfixe).
    
    Args:
        processed_path: Chemin vers un sidecar marqué comme traité
        
    Returns:
        Nom original du sidecar
    """
    if not processed_path.name.startswith(PROCESSED_PREFIX):
        return processed_path.name
        
    return processed_path.name[len(PROCESSED_PREFIX):]


def find_sidecars_to_skip(directory: Path) -> Set[Path]:
    """
    Trouve les sidecars à ignorer lors d'un nouveau traitement.
    
    Retourne les chemins originaux (sans préfixe) des sidecars déjà traités,
    pour que le processeur puisse les ignorer.
    
    Args:
        directory: Répertoire à scanner
        
    Returns:
        Set des chemins vers les sidecars originaux à ignorer
    """
    processed_sidecars = get_processed_sidecars(directory)
    to_skip = set()
    
    for processed_path in processed_sidecars:
        original_name = get_original_sidecar_name(processed_path)
        original_path = processed_path.parent / original_name
        to_skip.add(original_path)
        
    return to_skip


++ b/src/google_takeout_metadata/sidecar_safety.py
@@
from typing import List, Tuple, Set, Optional
@@
def generate_cleanup_script(directory: Path, output_file: Optional[Path] = None) -> Optional[Path]:
     """
     Génère un script pour supprimer définitivement les sidecars traités.
     
     Args:
         directory: Répertoire contenant les sidecars traités
         output_file: Chemin du script à générer (optionnel)
-        
-    Returns:
        
    Returns:
        Chemin vers le script généré, ou None s'il n'y a rien à faire ou en cas d'erreur
     """
     processed_sidecars = get_processed_sidecars(directory)
     
     if not processed_sidecars:
         logger.info("No processed sidecars found for cleanup script")
         return None
        
    # Déterminer le nom et type de script selon l'OS
    is_windows = platform.system() == "Windows"
    script_ext = ".bat" if is_windows else ".sh"
    
    if output_file is None:
        output_file = directory / f"cleanup_processed_sidecars{script_ext}"
        
    script_lines = []
    
    if is_windows:
        script_lines.extend([
            "@echo off",
            "REM Script pour supprimer les sidecars traités avec succès",
            "REM Généré automatiquement - Vérifiez avant exécution !",
            "echo Suppression des sidecars traités...",
            ""
        ])
        
        for sidecar_path in processed_sidecars:
            # Échapper les chemins pour Windows
            escaped_path = str(sidecar_path).replace('"', '""')
            script_lines.append(f'del /f "{escaped_path}"')
            
        script_lines.extend([
            "",
            "echo Nettoyage terminé.",
            "pause"
        ])
    else:
        script_lines.extend([
            "#!/bin/bash",
            "# Script pour supprimer les sidecars traités avec succès",
            "# Généré automatiquement - Vérifiez avant exécution !",
            "echo 'Suppression des sidecars traités...'",
            ""
        ])
        
        for sidecar_path in processed_sidecars:
            # Échapper les chemins pour bash
            escaped_path = str(sidecar_path).replace("'", "'\"'\"'")
            script_lines.append(f"rm -f '{escaped_path}'")
            
        script_lines.extend([
            "",
            "echo 'Nettoyage terminé.'"
        ])
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(script_lines))
            
        # Rendre exécutable sur Unix
        if not is_windows:
            os.chmod(output_file, 0o755)
            
        logger.info(f"Cleanup script generated: {output_file}")
        logger.info(f"Found {len(processed_sidecars)} processed sidecars to clean")
        
        return output_file
        
    except OSError as e:
        logger.error(f"Failed to generate cleanup script: {e}")
        return None


def generate_rollback_script(directory: Path, output_file: Optional[Path] = None) -> Optional[Path]:
    """
    Génère un script pour restaurer les noms originaux des sidecars traités.
    
    Args:
        directory: Répertoire contenant les sidecars traités
        output_file: Chemin du script à générer (optionnel)
        
    Returns:
        Chemin vers le script généré, ou None s'il n'y a rien à faire ou en cas d'erreur
    """
    processed_sidecars = get_processed_sidecars(directory)
    
    if not processed_sidecars:
        logger.info("No processed sidecars found for rollback script")
        return None
        
    # Déterminer le nom et type de script selon l'OS
    is_windows = platform.system() == "Windows"
    script_ext = ".bat" if is_windows else ".sh"
    
    if output_file is None:
        output_file = directory / f"rollback_processed_sidecars{script_ext}"
        
    script_lines = []
    
    if is_windows:
        script_lines.extend([
            "@echo off",
            "REM Script pour restaurer les noms originaux des sidecars",
            "REM Généré automatiquement - Vérifiez avant exécution !",
            "echo Restauration des noms originaux...",
            ""
        ])
        
        for processed_path in processed_sidecars:
            original_name = get_original_sidecar_name(processed_path)
            original_path = processed_path.parent / original_name
            
            # Échapper les chemins pour Windows
            escaped_from = str(processed_path).replace('"', '""')
            escaped_to = str(original_path).replace('"', '""')
            script_lines.append(f'ren "{escaped_from}" "{original_name}"')
            
        script_lines.extend([
            "",
            "echo Rollback terminé.",
            "pause"
        ])
    else:
        script_lines.extend([
            "#!/bin/bash",
            "# Script pour restaurer les noms originaux des sidecars", 
            "# Généré automatiquement - Vérifiez avant exécution !",
            "echo 'Restauration des noms originaux...'",
            ""
        ])
        
        for processed_path in processed_sidecars:
            original_name = get_original_sidecar_name(processed_path)
            original_path = processed_path.parent / original_name
            
            # Échapper les chemins pour bash
            escaped_from = str(processed_path).replace("'", "'\"'\"'")
            escaped_to = str(original_path).replace("'", "'\"'\"'")
            script_lines.append(f"mv '{escaped_from}' '{escaped_to}'")
            
        script_lines.extend([
            "",
            "echo 'Rollback terminé.'"
        ])
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(script_lines))
            
        # Rendre exécutable sur Unix
        if not is_windows:
            os.chmod(output_file, 0o755)
            
        logger.info(f"Rollback script generated: {output_file}")
        logger.info(f"Found {len(processed_sidecars)} processed sidecars to rollback")
        
        return output_file
        
    except OSError as e:
        logger.error(f"Failed to generate rollback script: {e}")
        return None


def generate_scripts_summary(directory: Path) -> Tuple[int, int, List[str]]:
    """
    Génère un résumé des sidecars traités et des actions possibles.
    
    Args:
        directory: Répertoire à analyser
        
    Returns:
        Tuple (nb_processed, nb_pending, messages)
    """
    processed_sidecars = get_processed_sidecars(directory)
    
    # Compter les sidecars en attente (non traités)
    all_sidecars = list(directory.rglob("*.json"))
    pending_sidecars = [s for s in all_sidecars if not is_sidecar_processed(s)]
    
    messages = []
    messages.append("=== Résumé des sidecars ===")
    messages.append(f"Traités avec succès (préfixe {PROCESSED_PREFIX}): {len(processed_sidecars)}")
    messages.append(f"En attente de traitement: {len(pending_sidecars)}")
    
    if processed_sidecars:
        messages.append("")
        messages.append("Actions disponibles:")
        messages.append("1. Générer script de nettoyage (suppression définitive)")
        messages.append("2. Générer script de rollback (restaurer noms originaux)")
        messages.append("3. Relancer le traitement (ignorera automatiquement les fichiers déjà traités)")
    
    return len(processed_sidecars), len(pending_sidecars), messages

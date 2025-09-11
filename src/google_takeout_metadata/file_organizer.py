"""Module de gestion des fichiers archivés et supprimés selon les métadonnées Google Takeout."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional, Tuple

from .sidecar import SidecarData

logger = logging.getLogger(__name__)


class FileOrganizer:
    """Gestionnaire pour organiser les fichiers selon leur statut archive/corbeille."""
    
    def __init__(self, base_directory: Path):
        """
        Initialiser l'organisateur de fichiers.
        
        Args:
            base_directory: Répertoire de base où créer les dossiers d'organisation
        """
        self.base_directory = Path(base_directory)
        self.archive_dir = self.base_directory / "_Archive"
        self.trash_dir = self.base_directory / "_Corbeille"
        self.locked_dir = self.base_directory / "_Verrouillé"
    
    def ensure_directories(self) -> None:
        """Créer les répertoires d'organisation s'ils n'existent pas."""
        self.archive_dir.mkdir(exist_ok=True)
        self.trash_dir.mkdir(exist_ok=True)
        self.locked_dir.mkdir(exist_ok=True)
        logger.debug(f"Répertoires d'organisation créés: {self.archive_dir}, {self.trash_dir}, {self.locked_dir}")
    
    def get_target_directory(self, meta: SidecarData) -> Optional[Path]:
        """
        Déterminer le répertoire cible selon le statut du fichier.
        
        Args:
            meta: Métadonnées du fichier
            
        Returns:
            Chemin du répertoire cible ou None si aucun déplacement nécessaire
            
        Règles de priorité:
        1. Si trashed=True -> Corbeille (priorité absolue)
        2. Si locked=True -> Dossier verrouillé (priorité haute)
        3. Si archived=True -> Archive  
        4. Sinon -> None (pas de déplacement)
        """
        if meta.trashed:
            return self.trash_dir
        elif meta.locked:
            return self.locked_dir
        elif meta.archived:
            return self.archive_dir
        else:
            return None
    
    def move_file_with_sidecar(
        self, 
        media_path: Path, 
        sidecar_path: Path, 
        meta: SidecarData
    ) -> Tuple[Optional[Path], Optional[Path]]:
        """
        Déplacer un fichier média et son sidecar selon le statut.
        
        Args:
            media_path: Chemin du fichier média
            sidecar_path: Chemin du fichier sidecar JSON
            meta: Métadonnées extraites du sidecar
            
        Returns:
            Tuple (nouveau_chemin_media, nouveau_chemin_sidecar) ou (None, None) si pas de déplacement
            
        Raises:
            OSError: En cas d'erreur de déplacement
        """
        target_dir = self.get_target_directory(meta)
        
        if target_dir is None:
            # Pas de déplacement nécessaire
            return None, None
        
        # Créer les répertoires si nécessaire
        self.ensure_directories()
        
        # Calculer les nouveaux chemins
        new_media_path = target_dir / media_path.name
        new_sidecar_path = target_dir / sidecar_path.name
        
        # Gérer les conflits de noms
        new_media_path = self._resolve_name_conflict(new_media_path)
        new_sidecar_path = self._resolve_name_conflict(new_sidecar_path)
        
        try:
            # Déplacer le fichier média
            if media_path.exists():
                shutil.move(str(media_path), str(new_media_path))
                logger.info(f"📁 Déplacé vers {target_dir.name}: {media_path.name} → {new_media_path.name}")
            else:
                new_media_path = None
                logger.warning(f"Fichier média introuvable pour déplacement: {media_path}")
            
            # Déplacer le sidecar
            if sidecar_path.exists():
                shutil.move(str(sidecar_path), str(new_sidecar_path))
                logger.debug(f"Sidecar déplacé: {sidecar_path.name} → {new_sidecar_path.name}")
            else:
                new_sidecar_path = None
                logger.warning(f"Sidecar introuvable pour déplacement: {sidecar_path}")
            
            return new_media_path, new_sidecar_path
            
        except (OSError, shutil.Error) as e:
            logger.error(f"Erreur lors du déplacement de {media_path.name}: {e}")
            raise
    
    def _resolve_name_conflict(self, target_path: Path) -> Path:
        """
        Résoudre les conflits de noms en ajoutant un suffixe numérique.
        
        Args:
            target_path: Chemin cible souhaité
            
        Returns:
            Chemin disponible (avec suffixe si nécessaire)
        """
        if not target_path.exists():
            return target_path
        
        # Générer un nom alternatif avec suffixe numérique
        stem = target_path.stem
        suffix = target_path.suffix
        parent = target_path.parent
        
        counter = 1
        while True:
            new_name = f"{stem}_{counter}{suffix}"
            new_path = parent / new_name
            if not new_path.exists():
                logger.debug(f"Conflit de nom résolu: {target_path.name} → {new_name}")
                return new_path
            counter += 1
            
            # Sécurité: éviter les boucles infinies
            if counter > 1000:
                raise OSError(f"Impossible de résoudre le conflit de nom pour {target_path}")


def should_organize_file(meta: SidecarData) -> bool:
    """
    Vérifier si un fichier doit être organisé selon son statut.
    
    Args:
        meta: Métadonnées du fichier
        
    Returns:
        True si le fichier doit être déplacé
    """
    return meta.trashed or meta.archived or meta.locked


def get_organization_status(meta: SidecarData) -> str:
    """
    Obtenir le statut d'organisation d'un fichier.
    
    Args:
        meta: Métadonnées du fichier
        
    Returns:
        String décrivant le statut ("trashed", "archived", "locked", "normal")
    """
    if meta.trashed:
        return "trashed"
    elif meta.locked:
        return "locked"
    elif meta.archived:
        return "archived"
    else:
        return "normal"

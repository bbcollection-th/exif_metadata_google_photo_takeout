#!/usr/bin/env python3
"""
Utilitaires pour la gestion des assets de test et la préparation d'environnements de test isolés.
"""

import shutil
from pathlib import Path
import tempfile
import subprocess
import json
import pytest


class TestAssetManager:
    """Gestionnaire des assets de test pour garantir des environnements isolés."""
    
    def __init__(self):
        self.assets_dir = Path(__file__).parent.parent / "test_assets"
        
    def copy_clean_asset(self, asset_name: str, dest_path: Path) -> None:
        """
        Copie un asset de test propre vers le chemin de destination.
        Utilise automatiquement la version _original si elle existe.
        """
        # Vérifier d'abord si une version _original existe
        original_name = f"{asset_name}_original"
        original_path = self.assets_dir / original_name
        
        if original_path.exists():
            # Utiliser la version originale propre
            source_path = original_path
        else:
            # Utiliser l'asset standard
            source_path = self.assets_dir / asset_name
            
        if not source_path.exists():
            pytest.skip(f"Asset de test {asset_name} introuvable dans {self.assets_dir}")
            
        # Copier l'asset
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_path)
        
    def create_test_environment(self, temp_dir: Path, assets: list[str]) -> dict[str, Path]:
        """
        Crée un environnement de test isolé avec les assets spécifiés.
        
        Args:
            temp_dir: Répertoire temporaire pour les tests
            assets: Liste des noms d'assets à copier
            
        Returns:
            Dict mapping asset_name -> chemin_copié
        """
        asset_paths = {}
        
        for asset_name in assets:
            dest_path = temp_dir / asset_name
            self.copy_clean_asset(asset_name, dest_path)
            asset_paths[asset_name] = dest_path
            
        return asset_paths
    
    def verify_asset_is_clean(self, asset_path: Path) -> bool:
        """
        Vérifie qu'un asset est vraiment propre (sans métadonnées problématiques).
        """
        try:
            result = subprocess.run([
                "exiftool", "-json", "-charset", "utf8", str(asset_path)
            ], capture_output=True, text=True, check=True)
            
            metadata = json.loads(result.stdout)[0]
            
            # Vérifier l'absence de métadonnées problématiques
            problematic_fields = [
                "Description", "Title", "Label", "Rating", "Keywords", 
                "XMP:Rating", "XMP:Label", "MWG:Description", "IPTC:ObjectName"
            ]
            
            for field in problematic_fields:
                if field in metadata and metadata[field] not in [0, None, ""]:
                    return False
                    
            return True
            
        except (subprocess.CalledProcessError, json.JSONDecodeError, IndexError):
            return False
    
    def ensure_clean_asset(self, asset_name: str) -> Path:
        """
        S'assure qu'un asset est propre. Si ce n'est pas le cas, le restaure depuis _original.
        """
        asset_path = self.assets_dir / asset_name
        
        if not self.verify_asset_is_clean(asset_path):
            # Restaurer depuis _original
            original_path = self.assets_dir / f"{asset_name}_original"
            if original_path.exists():
                shutil.copy2(original_path, asset_path)
                print(f"🔧 Asset {asset_name} restauré depuis la version originale")
            else:
                raise FileNotFoundError(f"Asset {asset_name} contaminé et pas de version _original")
                
        return asset_path


# Instance globale pour faciliter l'usage
test_asset_manager = TestAssetManager()


def create_isolated_test_environment(assets: list[str], temp_dir: Path = None) -> tuple[Path, dict[str, Path]]:
    """
    Fonction de commodité pour créer un environnement de test isolé.
    
    Args:
        assets: Liste des assets à copier
        temp_dir: Répertoire temporaire (créé automatiquement si None)
        
    Returns:
        (temp_dir, dict_asset_paths)
    """
    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp())
        
    asset_paths = test_asset_manager.create_test_environment(temp_dir, assets)
    return temp_dir, asset_paths


def verify_test_environment(asset_paths: dict[str, Path]) -> None:
    """
    Vérifie que tous les assets dans l'environnement de test sont propres.
    """
    for asset_name, asset_path in asset_paths.items():
        if not test_asset_manager.verify_asset_is_clean(asset_path):
            raise AssertionError(f"Asset {asset_name} dans l'environnement de test n'est pas propre")
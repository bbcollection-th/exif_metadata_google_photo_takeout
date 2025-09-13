"""
Configuration loader pour les mappings et stratégies EXIF.
Permet de charger la configuration depuis JSON et .env
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class StrategyConfig:
    """Configuration d'une stratégie d'écriture"""
    name: str
    description: str
    exiftool_args: list = None
    condition_template: str = None
    pattern: list = None
    for_lists: str = None
    icon: str = ""

@dataclass
class MappingConfig:
    """Configuration d'un mapping de métadonnée"""
    name: str
    source_fields: list
    target_tags: list
    default_strategy: str
    video_tags: list = None
    normalize: str = None
    sanitize: bool = False
    value_mapping: dict = None
    processing: dict = None
    conditional_tags: dict = None

class ConfigLoader:
    """Chargeur de configuration flexible"""
    
    def __init__(self, config_dir: Path = None):
        # Nouveau : pointer vers le dossier config/ organisé
        if config_dir is None:
            project_root = Path(__file__).parent.parent.parent
            config_dir = project_root / "config"
        self.config_dir = config_dir
        self.config = {}
        self.strategies = {}
        self.mappings = {}
        
    def load_config(self, json_file: str = "exif_mapping.json", env_file: str = ".env") -> Dict[str, Any]:
        """Charge la configuration depuis JSON et .env"""
        
        # 1. Charger la configuration JSON de base
        json_path = self.config_dir / json_file
        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            logger.info(f"Configuration JSON chargée depuis {json_path}")
        else:
            logger.warning(f"Fichier de configuration JSON non trouvé : {json_path}")
            self.config = self._get_default_config()
            
        # 2. Charger les overrides depuis .env
        env_path = self.config_dir / env_file
        if env_path.exists():
            self._load_env_overrides(env_path)
            logger.info(f"Overrides .env chargés depuis {env_path}")
            
        # 3. Charger les variables d'environnement
        self._load_env_variables()
        
        # 4. Parser les stratégies et mappings
        self._parse_strategies()
        self._parse_mappings()
        
        return self.config
    
    def _load_env_overrides(self, env_path: Path):
        """Charge les overrides depuis un fichier .env"""
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    self._apply_env_override(key.strip(), value.strip())
    
    def _load_env_variables(self):
        """Charge les variables d'environnement système"""
        for key, value in os.environ.items():
            if key.endswith('_STRATEGY') or key.startswith('EXIF_'):
                self._apply_env_override(key, value)
    
    def _apply_env_override(self, key: str, value: str):
        """Applique un override depuis une variable d'environnement"""
        
        # Conversion des types
        if value.lower() in ('true', 'false'):
            value = value.lower() == 'true'
        elif value.isdigit():
            value = int(value)
        elif value.replace('.', '').isdigit():
            value = float(value)
            
        # Application des overrides spécifiques
        if key.endswith('_STRATEGY'):
            field_name = key.replace('_STRATEGY', '').lower()
            if 'user_overrides' not in self.config:
                self.config['user_overrides'] = {}
            self.config['user_overrides'][field_name] = {'strategy': value}
            
        elif key == 'DEFAULT_STRATEGY':
            self.config.setdefault('global_settings', {})['default_strategy'] = value
            
        elif key in ['USE_LOCALTIME', 'IMMEDIATE_DELETE_SIDECARS', 'ENABLE_GEOCODING']:
            self.config.setdefault('global_settings', {})[key.lower()] = value
            
        # Custom mappings
        elif key == 'CUSTOM_MAPPINGS' and value:
            self._parse_custom_mappings(value)
    
    def _parse_custom_mappings(self, mappings_str: str):
        """Parse les mappings personnalisés depuis la config"""
        if not mappings_str:
            return
            
        for mapping in mappings_str.split(','):
            if ':' in mapping:
                parts = mapping.strip().split(':')
                if len(parts) >= 3:
                    source_field, target_tag, strategy = parts[:3]
                    custom_name = f"custom_{source_field}"
                    
                    self.config.setdefault('exif_mapping', {})[custom_name] = {
                        'source_fields': [source_field],
                        'target_tags': [target_tag],
                        'default_strategy': strategy
                    }
    
    def _parse_strategies(self):
        """Parse les configurations de stratégies"""
        strategies_config = self.config.get('strategies', {})
        for name, config in strategies_config.items():
            self.strategies[name] = StrategyConfig(
                name=name,
                description=config.get('description', ''),
                exiftool_args=config.get('exiftool_args', []),
                condition_template=config.get('condition_template'),
                pattern=config.get('pattern', []),
                for_lists=config.get('for_lists'),
                icon=config.get('icon', '')
            )
    
    def _parse_mappings(self):
        """Parse les configurations de mappings"""
        mappings_config = self.config.get('exif_mapping', {})
        user_overrides = self.config.get('user_overrides', {})
        
        for name, config in mappings_config.items():
            # Appliquer les overrides utilisateur
            strategy = config.get('default_strategy', 'preserve_existing')
            if name in user_overrides and 'strategy' in user_overrides[name]:
                strategy = user_overrides[name]['strategy']
                
            self.mappings[name] = MappingConfig(
                name=name,
                source_fields=config.get('source_fields', []),
                target_tags=config.get('target_tags', []),
                default_strategy=strategy,
                video_tags=config.get('video_tags', []),
                normalize=config.get('normalize'),
                sanitize=config.get('sanitize', False),
                value_mapping=config.get('value_mapping'),
                processing=config.get('processing'),
                conditional_tags=config.get('conditional_tags')
            )
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Configuration par défaut si aucun fichier n'est trouvé"""
        return {
            "exif_mapping": {
                "description": {
                    "source_fields": ["description"],
                    "target_tags": ["EXIF:ImageDescription", "XMP-dc:Description", "IPTC:Caption-Abstract"],
                    "default_strategy": "preserve_existing"
                }
            },
            "strategies": {
                "preserve_existing": {"description": "Préserve l'existant avec -wm cg"},
                "replace_all": {"description": "Remplace complètement"},
                "write_if_missing": {"description": "Écrit seulement si absent"},
                "clean_duplicates": {"description": "Évite les doublons"}
            },
            "global_settings": {
                "default_strategy": "preserve_existing"
            }
        }
    
    def get_strategy(self, name: str) -> Optional[StrategyConfig]:
        """Récupère une stratégie par nom"""
        return self.strategies.get(name)
    
    def get_mapping(self, name: str) -> Optional[MappingConfig]:
        """Récupère un mapping par nom"""
        return self.mappings.get(name)
    
    def get_all_strategies(self) -> Dict[str, StrategyConfig]:
        """Récupère toutes les stratégies"""
        return self.strategies
    
    def get_all_mappings(self) -> Dict[str, MappingConfig]:
        """Récupère tous les mappings"""
        return self.mappings

# Instance globale
_config_loader = None

def get_config_loader() -> ConfigLoader:
    """Récupère l'instance globale du loader de configuration"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
        _config_loader.load_config()
    return _config_loader

def reload_config():
    """Recharge la configuration"""
    global _config_loader
    _config_loader = None
    return get_config_loader()

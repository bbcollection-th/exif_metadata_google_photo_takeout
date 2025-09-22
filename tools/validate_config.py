#!/usr/bin/env python3
"""
Outil de validation et de nettoyage de la configuration EXIF découverte.

Valide la configuration générée par discover_fields.py et propose des améliorations.

Usage:
    python validate_config.py discovered_config.json
    python validate_config.py discovered_config.json --clean --output clean_config.json
"""

import json
import argparse
from pathlib import Path
from typing import Dict, Any, List
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class ConfigValidator:
    """Validateur et nettoyeur de configuration EXIF"""
    
    def __init__(self):
        self.issues: List[str] = []
        self.suggestions: List[str] = []
        
        # Tags EXIF/XMP valides connus
        self.known_tags = {
            'EXIF:ImageDescription', 'EXIF:Software', 'EXIF:DateTimeOriginal',
            'EXIF:CreateDate', 'EXIF:ModifyDate', 'EXIF:ImageWidth', 'EXIF:ImageHeight',
            'EXIF:OffsetTimeOriginal', 'EXIF:OffsetTimeDigitized', 'EXIF:OffsetTime',
            'XMP-dc:Description', 'XMP-dc:Subject', 'XMP-dc:Creator', 'XMP-dc:Title',
            'XMP-iptcExt:PersonInImage', 'XMP:Rating', 'XMP:City', 'XMP:Country',
            'XMP:Location', 'XMP-xmp:CreatorTool', 'XMP-xmp:CreateDate',
            'XMP-lr:HierarchicalSubject', 'XMP-photoshop:DateCreated',
            'XMP-photoshop:City', 'XMP-photoshop:State', 'XMP-photoshop:Country',
            'XMP-iptcCore:Location',
            'XMP-exif:GPSLatitude', 'XMP-exif:GPSLongitude', 'XMP-exif:GPSAltitude', 'XMP-exif:GPSAltitudeRef',
            'IPTC:Caption-Abstract', 'IPTC:Keywords', 'IPTC:City', 'IPTC:Country-PrimaryLocationName',
            'IPTC:ObjectName', 'IPTC:Province-State', 'IPTC:Sub-location', 'MWG:Description',
            'GPSLatitude', 'GPSLongitude', 'GPSAltitude', 'GPSAltitudeRef',
            'GPSLatitudeRef', 'GPSLongitudeRef',
            'Keys:Description', 'Keys:Location',
            'QuickTime:CreateDate', 'QuickTime:ModifyDate', 'QuickTime:GPSCoordinates',
            'QuickTime:TrackCreateDate', 'QuickTime:TrackModifyDate',
            'QuickTime:MediaCreateDate', 'QuickTime:MediaModifyDate'
        }
        
        # Stratégies valides
        self.valid_strategies = {
            'preserve_existing', 'replace_all', 'write_if_missing', 'clean_duplicates',
            'write_if_blank_or_missing', 'preserve_positive_rating'
        }
        
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Valide une configuration complète"""
        logger.info("🔍 Validation de la configuration...")
        
        is_valid = True
        
        # Validation de la structure
        if not self._validate_structure(config):
            is_valid = False
            
        # Validation des stratégies
        if not self._validate_strategies(config.get('strategies', {})):
            is_valid = False
            
        # Validation des mappings
        if not self._validate_mappings(config.get('exif_mapping', {})):
            is_valid = False
            
        # Validation des paramètres globaux
        if not self._validate_global_settings(config.get('global_settings', {})):
            is_valid = False
            
        return is_valid
    
    def _validate_structure(self, config: Dict[str, Any]) -> bool:
        """Valide la structure de base de la configuration"""
        required_sections = ['exif_mapping', 'strategies', 'global_settings']
        missing_sections = [s for s in required_sections if s not in config]
        
        if missing_sections:
            self.issues.append(f"❌ Sections manquantes : {missing_sections}")
            return False
            
        return True
    
    def _validate_strategies(self, strategies: Dict[str, Any]) -> bool:
        """Valide les définitions de stratégies"""
        is_valid = True
        
        for name, strategy in strategies.items():
            if name not in self.valid_strategies:
                self.issues.append(f"⚠️ Stratégie inconnue : {name}")
                
            if not isinstance(strategy, dict):
                self.issues.append(f"❌ Stratégie {name} doit être un objet")
                is_valid = False
                continue
                
            if 'description' not in strategy:
                self.issues.append(f"⚠️ Stratégie {name} sans description")
                
        return is_valid
    
    def _validate_mappings(self, mappings: Dict[str, Any]) -> bool:
        """Valide les mappings de métadonnées"""
        is_valid = True
        duplicate_targets: Dict[str, List[str]] = {}
        
        for name, mapping in mappings.items():
            if not isinstance(mapping, dict):
                self.issues.append(f"❌ Mapping {name} doit être un objet")
                is_valid = False
                continue
                
            # Validation des champs requis
            required_fields = ['source_fields', 'target_tags_image', 'default_strategy']
            missing_fields = [f for f in required_fields if f not in mapping]
            if missing_fields:
                self.issues.append(f"❌ Mapping {name} manque : {missing_fields}")
                is_valid = False
                continue
                
            # Validation de la stratégie
            strategy = mapping.get('default_strategy')
            if strategy not in self.valid_strategies:
                self.issues.append(f"⚠️ Mapping {name} : stratégie inconnue '{strategy}'")
                
            # Validation des types de champs
            source_fields = mapping.get('source_fields', [])
            target_tags_image = mapping.get('target_tags_image', [])
            if not isinstance(source_fields, list) or not source_fields or not all(isinstance(s, str) for s in source_fields):
                self.issues.append(f"❌ Mapping {name} : 'source_fields' doit être une liste non vide de chaînes")
                is_valid = False
                continue
            if not isinstance(target_tags_image, list) or not target_tags_image or not all(isinstance(t, str) for t in target_tags_image):
                self.issues.append(f"❌ Mapping {name} : 'target_tags_image' doit être une liste non vide de chaînes")
                is_valid = False
                continue

            # Validation des tags cibles           
            if isinstance(target_tags_image, list):
                for tag in target_tags_image:
                    if tag not in self.known_tags and not self._is_custom_tag(tag):
                        self.suggestions.append(f"💡 Tag possiblement incorrect : {tag} (mapping {name})")
                        
                    # Détection des doublons
                    if tag not in duplicate_targets:
                        duplicate_targets[tag] = []
                    duplicate_targets[tag].append(name)
                        
            # Validation de la fréquence (pour prioriser)
            discovery_info = mapping.get('_discovery_info', {})
            frequency = discovery_info.get('frequency', 0)
            if frequency < 5:
                self.suggestions.append(f"💡 Champ rare ({frequency}x) : {name} - considérer la suppression")
                
        # Signaler les doublons
        for tag, mapping_names in duplicate_targets.items():
            if len(mapping_names) > 1:
                self.issues.append(f"⚠️ Tag {tag} utilisé par plusieurs mappings : {mapping_names}")
                
        return is_valid
    
    def _validate_global_settings(self, settings: Dict[str, Any]) -> bool:
        """Valide les paramètres globaux"""
        if 'default_strategy' in settings:
            default_strategy = settings['default_strategy']
            if default_strategy not in self.valid_strategies:
                self.issues.append(f"❌ Stratégie par défaut inconnue : {default_strategy}")
                return False
                
        return True
    
    def _is_custom_tag(self, tag: str) -> bool:
        """Vérifie si un tag semble être un tag personnalisé valide"""
        # Pattern pour les tags personnalisés XMP
        return bool(re.match(r'^XMP[:-][a-zA-Z]+:[a-zA-Z][a-zA-Z0-9]*$', tag))
    
    def clean_config(self, config: Dict[str, Any], min_frequency: int = 5) -> Dict[str, Any]:
        """Nettoie la configuration en supprimant les champs peu fréquents et problématiques"""
        logger.info(f"🧹 Nettoyage de la configuration (fréquence min: {min_frequency})...")
        
        cleaned_config = json.loads(json.dumps(config))  # Deep copy
        
        mappings = cleaned_config.get('exif_mapping', {})
        original_count = len(mappings)
        
        # Supprimer les mappings peu fréquents ou problématiques
        to_remove = []
        for name, mapping in mappings.items():
            discovery_info = mapping.get('_discovery_info', {})
            frequency = discovery_info.get('frequency', 0)
            
            # Critères de suppression
            should_remove = False
            
            # Fréquence trop faible
            if frequency < min_frequency:
                should_remove = True
                logger.debug(f"Suppression de {name} : fréquence trop faible ({frequency})")
                
            # Champs techniques/debug
            if any(skip in name.lower() for skip in ['debug', 'internal', 'raw', 'meta', 'temp']):
                should_remove = True
                logger.debug(f"Suppression de {name} : champ technique")
                
            # Tags cibles invalides
            target_tags_image = mapping.get('target_tags_image', [])
            if isinstance(target_tags_image, list):
                valid_tags = [tag for tag in target_tags_image if tag in self.known_tags or self._is_custom_tag(tag)]
                if not valid_tags:
                    should_remove = True
                    logger.debug(f"Suppression de {name} : aucun tag valide")
                    
            if should_remove:
                to_remove.append(name)
        
        # Effectuer les suppressions
        for name in to_remove:
            del mappings[name]
            
        # Nettoyer les informations de découverte (optionnel)
        for mapping in mappings.values():
            if '_discovery_info' in mapping:
                # Garder seulement les infos utiles
                discovery_info = mapping['_discovery_info']
                mapping['_discovery_info'] = {
                    'frequency': discovery_info.get('frequency', 0),
                    'data_types': discovery_info.get('data_types', [])
                }
        
        logger.info(f"✂️ Nettoyage terminé : {original_count} → {len(mappings)} mappings")
        
        return cleaned_config
    
    def generate_report(self) -> str:
        """Génère un rapport de validation"""
        report = []
        report.append("=" * 60)
        report.append("📋 RAPPORT DE VALIDATION")
        report.append("=" * 60)
        
        if not self.issues and not self.suggestions:
            report.append("✅ Configuration valide ! Aucun problème détecté.")
        else:
            if self.issues:
                report.append(f"\n🚨 PROBLÈMES DÉTECTÉS ({len(self.issues)}):")
                for issue in self.issues:
                    report.append(f"   {issue}")
                    
            if self.suggestions:
                report.append(f"\n💡 SUGGESTIONS ({len(self.suggestions)}):")
                for suggestion in self.suggestions:
                    report.append(f"   {suggestion}")
        
        return "\n".join(report)

def main():
    parser = argparse.ArgumentParser(
        description="Validation et nettoyage de configuration EXIF découverte"
    )
    parser.add_argument(
        "config_file",
        type=Path,
        help="Fichier de configuration à valider"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Nettoyer la configuration"
    )
    parser.add_argument(
        "--min-frequency",
        type=int,
        default=5,
        help="Fréquence minimale pour garder un champ (défaut: 5)"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Fichier de sortie pour la configuration nettoyée"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Mode verbeux"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if not args.config_file.exists():
        logger.error(f"❌ Fichier introuvable : {args.config_file}")
        return 1
    
    # Chargement de la configuration
    try:
        with open(args.config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"❌ Erreur JSON : {e}")
        return 1
    
    # Validation
    validator = ConfigValidator()
    is_valid = validator.validate_config(config)
    
    # Affichage du rapport
    print(validator.generate_report())
    
    # Nettoyage si demandé
    if args.clean:
        cleaned_config = validator.clean_config(config, args.min_frequency)
        
        output_file = args.output or args.config_file.with_stem(f"{args.config_file.stem}_clean")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(cleaned_config, f, indent=2, ensure_ascii=False)
            
        logger.info(f"💾 Configuration nettoyée sauvée dans : {output_file}")
    
    return 0 if is_valid else 1

if __name__ == "__main__":
    exit(main())

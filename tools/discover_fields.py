#!/usr/bin/env python3
"""
Outil de découverte automatique des champs JSON pour générer la configuration EXIF.

Scanne récursivement les fichiers .json Google Photos pour découvrir tous les champs
possibles et génère automatiquement un fichier de configuration avec des stratégies
par défaut intelligentes.

Fonctionnalités incluses automatiquement :
- Mappings de métadonnées découverts automatiquement
- Stratégies optimisées (preserve_existing, replace_all, etc.)
- Configuration de correction de fuseau horaire (timezone_correction)
- Paramètres globaux avec encodage UTF-8

Usage:
    python discover_fields.py /path/to/google/photos/folder
    python discover_fields.py /path/to/google/photos/folder --output custom_config.json
"""

import json
import argparse
from pathlib import Path
from typing import Dict, Any, Set, List, Optional
import re
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

from dataclasses import dataclass, field

@dataclass
class FieldInfo:
    """Information sur un champ découvert"""
    name: str
    sample_values: List[Any]
    data_types: Set[str]
    frequency: int
    max_length: int = 0
    is_list: bool = False
    nested_fields: Dict[str, 'FieldInfo'] = field(default_factory=dict)
class FieldDiscoverer:
    """Découverte automatique des champs JSON"""
    
    def __init__(self):
        self.discovered_fields: Dict[str, FieldInfo] = {}
        self.file_count = 0
        self.error_count = 0
        
        # Règles de mapping automatique basées sur les noms de champs
        self.field_patterns = {
            # Texte/Description
            r'.*description.*|.*caption.*|.*comment.*': {
                'category': 'description',
                'target_tags_image': ['EXIF:ImageDescription', 'XMP-dc:Description', 'IPTC:Caption-Abstract'],
                'default_strategy': 'preserve_existing',
                'sanitize': True
            },
            
            # Personnes
            r'.*people_name.*|.*person.*|.*face.*|.*who.*': {
                'category': 'people_name',
                'target_tags_image': ['XMP-iptcExt:PersonInImage'],
                'default_strategy': 'clean_duplicates',
                'normalize': 'person_name'
            },
            
            # Localisation
            r'.*location.*|.*place.*|.*address.*|.*where.*': {
                'category': 'location',
                'target_tags_image': ['XMP:Location'],
                'default_strategy': 'replace_all'
            },
            
            # Coordonnées GPS
            r'(^|[._])(lat(itude)?|lon(gitude)?|lng|alt(itude)?|coord(s)?)\\b': {
                'category': 'gps',
                'target_tags_image': ['GPS:GPSLatitude', 'GPS:GPSLongitude', 'GPS:GPSAltitude'],
                'default_strategy': 'replace_all'
            },
            
            # Dates/Temps
            r'.*time.*|.*date.*|.*timestamp.*|.*when.*|.*taken.*|.*created.*': {
                'category': 'datetime',
                'target_tags_image': ['EXIF:DateTimeOriginal', 'EXIF:CreateDate'],
                'default_strategy': 'replace_all',
                'format': '%Y:%m:%d %H:%M:%S'
            },
            
            # Albums/Collections
            r'.*album.*|.*collection.*|.*folder.*|.*group.*': {
                'category': 'keywords',
                'target_tags_image': ['XMP-dc:Subject', 'IPTC:Keywords'],
                'default_strategy': 'clean_duplicates',
                'processing': {'prefix': 'Album: ', 'normalize': 'keyword'}
            },
            
            # Tags/Mots-clés
            r'.*tag.*|.*keyword.*|.*label.*|.*category.*': {
                'category': 'keywords',
                'target_tags_image': ['XMP-dc:Subject', 'IPTC:Keywords'],
                'default_strategy': 'clean_duplicates',
                'normalize': 'keyword'
            },
            
            # Rating/Favoris
            r'.*fav.*|.*star.*|.*rating.*|.*rank.*|.*like.*': {
                'category': 'rating',
                'target_tags_image': ['XMP:Rating'],
                'target_tags_video': ['XMP:Rating'],
                'default_strategy': 'preserve_positive_rating',
                'value_mapping': {'true': '5', 'false': None}
            },
            
            # Géolocalisation textuelle
            r'.*city.*|.*country.*|.*state.*|.*region.*': {
                'category': 'location',
                'target_tags_image': {
                    'city': ['XMP:City', 'IPTC:City'],
                    'country': ['XMP:Country', 'IPTC:Country-PrimaryLocationName']
                },
                'default_strategy': 'replace_all'
            },
            
            # Métadonnées techniques
            r'.*width.*|.*height.*|.*size.*|.*dimension.*': {
                'category': 'technical',
                'target_tags_image': ['EXIF:ImageWidth', 'EXIF:ImageHeight'],
                'default_strategy': 'write_if_missing'
            },
            
            # Métadonnées de source
            r'.*source.*|.*app.*|.*device.*|.*camera.*|.*tool.*': {
                'category': 'source',
                'target_tags_image': ['EXIF:Software', 'XMP-xmp:CreatorTool'],
                'default_strategy': 'write_if_missing'
            }
        }
    
    def discover_directory(self, directory: Path) -> Dict[str, FieldInfo]:
        """Découvre tous les champs dans un répertoire"""
        logger.info(f"🔍 Scan du répertoire : {directory}")
        
        json_files = list(directory.rglob("*.json"))
        logger.info(f"📁 {len(json_files)} fichiers JSON trouvés")
        
        for json_file in json_files:
            try:
                self._analyze_file(json_file)
                self.file_count += 1
                if self.file_count % 100 == 0:
                    logger.info(f"📊 {self.file_count} fichiers analysés...")
            except Exception as e:
                logger.warning(f"❌ Erreur dans {json_file.name}: {e}")
                self.error_count += 1
        
        logger.info(f"✅ Analyse terminée : {self.file_count} fichiers, {self.error_count} erreurs")
        logger.info(f"🎯 {len(self.discovered_fields)} champs uniques découverts")
        
        return self.discovered_fields
    
    def _analyze_file(self, json_file: Path):
        """Analyse un fichier JSON individuel"""
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self._analyze_object(data, prefix="")
    
    def _analyze_object(self, obj: Any, prefix: str = ""):
        """Analyse récursivement un objet JSON"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                field_name = f"{prefix}.{key}" if prefix else key
                self._record_field(field_name, value)
                
                # Analyse récursive pour les objets imbriqués
                if isinstance(value, (dict, list)):
                    self._analyze_object(value, field_name)
                    
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, (dict, list)):
                    self._analyze_object(item, prefix)
    
    def _record_field(self, field_name: str, value: Any):
        """Enregistre un champ découvert"""
        if field_name not in self.discovered_fields:
            self.discovered_fields[field_name] = FieldInfo(
                name=field_name,
                sample_values=[],
                data_types=set(),
                frequency=0,
                nested_fields={}
            )
        
        field_info = self.discovered_fields[field_name]
        field_info.frequency += 1
        
        # Type de données
        value_type = type(value).__name__
        field_info.data_types.add(value_type)
        
        # Échantillons de valeurs (limité pour éviter la surcharge mémoire)
        if len(field_info.sample_values) < 10:
            field_info.sample_values.append(value)
        
        # Caractéristiques spéciales
        if isinstance(value, str):
            field_info.max_length = max(field_info.max_length, len(value))
        elif isinstance(value, list):
            field_info.is_list = True
            field_info.max_length = max(field_info.max_length, len(value))
    
    def generate_config(self, output_file: Path = None) -> Dict[str, Any]:
        """Génère la configuration EXIF basée sur les champs découverts"""
        logger.info("🏗️ Génération de la configuration...")
        
        config = {
            "exif_mapping": {},
            "strategies": {
                "preserve_existing": {
                    "description": "Utilise -wm cg pour préserver l'existant",
                    "exiftool_args": ["-wm", "cg"],
                    "icon": "⚠️"
                },
                "replace_all": {
                    "description": "Remplace complètement les valeurs",
                    "for_lists": "clear_then_add",
                    "icon": "🔄"
                },
                "write_if_missing": {
                    "description": "Utilise -if pour n'écrire que si absent",
                    "condition_template": "-if \"not ${tag}\"",
                    "for_lists": "conditional_add",
                    "icon": "➕"
                },
                "clean_duplicates": {
                    "description": "Supprime puis ajoute pour éviter doublons",
                    "pattern": ["${tag}-=${value}", "${tag}+=${value}"],
                    "icon": "✨"
                },
                "preserve_positive_rating": {
                    "description": "Pour favorited: écrire Rating/Label=valeur si favorited=true ET (tag absent OU tag=0), ne jamais toucher si favorited=false",
                    "condition_template": "-if not defined $${tag} or $${tag} eq '0'",
                    "pattern": ["-${tag}=${value}"],
                    "special_logic": "favorited_rating"
                }
            },
            "global_settings": {
                "default_strategy": "preserve_existing",
                "video_extensions": [".mp4", ".mov", ".m4v", ".3gp"],
                "common_args": ["-overwrite_original"],
                "charset_args": [
                    "-charset", "filename=UTF8",
                    "-charset", "iptc=UTF8",
                    "-charset", "exif=UTF8",
                    "-codedcharacterset=utf8"
                ]
            },
            "timezone_correction": {
                "enabled": False,
                "description": "Correction automatique des fuseaux horaires basée sur les coordonnées GPS",
                "use_absolute_values": True,
                "fallback_to_utc": False,
                "note": "Nécessite timezonefinder: pip install timezonefinder"
            }
        }
        
        # Tri des champs par fréquence (plus fréquent = plus important)
        sorted_fields = sorted(
            self.discovered_fields.items(),
            key=lambda x: x[1].frequency,
            reverse=True
        )
        
        for field_name, field_info in sorted_fields:
            mapping = self._generate_mapping(field_name, field_info)
            if mapping:
                # Nom sécurisé pour la configuration
                safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', field_name).lower()
                config["exif_mapping"][safe_name] = mapping
                
                # LOGIQUE SPÉCIALE: Si c'est "favorited", ajouter automatiquement "favorited_label"
                if field_name == "favorited":
                    logger.info("🏷️ Ajout automatique de favorited_label pour XMP:Label")
                    favorited_label_mapping = {
                        "source_fields": ["favorited"],
                        "target_tags_image": ["XMP:Label"],
                        "target_tags_video": ["XMP:Label"],
                        "default_strategy": "preserve_positive_rating",
                        "value_mapping": {
                            "true": "Favorite",
                            "false": None
                        },
                        "_discovery_info": {
                            "frequency": field_info.frequency,
                            "data_types": list(field_info.data_types),
                            "sample_values": field_info.sample_values[:3],
                            "is_list": field_info.is_list,
                            "max_length": field_info.max_length,
                            "auto_generated": "Generated automatically when favorited field detected"
                        }
                    }
                    config["exif_mapping"]["favorited_label"] = favorited_label_mapping
        
        if output_file:
            # Générer le fichier de configuration épuré
            clean_config = self._create_clean_config(config)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(clean_config, f, indent=2, ensure_ascii=False)
            logger.info(f"💾 Configuration épurée sauvée dans : {output_file}")
            
            # Optionnel : sauvegarder un fichier de debug avec toutes les infos
            debug_file = output_file.with_name(f"debug_{output_file.name}")
            with open(debug_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logger.debug(f"🔍 Informations de debug sauvées dans : {debug_file}")
        
        return config
    
    def _create_clean_config(self, full_config: Dict[str, Any]) -> Dict[str, Any]:
        """Crée une version épurée de la configuration sans les infos de debug"""
        clean_config = {
            "exif_mapping": {},
            "strategies": {
                "preserve_existing": {
                    "description": "Préserver les métadonnées existantes",
                    "exiftool_args": ["-wm", "cg"]
                },
                "replace_all": {
                    "description": "Remplacer toutes les métadonnées",
                    "exiftool_args": ["-overwrite_original"]
                },
                "write_if_missing": {
                    "description": "Écrire seulement si absent",
                    "condition_template": "-if \"not ${tag}\""
                },
                "clean_duplicates": {
                    "description": "Nettoyer les doublons avant écriture",
                    "pattern": ["${tag}-=${value}", "${tag}+=${value}"]
                },
                "preserve_positive_rating": {
                    "description": "Pour favorited: écrire Rating/Label si favorited=true ET (tag absent OU tag=0), ne jamais toucher si favorited=false",
                    "condition_template": "-if not defined $${tag} or $${tag} eq '0'",
                    "pattern": ["-${tag}=${value}"],
                    "special_logic": "favorited_rating"
                }
            },
            "global_settings": {
                "default_strategy": "write_if_missing",
                "video_extensions": [".mp4", ".mov", ".m4v", ".3gp"],
                "common_args": ["-charset", "filename=UTF8"],
                "backup_original": True
            }
        }
        
        # Copier les mappings en supprimant les infos de debug
        for name, mapping in full_config["exif_mapping"].items():
            clean_mapping = {}
            for key, value in mapping.items():
                # Exclure les clés de debug qui commencent par '_'
                if not key.startswith('_'):
                    clean_mapping[key] = value
            clean_config["exif_mapping"][name] = clean_mapping
        
        return clean_config
    
    def _generate_mapping(self, field_name: str, field_info: FieldInfo) -> Optional[Dict[str, Any]]:
        """Génère un mapping pour un champ découvert"""
        
        # Recherche de pattern correspondant
        matched_pattern = None
        for pattern, mapping_template in self.field_patterns.items():
            if re.search(pattern, field_name.lower()):
                matched_pattern = mapping_template
                break
        
        # Si aucun pattern ne correspond, créer un mapping générique
        if not matched_pattern:
            # Ignorer certains champs techniques/méta
            if any(skip in field_name.lower() for skip in ['_', 'meta', 'raw', 'debug', 'internal']):
                return None
                
            matched_pattern = {
                'category': 'custom',
                'target_tags_image': [f'XMP:Custom{field_name.replace(".", "").title()}'],
                'default_strategy': 'write_if_missing'
            }
        
        # Résoudre target_tags_image selon le contexte
        pattern_tt = matched_pattern['target_tags_image']
        if isinstance(pattern_tt, dict):
            lname = field_name.lower()
            if 'city' in lname:
                resolved_tt = pattern_tt.get('city', [])
            elif 'country' in lname:
                resolved_tt = pattern_tt.get('country', [])
            else:
                # fallback: concaténation de toutes les listes
                resolved_tt = [t for v in pattern_tt.values() for t in v]
        elif matched_pattern.get('category') == 'gps':
            lname = field_name.lower()
            if re.search(r'lat(itude)?\\b', lname):
                resolved_tt = ['GPS:GPSLatitude']
            elif re.search(r'(lon|long|lng)(gitude)?\\b', lname):
                resolved_tt = ['GPS:GPSLongitude']
            elif 'alt' in lname:
                resolved_tt = ['GPS:GPSAltitude']
            else:
                resolved_tt = ['XMP:CustomGps']
        else:
            resolved_tt = pattern_tt

        mapping = {
            "source_fields": [field_name],
            "target_tags_image": resolved_tt,
            "default_strategy": matched_pattern['default_strategy'],
            "_discovery_info": {
                "frequency": field_info.frequency,
                "data_types": list(field_info.data_types),
                "sample_values": field_info.sample_values[:3],  # Premiers échantillons
                "is_list": field_info.is_list,
                "max_length": field_info.max_length
            }
        }
        
        # Ajout des propriétés optionnelles
        for prop in ['normalize', 'sanitize', 'format', 'value_mapping', 'processing']:
            if prop in matched_pattern:
                mapping[prop] = matched_pattern[prop]
        
        return mapping
    
    def print_summary(self):
        """Affiche un résumé des découvertes"""
        print("\n" + "="*60)
        print("📊 RÉSUMÉ DE LA DÉCOUVERTE")
        print("="*60)
        print(f"Fichiers analysés : {self.file_count}")
        print(f"Erreurs rencontrées : {self.error_count}")
        print(f"Champs uniques : {len(self.discovered_fields)}")
        
        print("\n🔥 TOP 10 DES CHAMPS LES PLUS FRÉQUENTS:")
        sorted_fields = sorted(
            self.discovered_fields.items(),
            key=lambda x: x[1].frequency,
            reverse=True
        )
        
        for i, (name, info) in enumerate(sorted_fields[:10]):
            types_str = ", ".join(info.data_types)
            print(f"{i+1:2}. {name:<30} ({info.frequency:>5}x) [{types_str}]")
        
        print("\n📝 CHAMPS DE TYPE LISTE:")
        list_fields = [(name, info) for name, info in sorted_fields if info.is_list]
        for name, info in list_fields[:10]:
            sample = info.sample_values[0] if info.sample_values else "N/A"
            print(f"   • {name:<30} (max: {info.max_length}, ex: {sample})")

def main():
    parser = argparse.ArgumentParser(
        description="Découverte automatique des champs JSON pour configuration EXIF"
    )
    parser.add_argument(
        "directory",
        type=Path,
        help="Répertoire contenant les fichiers JSON à analyser"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default="exif_mapping_autogenerated.json",
        help="Fichier de sortie pour la configuration (défaut: exif_mapping_autogenerated.json)"
    )
    parser.add_argument(
        "-s", "--summary",
        action="store_true",
        help="Afficher un résumé détaillé des découvertes"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Mode verbeux"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if not args.directory.exists():
        logger.error(f"❌ Répertoire introuvable : {args.directory}")
        return 1
    
    # Découverte des champs
    discoverer = FieldDiscoverer()
    discoverer.discover_directory(args.directory)
    
    # Génération de la configuration
    discoverer.generate_config(args.output)
    
    # Affichage du résumé
    if args.summary:
        discoverer.print_summary()
    
    print(f"\n✅ Configuration générée dans : {args.output}")
    print("🔧 Vous pouvez maintenant éditer ce fichier pour :")
    print("   • Ajuster les stratégies par défaut")
    print("   • Supprimer les champs non désirés") 
    print("   • Ajouter des mappings personnalisés")
    print("   • Configurer la normalisation")
    
    return 0

if __name__ == "__main__":
    exit(main())

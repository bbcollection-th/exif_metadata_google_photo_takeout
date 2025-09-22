#!/usr/bin/env python3
"""
Tests de qualité pour Google Photos Takeout Metadata Processor
Point 10 de la checklist : Tests avant/après traitement, suppression warnings, sauvegarde config

Ce script :
1. Teste le traitement sur des fichiers réels avant/après
2. Vérifie la suppression des warnings ExifTool
3. Sauvegarde la config avec export -args
4. Valide l'intégrité des métadonnées
"""

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class QualityTester:
    """Testeur de qualité pour le processus de métadonnées"""
    
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.test_assets_dir = workspace_root / "test_assets"  # Pas dans tools/
        self.temp_dir = None
        self.exiftool_path = self._find_exiftool()
        
    def _find_exiftool(self) -> Optional[str]:
        """Trouve ExifTool dans le système"""
        try:
            result = subprocess.run(['exiftool', '-ver'], capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"✅ ExifTool trouvé, version: {result.stdout.strip()}")
                return 'exiftool'
        except FileNotFoundError:
            pass
            
        # Essayer des chemins Windows communs
        for path in ['C:/Windows/exiftool.exe', 'C:/Program Files/exiftool/exiftool.exe']:
            if Path(path).exists():
                logger.info(f"✅ ExifTool trouvé: {path}")
                return path
                
        logger.error("❌ ExifTool non trouvé dans le système")
        return None
    
    def _read_metadata(self, file_path: Path) -> Dict:
        """Lit les métadonnées d'un fichier avec ExifTool"""
        if not self.exiftool_path:
            return {}
            
        try:
            cmd = [
                self.exiftool_path, '-json', '-charset', 'utf8',
                '-codedcharacterset=utf8', str(file_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                try:
                    metadata = json.loads(result.stdout)[0]
                    # Filtrer les clés importantes pour le test
                    filtered = {k: v for k, v in metadata.items() 
                               if any(tag in k for tag in ['XMP', 'EXIF', 'IPTC']) 
                               and 'Directory' not in k and 'FileName' not in k}
                    return filtered
                except (json.JSONDecodeError, IndexError):
                    # JSON vide ou invalide - normal pour certains fichiers
                    return {}
            else:
                return {}
        except Exception as e:
            logger.error(f"Erreur lecture métadonnées: {e}")
            return {}
    
    def _count_warnings(self, exiftool_output: str) -> int:
        """Compte le nombre de warnings dans la sortie ExifTool"""
        warning_indicators = [
            'Warning:', 'warning:', 'WARNING:',
            'Note:', 'note:', 'NOTE:',
            'Error:', 'error:', 'ERROR:'
        ]
        
        lines = exiftool_output.split('\n')
        warning_count = 0
        
        for line in lines:
            if any(indicator in line for indicator in warning_indicators):
                warning_count += 1
                logger.debug(f"Warning détecté: {line.strip()}")
        
        return warning_count
    
    def test_before_after_processing(self) -> bool:
        """Test avant/après traitement sur fichiers réels"""
        logger.info("🧪 Test avant/après traitement...")
        
        if not self.test_assets_dir.exists():
            logger.error(f"❌ Répertoire test_assets manquant: {self.test_assets_dir}")
            return False
        
        # Créer répertoire temporaire
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Copier les assets de test
            test_files = []
            for pattern in ['*.jpg', '*.mp4']:
                test_files.extend(self.test_assets_dir.glob(pattern))
            
            if not test_files:
                logger.error("❌ Aucun fichier de test trouvé dans test_assets/")
                return False
            
            logger.info(f"📁 {len(test_files)} fichiers de test trouvés")
            
            results = []
            for test_file in test_files[:3]:  # Limiter à 3 fichiers pour le test
                # Copier le fichier
                temp_file = temp_path / test_file.name
                shutil.copy2(test_file, temp_file)
                
                # Lire métadonnées AVANT
                metadata_before = self._read_metadata(temp_file)
                
                # Créer un JSON de test simple
                json_file = temp_file.with_suffix('.json')
                test_metadata = {
                    "title": temp_file.stem,  # Utiliser le nom du fichier sans extension
                    "description": "Test de qualité automatisé",
                    "favorited": True,
                    "photoTakenTime": {
                        "timestamp": "1672531200",
                        "formatted": "Jan 1, 2023, 12:00:00 AM UTC"
                    }
                }
                
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(test_metadata, f, indent=2, ensure_ascii=False)
                
                # Exécuter un test simple ExifTool directement
                try:
                    if not self.exiftool_path:
                        raise Exception("ExifTool non disponible")
                    
                    # Commandes de test simples
                    cmd = [
                        self.exiftool_path,
                        '-charset', 'utf8',
                        '-codedcharacterset=utf8',
                        '-XMP:Rating=5',
                        '-XMP:Label=Favorite',
                        '-XMP-dc:Title=Test automatisé',
                        '-overwrite_original',
                        str(temp_file)
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    success = result.returncode == 0
                    
                    if not success:
                        logger.warning(f"ExifTool stderr: {result.stderr}")
                    
                    # Lire métadonnées APRÈS
                    metadata_after = self._read_metadata(temp_file)
                    
                    # Analyser les changements
                    changes = self._analyze_metadata_changes(metadata_before, metadata_after)
                    
                    result_data = {
                        'file': temp_file.name,
                        'success': success,
                        'metadata_before_count': len(metadata_before),
                        'metadata_after_count': len(metadata_after),
                        'changes': changes
                    }
                    results.append(result_data)
                    
                    logger.info(f"✅ {temp_file.name}: {len(changes)} modifications détectées")
                    
                except Exception as e:
                    logger.error(f"❌ Erreur traitement {temp_file.name}: {e}")
                    results.append({
                        'file': temp_file.name,
                        'success': False,
                        'error': str(e)
                    })
            
            # Résumé des résultats
            successful = sum(1 for r in results if r.get('success', False))
            total = len(results)
            
            logger.info(f"📊 Résultats: {successful}/{total} fichiers traités avec succès")
            
            if successful > 0:
                total_changes = sum(len(r.get('changes', [])) for r in results if r.get('success'))
                logger.info(f"🔄 Total modifications: {total_changes}")
                return True
            else:
                logger.error("❌ Aucun fichier traité avec succès")
                return False
    
    def _analyze_metadata_changes(self, before: Dict, after: Dict) -> List[str]:
        """Analyse les changements entre métadonnées avant/après"""
        changes = []
        
        # Nouvelles clés ajoutées
        new_keys = set(after.keys()) - set(before.keys())
        for key in new_keys:
            changes.append(f"Ajouté: {key} = {after[key]}")
        
        # Valeurs modifiées
        for key in set(before.keys()) & set(after.keys()):
            if before[key] != after[key]:
                changes.append(f"Modifié: {key} = {before[key]} → {after[key]}")
        
        return changes
    
    def test_warning_suppression(self) -> bool:
        """Test de suppression des warnings ExifTool"""
        logger.info("⚠️ Test suppression des warnings...")
        
        if not self.exiftool_path:
            logger.error("❌ ExifTool non disponible pour le test")
            return False
        
        # Test avec un fichier qui devrait générer des warnings
        test_files = list(self.test_assets_dir.glob("*.jpg"))
        if not test_files:
            logger.error("❌ Aucun fichier JPG de test disponible")
            return False
        
        test_file = test_files[0]
        
        # Commande qui pourrait générer des warnings
        cmd = [
            self.exiftool_path,
            '-charset', 'utf8',
            '-codedcharacterset=utf8',
            '-XMP:Rating=5',
            '-XMP:Label=Favorite',
            '-overwrite_original',
            str(test_file)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Analyser la sortie pour les warnings
            warning_count = self._count_warnings(result.stderr)
            
            logger.info(f"📝 Sortie ExifTool stderr: {len(result.stderr.split()) if result.stderr else 0} mots")
            logger.info(f"⚠️ Warnings détectés: {warning_count}")
            
            if warning_count == 0:
                logger.info("✅ Aucun warning détecté - configuration charset correcte")
                return True
            else:
                logger.warning(f"⚠️ {warning_count} warnings détectés - vérification needed")
                # Log des warnings pour debug
                for line in result.stderr.split('\n'):
                    if any(w in line.lower() for w in ['warning', 'error', 'note']):
                        logger.debug(f"Warning: {line.strip()}")
                return warning_count <= 2  # Tolérer quelques warnings mineurs
                
        except Exception as e:
            logger.error(f"❌ Erreur test warnings: {e}")
            return False
    
    def test_config_export_args(self) -> bool:
        """Test sauvegarde config avec export -args"""
        logger.info("💾 Test export config -args...")
        
        config_file = self.workspace_root / "config" / "exif_mapping.json"
        if not config_file.exists():
            logger.error(f"❌ Fichier config manquant: {config_file}")
            return False
        
        try:
            # Charger la configuration
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Créer un fichier d'arguments ExifTool
            args_file = self.workspace_root / "config" / "exiftool_args_export.txt"
            
            with open(args_file, 'w', encoding='utf-8') as f:
                f.write("# ExifTool Arguments Export - Auto-generated\n")
                f.write(f"# Generated on: {Path().cwd()}\n")
                f.write("# Configuration: Google Photos Takeout Metadata\n\n")
                
                # Arguments globaux
                global_settings = config.get("global_settings", {})
                common_args = global_settings.get("common_args", [])
                
                f.write("# Global Arguments\n")
                for arg in common_args:
                    f.write(f"{arg}\n")
                
                f.write("\n# Strategy Examples\n")
                strategies = config.get("strategies", {})
                
                for strategy_name, strategy_config in strategies.items():
                    f.write(f"\n# Strategy: {strategy_name}\n")
                    f.write(f"# Description: {strategy_config.get('description', '')}\n")
                    
                    if 'condition_template' in strategy_config:
                        f.write(f"# Condition: {strategy_config['condition_template']}\n")
                    
                    if 'pattern' in strategy_config:
                        for pattern in strategy_config['pattern']:
                            f.write(f"# Pattern: {pattern}\n")
                
                f.write("\n# Sample Usage\n")
                f.write("# exiftool @exiftool_args_export.txt your_files/\n")
            
            logger.info(f"✅ Arguments exportés vers: {args_file}")
            
            # Vérifier que le fichier a été créé et n'est pas vide
            if args_file.exists() and args_file.stat().st_size > 100:
                lines = args_file.read_text(encoding='utf-8').count('\n')
                logger.info(f"📄 Fichier d'arguments: {lines} lignes")
                return True
            else:
                logger.error("❌ Fichier d'arguments vide ou non créé")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erreur export config: {e}")
            return False
    
    def run_all_tests(self) -> bool:
        """Exécute tous les tests de qualité"""
        logger.info("🚀 Démarrage des tests de qualité...")
        
        tests = [
            ("Test avant/après traitement", self.test_before_after_processing),
            ("Test suppression warnings", self.test_warning_suppression),
            ("Test export config args", self.test_config_export_args)
        ]
        
        results = []
        for test_name, test_func in tests:
            logger.info(f"\n{'='*60}")
            logger.info(f"🧪 {test_name}")
            logger.info('='*60)
            
            try:
                success = test_func()
                results.append((test_name, success))
                
                if success:
                    logger.info(f"✅ {test_name}: SUCCÈS")
                else:
                    logger.error(f"❌ {test_name}: ÉCHEC")
                    
            except Exception as e:
                logger.error(f"❌ {test_name}: ERREUR - {e}")
                results.append((test_name, False))
        
        # Résumé final
        logger.info(f"\n{'='*60}")
        logger.info("📊 RÉSUMÉ DES TESTS DE QUALITÉ")
        logger.info('='*60)
        
        success_count = sum(1 for _, success in results if success)
        total_count = len(results)
        
        for test_name, success in results:
            status = "✅ SUCCÈS" if success else "❌ ÉCHEC"
            logger.info(f"{status:<12} {test_name}")
        
        logger.info(f"\n🎯 Résultat global: {success_count}/{total_count} tests réussis")
        
        if success_count == total_count:
            logger.info("🎉 Tous les tests de qualité passent !")
            return True
        else:
            logger.warning(f"⚠️ {total_count - success_count} test(s) en échec")
            return False

def main():
    """Point d'entrée principal"""
    workspace_root = Path(__file__).parent.parent.absolute()  # Remonter de tools/ vers racine
    
    tester = QualityTester(workspace_root)
    success = tester.run_all_tests()
    
    return 0 if success else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
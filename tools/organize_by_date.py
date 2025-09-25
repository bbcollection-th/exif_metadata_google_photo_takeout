#!/usr/bin/env python3
"""
Script pour organiser les photos par date (Année/Mois) basé sur les métadonnées EXIF.

Utilise ExifTool pour lire les dates de création et organise les fichiers dans une structure :
source_folder/
├── 2023-01/
├── 2023-02/
├── 2024-12/
└── unknown_date/  (pour les fichiers sans date)

Usage:
    python organize_by_date.py /chemin/vers/photos
    python organize_by_date.py /chemin/vers/photos --dry-run
    python organize_by_date.py /chemin/vers/photos --target-dir /autre/dossier
"""

import argparse
import json
import logging
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class PhotoDateOrganizer:
    """Organisateur de photos par date basé sur ExifTool."""
    
    # Extensions de fichiers supportées
    SUPPORTED_EXTENSIONS = {
        '.jpg', '.jpeg', '.jpe',
        '.png', '.gif', '.bmp', '.tiff', '.tif',
        '.heic', '.heif', '.webp',
        '.mp4', '.mov', '.avi', '.mkv', '.wmv', '.m4v',
        '.raw', '.cr2', '.nef', '.arw', '.dng'
    }
    
    # Tags de date par ordre de priorité (du plus précis au moins précis)
    DATE_TAGS = [
        'DateTimeOriginal',
        'CreateDate', 
        'ModifyDate',
        'QuickTime:CreateDate',
        'QuickTime:CreationDate',
        'XMP:DateCreated',
        'IPTC:DateCreated',
        'FileCreateDate',  # Ajouté pour les dates EXIF corrompues
        'FileModifyDate'
    ]
    
    def __init__(self, source_dir: Path, target_dir: Optional[Path] = None, dry_run: bool = False, resume: bool = False):
        """
        Initialise l'organisateur.
        
        Args:
            source_dir: Dossier source contenant les photos
            target_dir: Dossier de destination (par défaut: même que source)
            dry_run: Mode simulation (ne déplace pas réellement les fichiers)
            resume: Reprendre un traitement interrompu
        """
        self.source_dir = Path(source_dir).resolve()
        self.target_dir = Path(target_dir).resolve() if target_dir else self.source_dir
        self.dry_run = dry_run
        self.resume = resume
        self.progress_file = self.target_dir / ".organize_progress.json"
        
        if not self.source_dir.exists():
            raise FileNotFoundError(f"Dossier source non trouvé: {self.source_dir}")
        
        if not self._check_exiftool():
            raise RuntimeError("ExifTool non trouvé. Installez-le avec: pip install pyexiftool ou scoop install exiftool")
        
        # Vérifications de sécurité
        self._validate_directories()
        self._check_permissions()
    
    def _check_exiftool(self) -> bool:
        """Vérifie que ExifTool est installé et accessible."""
        try:
            result = subprocess.run(['exiftool', '-ver'], 
                                  capture_output=True, text=True, check=True)
            version = result.stdout.strip()
            logger.info(f"ExifTool version {version} détecté")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _validate_directories(self) -> None:
        """Valide que les dossiers source et destination sont cohérents."""
        source_resolved = self.source_dir.resolve()
        target_resolved = self.target_dir.resolve()
        
        # Si source = destination, c'est OK (organisation en sous-dossiers)
        if source_resolved == target_resolved:
            logger.info("Organisation dans le même dossier : création de sous-dossiers par date")
            return
        
        # Éviter que target soit un sous-dossier strict de source (problématique)
        try:
            relative_path = target_resolved.relative_to(source_resolved)
            # Si on arrive ici, target est un sous-dossier de source
            if str(relative_path) != ".":  # Pas le même dossier
                raise ValueError(f"Le dossier de destination ({target_resolved}) ne peut pas être un sous-dossier du source ({source_resolved})")
        except ValueError as e:
            if "is not in the subpath" in str(e) or "does not start with" in str(e):
                # C'est normal, target n'est pas un sous-dossier de source
                pass
            else:
                # Re-lancer l'erreur si c'est notre ValueError personnalisé
                raise
    
    def _check_permissions(self) -> None:
        """Vérifie les permissions de lecture/écriture."""
        # Vérifier lecture source
        if not self.source_dir.is_dir():
            raise PermissionError(f"Impossible de lire le dossier source: {self.source_dir}")
        
        # Vérifier écriture destination (créer un fichier test)
        if not self.dry_run:
            test_dir = self.target_dir / "test_write_permissions"
            try:
                test_dir.mkdir(exist_ok=True)
                test_file = test_dir / "test_file.txt"
                test_file.write_text("test")
                test_file.unlink()
                test_dir.rmdir()
            except (PermissionError, OSError) as e:
                raise PermissionError(f"Permissions insuffisantes pour écrire dans: {self.target_dir}. Erreur: {e}")
    
    def _check_disk_space(self, files: List[Path]) -> None:
        """Vérifie l'espace disque disponible."""
        if self.dry_run:
            return
        
        # Vérifier si source et destination sont sur le même disque
        try:
            source_drive = self.source_dir.resolve().parts[0]  # ex: C:\
            target_drive = self.target_dir.resolve().parts[0]
            
            if source_drive == target_drive:
                logger.info(f"Même disque ({source_drive}) → Déplacement rapide, pas de vérification d'espace")
                return
                
            logger.info(f"Disques différents ({source_drive} → {target_drive}) → Vérification espace...")
            
            # Calculer la taille totale seulement si copie entre disques différents
            total_size = 0
            sample_count = 0
            
            for file_path in files[:50]:  # Échantillon de 50 fichiers max
                try:
                    total_size += file_path.stat().st_size
                    sample_count += 1
                except (OSError, FileNotFoundError):
                    continue
            
            if sample_count == 0:
                return
            
            # Estimer la taille totale
            estimated_total = (total_size / sample_count) * len(files)
            
            # Vérifier l'espace disponible (avec marge de 20%)
            _, _, free_space = shutil.disk_usage(self.target_dir)
            required_space = estimated_total * 1.2  # Marge de 20%
            
            if free_space < required_space:
                size_mb = required_space / (1024 * 1024)
                free_mb = free_space / (1024 * 1024)
                raise RuntimeError(f"Espace disque insuffisant pour copie entre disques. Requis: {size_mb:.1f}MB, Disponible: {free_mb:.1f}MB")
                
        except OSError:
            logger.warning("Impossible de vérifier l'espace disque disponible")
    
    def _save_progress(self, processed_files: set, stats: dict, successful_moves: int) -> None:
        """Sauvegarde la progression pour reprise après interruption."""
        try:
            import json
            progress_data = {
                'processed_files': list(processed_files),
                'stats': stats,
                'successful_moves': successful_moves,
                'timestamp': datetime.now().isoformat()
            }
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Impossible de sauvegarder la progression: {e}")
    
    def _get_all_image_files(self) -> List[Path]:
        """Trouve tous les fichiers images/vidéos dans le dossier source (récursivement)."""
        files = []
        
        logger.info(f"Recherche de fichiers dans {self.source_dir}...")
        
        for file_path in self.source_dir.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                files.append(file_path)
        
        logger.info(f"{len(files)} fichiers supportés trouvés")
        return files
    
    def _extract_dates_batch(self, files: List[Path]) -> Dict[str, Optional[datetime]]:
        """
        Extrait les dates de création pour un lot de fichiers via ExifTool.
        
        Returns:
            Dict[chemin_fichier, date_ou_None]
        """
        if not files:
            return {}
        
        logger.info(f"Extraction des dates pour {len(files)} fichiers...")
        
        # Construire la commande ExifTool pour extraction en lot
        cmd = ['exiftool', '-json', '-charset', 'utf8']
        
        # Ajouter les tags de date que nous voulons extraire
        for tag in self.DATE_TAGS:
            cmd.extend(['-' + tag])
        
        # Ajouter les chemins des fichiers
        for file_path in files:
            cmd.append(str(file_path))
        
        try:
            # Timeout de 5 minutes pour éviter les blocages sur gros fichiers
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=300)
            metadata_list = json.loads(result.stdout)
            
            dates_dict = {}
            
            for metadata in metadata_list:
                source_file = metadata.get('SourceFile')
                if not source_file:
                    continue
                
                # Chercher la première date valide dans l'ordre de priorité
                best_date = None
                
                # Debug: afficher toutes les clés disponibles
                logger.debug(f"Métadonnées pour {Path(source_file).name}: {list(metadata.keys())}")
                
                for tag in self.DATE_TAGS:
                    date_str = metadata.get(tag)
                    if date_str:
                        logger.debug(f"  Trouvé {tag}: {date_str}")
                        parsed_date = self._parse_date_string(date_str)
                        if parsed_date:
                            logger.debug(f"  Date parsée: {parsed_date}")
                            best_date = parsed_date
                            break
                        else:
                            logger.debug(f"  Échec parsing de: {date_str}")
                
                if not best_date:
                    logger.debug(f"  Aucune date valide trouvée pour {Path(source_file).name}")
                
                dates_dict[source_file] = best_date
            
            return dates_dict
            
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout ExifTool (>5min) pour {len(files)} fichiers. Réduisez la taille du lot.")
            return {}
        except subprocess.CalledProcessError as e:
            if "Argument list too long" in str(e) or len(cmd) > 8000:
                logger.error(f"Ligne de commande trop longue ({len(files)} fichiers). Réduisez batch_size.")
                return {}
            logger.error(f"Erreur ExifTool: {e}")
            logger.error(f"Stderr: {e.stderr}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Erreur parsing JSON: {e}")
            return {}
    
    def _parse_date_string(self, date_str: str) -> Optional[datetime]:
        """Parse une chaîne de date ExifTool en objet datetime."""
        if not date_str or date_str == '0000:00:00 00:00:00':
            return None
        
        # Formats de date couramment trouvés dans ExifTool
        date_formats = [
            '%Y:%m:%d %H:%M:%S',      # 2023:12:25 14:30:45
            '%Y-%m-%d %H:%M:%S',      # 2023-12-25 14:30:45
            '%Y:%m:%d %H:%M:%S%z',    # Avec timezone
            '%Y-%m-%d %H:%M:%S%z',    
            '%Y:%m:%d',               # Date seulement
            '%Y-%m-%d',
        ]
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                
                # Filtrer les dates aberrantes (avant 2010 ou futures)
                if parsed_date.year < 2010 or parsed_date.year > datetime.now().year + 1:
                    logger.debug(f"Date suspecte ignorée: {date_str} (année {parsed_date.year})")
                    return None
                
                return parsed_date
            except ValueError:
                continue
        
        logger.warning(f"Format de date non reconnu: {date_str}")
        return None
    
    def _get_target_folder(self, date: Optional[datetime]) -> str:
        """Détermine le dossier de destination basé sur la date."""
        if date is None:
            return "unknown_date"
        
        return f"{date.year:04d}-{date.month:02d}"
    
    def _move_file(self, source: Path, target_folder: str) -> bool:
        """
        Déplace un fichier vers le dossier de destination.
        
        Returns:
            True si succès, False sinon
        """
        target_dir = self.target_dir / target_folder
        target_path = target_dir / source.name
        
        # Créer le dossier de destination s'il n'existe pas
        if not self.dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
        
        # Gérer les conflits de noms
        counter = 1
        original_target = target_path
        
        while target_path.exists():
            stem = original_target.stem
            suffix = original_target.suffix
            target_path = target_dir / f"{stem}_{counter:03d}{suffix}"
            counter += 1
        
        try:
            if self.dry_run:
                logger.info(f"[DRY-RUN] Déplacerait: {source} -> {target_path}")
            else:
                # Vérifier que le fichier source existe toujours
                if not source.exists():
                    logger.error(f"Fichier source disparu: {source}")
                    return False
                
                shutil.move(str(source), str(target_path))
                logger.info(f"Déplacé: {source.name} -> {target_folder}/")
            
            return True
            
        except PermissionError as e:
            logger.error(f"Permissions insuffisantes pour {source.name}: {e}")
            return False
        except FileNotFoundError as e:
            logger.error(f"Fichier non trouvé {source.name}: {e}")
            return False
        except OSError as e:
            if "being used by another process" in str(e) or e.errno == 32:
                logger.error(f"Fichier verrouillé ou en cours d'utilisation: {source.name}")
            else:
                logger.error(f"Erreur système pour {source.name}: {e}")
            return False
        except UnicodeError as e:
            logger.error(f"Caractères spéciaux problématiques dans {source.name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Erreur inattendue pour {source.name}: {e}")
            return False
    
    def organize_photos(self) -> Dict[str, int]:
        """
        Organise toutes les photos par date.
        
        Returns:
            Statistiques: {folder_name: count, ...}
        """
        # Trouver tous les fichiers
        files = self._get_all_image_files()
        
        if not files:
            logger.warning("Aucun fichier supporté trouvé")
            return {}
        
        # Vérifier l'espace disque avant de commencer
        self._check_disk_space(files)
        
        # Mode streaming : traiter et déplacer immédiatement (résistant aux coupures)
        batch_size = 50
        stats = {}
        successful_moves = 0
        
        # Système de reprise après interruption
        processed_files = set()
        if self.resume and self.progress_file.exists():
            try:
                import json
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress_data = json.load(f)
                    processed_files = set(progress_data.get('processed_files', []))
                    stats = progress_data.get('stats', {})
                    successful_moves = progress_data.get('successful_moves', 0)
                logger.info(f"Reprise: {len(processed_files)} fichiers déjà traités")
            except Exception as e:
                logger.warning(f"Impossible de lire le fichier de progression: {e}")
        
        # Filtrer les fichiers déjà traités
        if processed_files:
            files = [f for f in files if str(f) not in processed_files]
            logger.info(f"Fichiers restants à traiter: {len(files)}")
        
        for i in range(0, len(files), batch_size):
            batch = files[i:i + batch_size]
            logger.info(f"Traitement batch {i//batch_size + 1}/{(len(files)-1)//batch_size + 1} ({len(batch)} fichiers)")
            
            # Extraire les dates du batch
            batch_dates = self._extract_dates_batch(batch)
            
            # Déplacer immédiatement les fichiers du batch
            for file_path in batch:
                # Normaliser le chemin pour correspondre à ExifTool (Unix slashes)
                file_str_normalized = str(file_path).replace('\\', '/')
                date = batch_dates.get(file_str_normalized)
                target_folder = self._get_target_folder(date)
                
                if target_folder not in stats:
                    stats[target_folder] = 0
                
                if self._move_file(file_path, target_folder):
                    stats[target_folder] += 1
                    successful_moves += 1
                
                # Marquer comme traité
                processed_files.add(str(file_path))
            
            # Sauvegarder progression tous les 10 batches (pour reprise)
            if not self.dry_run and (i // batch_size) % 10 == 0:
                self._save_progress(processed_files, stats, successful_moves)
            
            # Afficher progression
            # Total = fichiers de cette session + fichiers déjà traités (reprise)
            total_original = len(files) + len(processed_files) if processed_files else len(files)
            current_total = successful_moves + len(processed_files) if processed_files else successful_moves
            progress = (current_total / total_original) * 100
            logger.info(f"Progression: {progress:.1f}% ({current_total}/{total_original} traités)")
            
            # Libérer la mémoire du batch
            del batch_dates
        
        # Nettoyer le fichier de progression à la fin
        if not self.dry_run and self.progress_file.exists():
            self.progress_file.unlink()
            logger.info("Traitement terminé - fichier de progression supprimé")
        
        # Afficher les statistiques
        logger.info("\n" + "="*50)
        logger.info("STATISTIQUES FINALES")
        logger.info("="*50)
        
        for folder, count in sorted(stats.items()):
            logger.info(f"{folder:20} : {count:4d} fichiers")
        
        # Calculer le total original (cette session + précédentes)
        total_original_files = len(files) + len(processed_files) if processed_files else len(files)
        total_moved = successful_moves + len(processed_files) if processed_files else successful_moves
        logger.info(f"\nTotal traité: {total_moved}/{total_original_files} fichiers")
        
        if self.dry_run:
            logger.info("\n⚠️  MODE DRY-RUN: Aucun fichier n'a été réellement déplacé")
        
        return stats


def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Organise les photos par date (AAAA-MM) basé sur les métadonnées EXIF",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python organize_by_date.py /chemin/vers/photos
  python organize_by_date.py /chemin/vers/photos --dry-run
  python organize_by_date.py /chemin/vers/photos --target-dir /dossier/organise
        """
    )
    
    parser.add_argument(
        'source_dir',
        help='Dossier source contenant les photos à organiser'
    )
    
    parser.add_argument(
        '--target-dir',
        help='Dossier de destination (par défaut: même que source)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Mode simulation (affiche les actions sans les exécuter)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Mode verbose (logs détaillés)'
    )
    
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Reprendre un traitement interrompu (utilise .organize_progress.json)'
    )
    
    parser.add_argument(
        '--fix-dates',
        action='store_true',
        help='Ignorer les dates EXIF aberrantes (<2010) et utiliser FileCreateDate'
    )
    
    args = parser.parse_args()
    
    # Configurer le niveau de log
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        # DEBUG temporaire pour diagnostiquer le problème des dates
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Créer l'organisateur
        organizer = PhotoDateOrganizer(
            source_dir=args.source_dir,
            target_dir=args.target_dir,
            dry_run=args.dry_run,
            resume=args.resume
        )
        
        # Exécuter l'organisation
        organizer.organize_photos()
        
    except Exception as e:
        logger.error(f"Erreur: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
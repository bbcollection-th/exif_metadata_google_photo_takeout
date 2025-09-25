import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple, Union
from datetime import datetime
import shutil

from .exif_writer import build_exiftool_args
from .config_loader import ConfigLoader
from .sidecar import find_albums_for_directory, parse_sidecar
from .processor import (
    IMAGE_EXTS,
    fix_file_extension_mismatch,
    _is_sidecar_file,
    _enrich_with_reverse_geocode,
)
from . import sidecar_safety
from . import statistics
from .file_organizer import FileOrganizer


logger = logging.getLogger(__name__)


def _retry_batch_with_format_correction(batch: List[Tuple[Path, Path, List[str]]], immediate_delete: bool, efile_dir: Union[str, Path]) -> int:
    """Retraiter un lot en forçant la correction des extensions de fichiers incorrectes.
    
    Cette fonction est appelée quand ExifTool détecte des incohérences de format
    (ex: fichier .PNG qui est en réalité un JPEG).
    """
    corrected_batch = []
    config_loader = ConfigLoader()
    
    for media_path, json_path, original_args in batch:
        try:
            # Forcer la correction d'extension même si elle n'a pas été détectée avant
            from .processor import detect_file_type
            actual_ext = detect_file_type(media_path)
            
            if actual_ext and actual_ext != media_path.suffix.lower():
                # Extension incorrecte détectée, corriger
                new_media_path = media_path.with_suffix(actual_ext)
                new_json_path = json_path.with_name(new_media_path.name + ".supplemental-metadata.json")
                
                logger.info(f"🔧 Correction forcée d'extension : {media_path.name} → {new_media_path.name}")
                
                # Renommer les fichiers
                media_path.rename(new_media_path)
                
                # Mettre à jour le JSON
                import json
                with open(json_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                json_data['title'] = new_media_path.name
                
                with open(new_json_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=2, ensure_ascii=False)
                json_path.unlink()
                
                # Regénérer les arguments ExifTool avec le nouveau chemin
                meta = parse_sidecar(new_json_path)
                new_args = build_exiftool_args(meta, media_path=new_media_path, use_localTime=False, config_loader=config_loader)
                
                corrected_batch.append((new_media_path, new_json_path, new_args))
                statistics.stats.add_fixed_extension(media_path.name, new_media_path.name)
                
            else:
                # Pas de correction nécessaire, garder tel quel
                corrected_batch.append((media_path, json_path, original_args))
                
        except Exception as e:
            logger.warning(f"❌ Échec de la correction d'extension pour {media_path.name}: {e}")
            # En cas d'échec de correction, marquer comme échoué
            statistics.stats.add_failed_file(media_path, "format_correction_failed", str(e))
            continue
    
    if corrected_batch:
        logger.info(f"🔄 Nouvelle tentative de traitement avec {len(corrected_batch)} fichier(s) corrigé(s)...")
        return process_batch(corrected_batch, immediate_delete, efile_dir)
    else:
        logger.warning("❌ Aucun fichier n'a pu être corrigé pour un nouveau traitement")
        return 0


def process_batch(batch: List[Tuple[Path, Path, List[str]]], immediate_delete: bool, efile_dir: Union[str, Path] = "logs") -> int:
    """Traiter un lot de fichiers avec exiftool via un fichier d'arguments."""
    if not batch:
        return 0

    # Convertir efile_dir en Path si nécessaire
    efile_dir = Path(efile_dir)

    argfile_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8', suffix=".txt") as argfile:
            argfile_path = argfile.name
        
        with open(argfile_path, 'w', encoding='utf-8') as argfile:
            for media_path, _, args in batch:
                for arg in args:
                    argfile.write(f"{arg}\n")
                argfile.write(f"{media_path}\n")
                argfile.write("-execute\n")

        logger.info(f"📦 Traitement d'un lot de {len(batch)} fichier(s)...")

        # ✅ IMPLÉMENTATION -efile pour journalisation et reprises intelligentes
        # Répertoire de sortie pour les fichiers -efile (ex: logs/)
        # S'assurer que le dossier existe
        try:
            efile_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            # Ne pas interrompre le traitement si création impossible; fallback sur cwd
            pass

        cmd = [
            "exiftool",
            # Charset settings MUST come before -@ for proper ExifTool behavior.
            "-charset", "filename=UTF8",    # For Unicode filenames (must be before -@)
            "-charset", "iptc=UTF8",        # For IPTC writing
            "-charset", "exif=UTF8",        # For EXIF writing
            "-codedcharacterset=utf8",      # For IPTC encoding (must be before -@)
            "-@", argfile_path,
            "-common_args",                 # After -@ : applied to each block
            "-overwrite_original",
            "-q", "-q",
            "-api", "NoDups=1",            # For intra-batch deduplication
            "-efile1", str(efile_dir / "error_files.txt"),                 # errors = 1
            "-efile2", str(efile_dir / "unchanged_files.txt"),            # unchanged = 2  
            "-efile4", str(efile_dir / "failed_condition_files.txt"),     # failed -if condition = 4
            "-efile8", str(efile_dir / "updated_files.txt")               # updated = 8
        ]
        
        timeout_seconds = 60 + (len(batch) * 5)
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=timeout_seconds, encoding='utf-8'
        )
        
        # Analyser la sortie pour compter les fichiers traités
        processed_count = 0
        if result.stdout and result.stdout.strip():
            stdout_lines = result.stdout.strip().split('\n')
            for line in stdout_lines:
                if 'image files updated' in line.lower() or 'files updated' in line.lower():
                    # Extraire le nombre de fichiers mis à jour
                    try:
                        numbers = [int(word) for word in line.split() if word.isdigit()]
                        if numbers:
                            processed_count = numbers[0]
                    except (ValueError, IndexError):
                        pass
                    logger.info(f"✅ {line.strip()}")
        
        # Si on n'a pas pu extraire le nombre, utiliser la taille du lot
        if processed_count == 0:
            processed_count = len(batch)
            logger.info(f"✅ Lot de {len(batch)} fichier(s) traité avec succès")
        
        # Mettre à jour les statistiques pour chaque fichier du lot
        for media_path, _, _ in batch:
            is_image = media_path.suffix.lower() in IMAGE_EXTS
            statistics.stats.add_processed_file(is_image)

        # Gestion des sidecars après traitement réussi
        if immediate_delete:
            # Mode destructeur : suppression immédiate
            cleaned_count = 0
            for _, json_path, _ in batch:
                try:
                    json_path.unlink()
                    cleaned_count += 1
                except OSError as e:
                    logger.warning(f"Échec de la suppression du fichier de métadonnées {json_path.name}: {e}")
            statistics.stats.sidecars_cleaned += cleaned_count
        else:
            # Mode sécurisé : marquage avec préfixe OK_
            marked_count = 0
            for _, json_path, _ in batch:
                try:
                    if sidecar_safety.mark_sidecar_as_processed(json_path):
                        marked_count += 1
                except OSError as e:
                    logger.warning(f"Échec du marquage du sidecar {json_path.name}: {e}")
            statistics.stats.sidecars_cleaned += marked_count  # Réutilise le compteur pour "traités"
        
        return len(batch)

    except FileNotFoundError as exc:
        raise RuntimeError("exiftool introuvable") from exc
    except subprocess.CalledProcessError as exc:
        stderr_msg = exc.stderr or ""
        stdout_msg = exc.stdout or ""
        
        # Analyser le type d'erreur pour donner un message plus clair
        if "files failed condition" in stderr_msg or "files failed condition" in stdout_msg:
            logger.info(f"ℹ️ Lot traité avec conditions non remplies (normal en mode append-only). "
                       f"Certaines métadonnées existaient déjà pour {len(batch)} fichier(s).")
            # En mode append-only, considérer ceci comme un succès partiel
            for media_path, _, _ in batch:
                is_image = media_path.suffix.lower() in IMAGE_EXTS
                statistics.stats.add_processed_file(is_image)
            
            # Nettoyer les sidecars si demandé (comme dans le cas de succès normal)
            if immediate_delete:
                cleaned_count = 0
                for _, json_path, _ in batch:
                    try:
                        json_path.unlink()
                        cleaned_count += 1
                    except OSError as e:
                        logger.warning(f"Échec de la suppression du fichier de métadonnées {json_path.name}: {e}")
                statistics.stats.sidecars_cleaned += cleaned_count
            else:
                # Mode sécurisé : marquage avec préfixe OK_
                marked_count = 0
                for _, json_path, _ in batch:
                    try:
                        if sidecar_safety.mark_sidecar_as_processed(json_path):
                            marked_count += 1
                    except OSError as e:
                        logger.warning(f"Échec du marquage du sidecar {json_path.name}: {e}")
                statistics.stats.sidecars_cleaned += marked_count
            
            return len(batch)
        elif "doesn't exist or isn't writable" in stderr_msg:
            logger.warning(f"⚠️ Certains champs de métadonnées non supportés par les fichiers du lot. "
                          f"Normal pour vidéos ou certains formats. Détails: {stderr_msg.strip()}")
            # Considérer comme un succès partiel
            for media_path, _, _ in batch:
                is_image = media_path.suffix.lower() in IMAGE_EXTS  
                statistics.stats.add_processed_file(is_image)
            
            # Nettoyer les sidecars si demandé (comme dans le cas de succès normal)
            if immediate_delete:
                cleaned_count = 0
                for _, json_path, _ in batch:
                    try:
                        json_path.unlink()
                        cleaned_count += 1
                    except OSError as e:
                        logger.warning(f"Échec de la suppression du fichier de métadonnées {json_path.name}: {e}")
                statistics.stats.sidecars_cleaned += cleaned_count
            else:
                # Mode sécurisé : marquage avec préfixe OK_
                marked_count = 0
                for _, json_path, _ in batch:
                    try:
                        if sidecar_safety.mark_sidecar_as_processed(json_path):
                            marked_count += 1
                    except OSError as e:
                        logger.warning(f"Échec du marquage du sidecar {json_path.name}: {e}")
                statistics.stats.sidecars_cleaned += marked_count
            
            return len(batch)
        elif "character(s) could not be encoded" in stderr_msg:
            error_type = "encoding_error"
            error_msg = "Problème d'encodage de caractères (émojis, accents)"
            logger.warning(f"⚠️ {error_msg}. Détails: {stderr_msg.strip()}")
        elif "not a valid png" in stderr_msg.lower() and "looks more like a jpeg" in stderr_msg.lower():
            error_type = "file_format_mismatch"
            error_msg = "Extension de fichier incorrecte (PNG qui est en réalité un JPEG)"
            logger.warning(f"⚠️ {error_msg}. Réessai avec correction automatique d'extension...")
            
            # Tentative de retraitement avec correction forcée des extensions
            return _retry_batch_with_format_correction(batch, immediate_delete, efile_dir)
        else:
            error_type = "exiftool_error"
            error_msg = f"Erreur exiftool (code {exc.returncode}): {stderr_msg.strip() or 'Erreur inconnue'}"
            logger.exception(f"❌ Échec du traitement par lot de {len(batch)} fichier(s). {error_msg}")
        
        # Marquer tous les fichiers du lot comme échoués
        for media_path, _, _ in batch:
            statistics.stats.add_failed_file(media_path, error_type, error_msg)
        
        # NE PAS nettoyer les sidecars en cas d'échec exiftool - les garder pour retry
        # LOGIQUE MÉTIER: On ne supprime le sidecar QUE si le traitement a réussi
        return 0
    finally:
        if argfile_path and Path(argfile_path).exists():
            Path(argfile_path).unlink()


def process_directory_batch(root: Path, use_localTime: bool = False,  immediate_delete: bool = False, organize_files: bool = False, geocode: bool = False) -> None:
    """Traiter récursivement tous les fichiers sidecar sous ``root`` par lots.
    
    Args:
        root: Répertoire racine à parcourir
        use_localTime: Convertir les dates en heure locale au lieu d'UTC
        immediate_delete: Mode destructeur - supprimer immédiatement les JSON après succès
                         (par défaut: mode sécurisé avec préfixe OK_)
        organize_files: Organiser les fichiers selon leur statut (archivé/supprimé/vérouillé)
        geocode: Activer le géocodage inverse si l'API est disponible
    """
    batch: List[Tuple[Path, Path, List[str]]] = []
    BATCH_SIZE = 100
    config_loader = ConfigLoader()
    config_loader.load_config()   
    # Initialiser les statistiques
    statistics.stats.start_processing()
    
    # Dossier de destination pour les fichiers -efile (configurable via exif_mapping.json)
    try:
        cfg = ConfigLoader()
        cfg.load_config()
        efile_dir_setting = (
            cfg.config.get('global_settings', {}).get('efile_output_dir', 'logs')
        )
    except Exception:
        efile_dir_setting = 'logs'

    efile_dir = Path(efile_dir_setting)
    if not efile_dir.is_absolute():
        efile_dir = root / efile_dir
    
    # Initialiser l'organisateur de fichiers si demandé
    file_organizer = None
    if organize_files:
        file_organizer = FileOrganizer(root)
        logger.info("📁 Mode organisation activé : les fichiers seront organisés selon leur statut")
    
    # Exclure les sidecars déjà traités (préfixe OK_)
    all_sidecar_files = [path for path in root.rglob("*.json") if _is_sidecar_file(path)]
    sidecar_files = [path for path in all_sidecar_files if not sidecar_safety.is_sidecar_processed(path)]
    
    # Afficher les statistiques de filtrage et les comptabiliser
    processed_count = len(all_sidecar_files) - len(sidecar_files)
    if processed_count > 0:
        logger.info("📋 %d sidecars déjà traités ignorés (préfixe OK_)", processed_count)
        # Ajouter les fichiers déjà traités aux statistiques
        for path in all_sidecar_files:
            if sidecar_safety.is_sidecar_processed(path):
                statistics.stats.add_skipped_file(path, "Déjà traité (préfixe OK_)")
    
    statistics.stats.total_sidecars_found = len(sidecar_files)
    
    if statistics.stats.total_sidecars_found == 0:
        logger.warning("Aucun fichier de métadonnées (.json) trouvé dans %s", root)
        statistics.stats.end_processing()
        return

    logger.info("🔍 Traitement par lots de %d fichier(s) de métadonnées dans %s", statistics.stats.total_sidecars_found, root)

    for json_path in sidecar_files:
        try:
            meta = parse_sidecar(json_path)
            _enrich_with_reverse_geocode(meta, json_path, geocode)

            directory_albums = find_albums_for_directory(json_path.parent)
            meta.albums.extend(directory_albums)
            
            media_path = json_path.with_name(meta.title)
            if not media_path.exists():
                error_msg = f"Fichier image introuvable : {meta.title}"
                statistics.stats.add_failed_file(json_path, "file_not_found", error_msg)
                logger.warning(f"❌ {error_msg}")
                continue

            fixed_media_path, fixed_json_path = fix_file_extension_mismatch(media_path, json_path)
            if fixed_json_path != json_path:
                meta = parse_sidecar(fixed_json_path)
                _enrich_with_reverse_geocode(meta, fixed_json_path, geocode)
                meta.albums.extend(find_albums_for_directory(fixed_json_path.parent))
            
            # Organisation des fichiers si demandée
            if file_organizer and (meta.archived or meta.trashed or meta.inLockedFolder):
                try:
                    moved_media, moved_json = file_organizer.move_file_with_sidecar(fixed_media_path, fixed_json_path, meta)
                    if moved_media and moved_json:
                        # Mettre à jour les chemins pour la suite du traitement
                        fixed_media_path = moved_media
                        fixed_json_path = moved_json
                        logger.info(f"📁 Fichier organisé : {media_path.name} → {moved_media.parent.name}/")
                except (OSError, shutil.Error) as e:
                    logger.warning(f"⚠️ Échec de l'organisation du fichier {media_path.name}: {e}")
            
            args = build_exiftool_args(
                meta, media_path=fixed_media_path, use_localTime=use_localTime, config_loader=config_loader
            )

            if args:
                batch.append((fixed_media_path, fixed_json_path, args))
            else:
                # Aucun tag à écrire pour ce sidecar
                statistics.stats.total_skipped += 1
                statistics.stats.skipped_files.append(json_path.name)

            if len(batch) >= BATCH_SIZE:
                process_batch(batch, immediate_delete, efile_dir=efile_dir)
                batch = []

        except (ValueError, RuntimeError) as exc:
            error_msg = f"Erreur de préparation : {exc}"
            statistics.stats.add_failed_file(json_path, "preparation_error", error_msg)
            logger.warning("❌ Échec de la préparation de %s : %s", json_path.name, exc)

    if batch:
        process_batch(batch, immediate_delete, efile_dir=efile_dir)

    statistics.stats.end_processing()
    
    # Affichage du résumé
    statistics.stats.print_console_summary()
    
    # Générer les scripts de sécurité si des sidecars ont été traités (mode sécurisé uniquement)
    if not immediate_delete and statistics.stats.sidecars_cleaned > 0:
        logger.info("\n🔐 === SYSTÈME DE SÉCURITÉ ===")
        
        # Générer les scripts
        cleanup_script = sidecar_safety.generate_cleanup_script(root)
        rollback_script = sidecar_safety.generate_rollback_script(root)
        
        if cleanup_script and rollback_script:
            logger.info("📜 Scripts de gestion générés :")
            logger.info("   • Nettoyage : %s", cleanup_script)
            logger.info("   • Rollback  : %s", rollback_script)
            logger.info("")
            logger.info("⚠️  Les sidecars traités ont été marqués avec le préfixe 'OK_'")
            logger.info("   Vérifiez le traitement puis utilisez les scripts pour:")
            logger.info("   1. Supprimer définitivement les sidecars traités (cleanup)")
            logger.info("   2. Restaurer les noms originaux en cas d'erreur (rollback)")
        
        # Afficher le résumé de sécurité
        nb_processed, nb_pending, messages = sidecar_safety.generate_scripts_summary(root)
        for message in messages:
            logger.info(message)
    
    # Créer un dossier logs s'il n'existe pas
    logs_dir = root / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Sauvegarde du rapport détaillé avec un nom incluant la date
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = logs_dir / f"traitement_log_{timestamp}.json"
    statistics.stats.save_detailed_report(log_file)

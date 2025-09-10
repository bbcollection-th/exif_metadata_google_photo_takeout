import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple
from datetime import datetime

from .exif_writer import build_exiftool_args
from .sidecar import find_albums_for_directory, parse_sidecar
from .processor import IMAGE_EXTS, fix_file_extension_mismatch, _is_sidecar_file 
from . import statistics


logger = logging.getLogger(__name__)



def process_batch(batch: List[Tuple[Path, Path, List[str]]], clean_sidecars: bool) -> int:
    """Traiter un lot de fichiers avec exiftool via un fichier d'arguments."""
    if not batch:
        return 0

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
        cmd = [
            "exiftool",
            "-charset", "filename=UTF8",    # ✅ AVANT -@ (Windows/Unicode, noms de fichiers)
            "-@", argfile_path,
            "-common_args",                 # ✅ APRÈS -@ : appliqué à chaque bloc
            "-overwrite_original",
            "-charset", "iptc=UTF8",        # ✅ Pour écriture IPTC  
            "-charset", "exif=UTF8",        # ✅ Pour écriture EXIF
            "-codedcharacterset=utf8",      # ✅ Définit l'encoding UTF-8 pour IPTC (syntaxe correcte)
            "-q", "-q",
            "-api", "NoDups=1",            # ✅ GARDER pour déduplication intra-lot (complémentaire avec -=/+=)
            "-efile1", "error_files.txt",     # ✅ errors = 1
            "-efile2", "unchanged_files.txt", # ✅ unchanged = 2  
            "-efile4", "failed_condition_files.txt", # ✅ failed -if condition = 4
            "-efile8", "updated_files.txt"    # ✅ updated = 8
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
            statistics.stats.add_processed_file(media_path, is_image)

        if clean_sidecars:
            cleaned_count = 0
            for _, json_path, _ in batch:
                try:
                    json_path.unlink()
                    cleaned_count += 1
                except OSError as e:
                    logger.warning(f"Échec de la suppression du fichier de métadonnées {json_path.name}: {e}")
            statistics.stats.sidecars_cleaned += cleaned_count
        
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
                statistics.stats.add_processed_file(media_path, is_image)
            
            # Nettoyer les sidecars si demandé (comme dans le cas de succès normal)
            if clean_sidecars:
                cleaned_count = 0
                for _, json_path, _ in batch:
                    try:
                        json_path.unlink()
                        cleaned_count += 1
                    except OSError as e:
                        logger.warning(f"Échec de la suppression du fichier de métadonnées {json_path.name}: {e}")
                statistics.stats.sidecars_cleaned += cleaned_count
            
            return len(batch)
        elif "doesn't exist or isn't writable" in stderr_msg:
            logger.warning(f"⚠️ Certains champs de métadonnées non supportés par les fichiers du lot. "
                          f"Normal pour vidéos ou certains formats. Détails: {stderr_msg.strip()}")
            # Considérer comme un succès partiel
            for media_path, _, _ in batch:
                is_image = media_path.suffix.lower() in IMAGE_EXTS  
                statistics.stats.add_processed_file(media_path, is_image)
            
            # Nettoyer les sidecars si demandé (comme dans le cas de succès normal)
            if clean_sidecars:
                cleaned_count = 0
                for _, json_path, _ in batch:
                    try:
                        json_path.unlink()
                        cleaned_count += 1
                    except OSError as e:
                        logger.warning(f"Échec de la suppression du fichier de métadonnées {json_path.name}: {e}")
                statistics.stats.sidecars_cleaned += cleaned_count
            
            return len(batch)
        elif "character(s) could not be encoded" in stderr_msg:
            error_type = "encoding_error"
            error_msg = "Problème d'encodage de caractères (émojis, accents)"
            logger.warning(f"⚠️ {error_msg}. Détails: {stderr_msg.strip()}")
        else:
            error_type = "exiftool_error"
            error_msg = f"Erreur exiftool (code {exc.returncode}): {stderr_msg.strip() or 'Erreur inconnue'}"
            logger.exception(f"❌ Échec du traitement par lot de {len(batch)} fichier(s). {error_msg}")
        
        # Marquer tous les fichiers du lot comme échoués
        for media_path, _, _ in batch:
            statistics.stats.add_failed_file(media_path, error_type, error_msg)
        
        # Nettoyer les sidecars même en cas d'échec si demandé
        if clean_sidecars:
            cleaned_count = 0
            for _, json_path, _ in batch:
                try:
                    json_path.unlink()
                    cleaned_count += 1
                except OSError as e:
                    logger.warning(f"Échec de la suppression du fichier de métadonnées {json_path.name}: {e}")
            statistics.stats.sidecars_cleaned += cleaned_count
            # Retourner le nombre de fichiers traités même si échec (pour le nettoyage des sidecars)
            return len(batch)
        
        return 0
    finally:
        if argfile_path and Path(argfile_path).exists():
            Path(argfile_path).unlink()


def process_directory_batch(root: Path, use_localtime: bool = False, append_only: bool = True, clean_sidecars: bool = False) -> None:
    """Traiter récursivement tous les fichiers sidecar sous ``root`` par lots."""
    batch: List[Tuple[Path, Path, List[str]]] = []
    BATCH_SIZE = 100
    
    # Initialiser les statistiques
    statistics.stats.start_processing()
    
    sidecar_files = [path for path in root.rglob("*.json") if _is_sidecar_file(path)]
    statistics.stats.total_sidecars_found = len(sidecar_files)
    
    if statistics.stats.total_sidecars_found == 0:
        logger.warning("Aucun fichier de métadonnées (.json) trouvé dans %s", root)
        statistics.stats.end_processing()
        return

    logger.info("🔍 Traitement par lots de %d fichier(s) de métadonnées dans %s", statistics.stats.total_sidecars_found, root)

    for json_path in sidecar_files:
        try:
            meta = parse_sidecar(json_path)
            
            directory_albums = find_albums_for_directory(json_path.parent)
            meta.albums.extend(directory_albums)
            
            media_path = json_path.with_name(meta.filename)
            if not media_path.exists():
                error_msg = f"Fichier image introuvable : {meta.filename}"
                statistics.stats.add_failed_file(json_path, "file_not_found", error_msg)
                logger.warning(f"❌ {error_msg}")
                continue

            fixed_media_path, fixed_json_path = fix_file_extension_mismatch(media_path, json_path)
            if fixed_json_path != json_path:
                meta = parse_sidecar(fixed_json_path)
                meta.albums.extend(find_albums_for_directory(fixed_json_path.parent))
            
            args = build_exiftool_args(
                meta, media_path=fixed_media_path, use_localtime=use_localtime, append_only=append_only
            )

            if args:
                batch.append((fixed_media_path, fixed_json_path, args))
            else:
                # Aucun tag à écrire pour ce sidecar
                statistics.stats.total_skipped += 1
                statistics.stats.skipped_files.append(json_path.name)

            if len(batch) >= BATCH_SIZE:
                process_batch(batch, clean_sidecars)
                batch = []

        except (ValueError, RuntimeError) as exc:
            error_msg = f"Erreur de préparation : {exc}"
            statistics.stats.add_failed_file(json_path, "preparation_error", error_msg)
            logger.warning("❌ Échec de la préparation de %s : %s", json_path.name, exc)

    if batch:
        process_batch(batch, clean_sidecars)

    statistics.stats.end_processing()
    
    # Affichage du résumé
    statistics.stats.print_console_summary()
    
    # Créer un dossier logs s'il n'existe pas
    logs_dir = root / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Sauvegarde du rapport détaillé avec un nom incluant la date
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = logs_dir / f"traitement_log_{timestamp}.json"
    statistics.stats.save_detailed_report(log_file)

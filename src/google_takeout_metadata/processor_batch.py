import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple

from .exif_writer import build_exiftool_args
from .sidecar import find_albums_for_directory, parse_sidecar
from .processor import IMAGE_EXTS, VIDEO_EXTS, ALL_MEDIA_EXTS, detect_file_type, fix_file_extension_mismatch, _is_sidecar_file 


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

        logger.info(f"Traitement d'un batch de {len(batch)} fichier(s) avec exiftool...")

        cmd = [
            "exiftool",
            "-overwrite_original",
            "-charset", "filename=UTF8",
            "-charset", "iptc=UTF8",
            "-charset", "exif=UTF8",
            "-@", argfile_path,
        ]
        
        timeout_seconds = 60 + (len(batch) * 5)
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=timeout_seconds, encoding='utf-8'
        )
        
        # Journaliser le succès avec des détails si pertinents
        if result.stdout and result.stdout.strip() and isinstance(result.stdout, str):
            # Compter les fichiers mis à jour dans la sortie exiftool
            stdout_lines = result.stdout.strip().split('\n')
            update_lines = [line for line in stdout_lines if 'files updated' in line.lower() or 'image files updated' in line.lower()]
            if update_lines:
                logger.info(f"Batch de {len(batch)} fichiers traité avec succès. {', '.join(update_lines)}")
            else:
                logger.info(f"Batch de {len(batch)} fichiers traité avec succès.")
        else:
            logger.info(f"Batch de {len(batch)} fichiers traité avec succès.")

        if clean_sidecars:
            for _, json_path, _ in batch:
                try:
                    json_path.unlink()
                except OSError as e:
                    logger.warning(f"Échec de la suppression du fichier de métadonnées {json_path.name}: {e}")
        
        return len(batch)

    except FileNotFoundError as exc:
        raise RuntimeError("exiftool introuvable") from exc
    except subprocess.CalledProcessError as exc:
        stderr_msg = exc.stderr or ""
        stdout_msg = exc.stdout or ""
        
        # Analyser le type d'erreur pour donner un message plus clair
        if "files failed condition" in stderr_msg or "files failed condition" in stdout_msg:
            logger.warning(f"Traitement par lot terminé avec des conditions non remplies (normal en mode append-only). "
                          f"{len(batch)} fichiers traités. Certaines métadonnées existaient déjà.")
        elif "doesn't exist or isn't writable" in stderr_msg:
            logger.warning(f"Certains champs de métadonnées ne sont pas supportés par certains fichiers du batch. "
                          f"Ceci est normal pour les vidéos ou certains formats. Détails: {stderr_msg.strip()}")
        elif "character(s) could not be encoded" in stderr_msg:
            logger.warning(f"Problème d'encodage de caractères dans les noms de fichiers. "
                          f"Certains caractères spéciaux (émojis, accents) peuvent causer ce problème. "
                          f"Fichiers concernés visibles dans: {stderr_msg.strip()}")
        else:
            logger.error(f"Échec du traitement par lot pour {len(batch)} fichiers. "
                        f"Code d'erreur: {exc.returncode}. "
                        f"Erreur: {stderr_msg.strip() if stderr_msg.strip() else 'Aucune erreur détaillée'}. "
                        f"Sortie: {stdout_msg.strip() if stdout_msg.strip() else 'Aucune sortie détaillée'}")
        return 0
    finally:
        if argfile_path and Path(argfile_path).exists():
            Path(argfile_path).unlink()


def process_directory_batch(root: Path, use_localtime: bool = False, append_only: bool = True, clean_sidecars: bool = False) -> None:
    """Traiter récursivement tous les fichiers sidecar sous ``root`` par lots."""
    batch: List[Tuple[Path, Path, List[str]]] = []
    BATCH_SIZE = 100
    total_processed = 0
    
    sidecar_files = [path for path in root.rglob("*.json") if _is_sidecar_file(path)]
    total_sidecars = len(sidecar_files)
    
    if total_sidecars == 0:
        logger.warning("Aucun fichier de métadonnées (.json) trouvé dans %s", root)
        return

    for json_path in sidecar_files:
        try:
            meta = parse_sidecar(json_path)
            
            directory_albums = find_albums_for_directory(json_path.parent)
            meta.albums.extend(directory_albums)
            
            media_path = json_path.with_name(meta.filename)
            if not media_path.exists():
                logger.warning(f"Fichier image introuvable pour les métadonnées {json_path.name}, ignoré.")
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

            if len(batch) >= BATCH_SIZE:
                processed_count = process_batch(batch, clean_sidecars)
                total_processed += processed_count
                batch = []

        except (ValueError, RuntimeError) as exc:
            logger.warning("Échec de la préparation de %s pour le traitement par lot : %s", json_path.name, exc)

    if batch:
        processed_count = process_batch(batch, clean_sidecars)
        total_processed += processed_count

    logger.info("%d / %d fichier(s) sidecar traité(s) dans %s", total_processed, total_sidecars, root)
    if clean_sidecars and total_processed > 0:
        logger.info("%d fichier(s) sidecar supprimé(s)", total_processed)

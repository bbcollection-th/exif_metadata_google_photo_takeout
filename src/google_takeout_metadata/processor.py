"""Traitement de haut niveau des répertoires contenant des métadonnées Google Takeout."""

from __future__ import annotations

from pathlib import Path
import logging
import json
import subprocess

from .sidecar import parse_sidecar, find_albums_for_directory
from .exif_writer import write_metadata

logger = logging.getLogger(__name__)

# Séparer les extensions images et vidéos pour une meilleure cohérence
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".avif"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".3gp"}
ALL_MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS


def detect_file_type(file_path: Path) -> str | None:
    """Détecter le type réel du fichier via la commande ``file`` ou les octets magiques.
    
    Retourne:
        L'extension correcte (avec point) ou ``None`` si la détection échoue
    """
    try:
        # Essayer d'abord la commande ``file`` (disponible sur la plupart des systèmes)
        result = subprocess.run(
            ["file", str(file_path)], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        if result.returncode == 0:
            output = result.stdout.lower()
            if "jpeg" in output or "jfif" in output:
                return ".jpg"
            elif "png" in output:
                return ".png"
            elif "gif" in output:
                return ".gif"
            elif "webp" in output:
                return ".webp"
            elif "heic" in output or "heif" in output:
                return ".heic"
            elif "mp4" in output:
                return ".mp4"
            elif "quicktime" in output or "mov" in output:
                return ".mov"
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # Repli : lecture des octets magiques
    try:
        with open(file_path, "rb") as f:
            header = f.read(16)
            if header.startswith(b'\xff\xd8\xff'):
                return ".jpg"
            elif header.startswith(b'\x89PNG\r\n\x1a\n'):
                return ".png"
            elif header.startswith(b'GIF8'):
                return ".gif"
            elif header.startswith(b'RIFF') and b'WEBP' in header:
                return ".webp"
            elif header[4:8] == b'ftyp':
                if b'heic' in header[:16] or b'mif1' in header[:16]:
                    return ".heic"
                elif b'mp4' in header[:16] or b'isom' in header[:16]:
                    return ".mp4"
    except (OSError, IOError):
        pass
    
    return None


def fix_file_extension_mismatch(media_path: Path, json_path: Path) -> tuple[Path, Path]:
    """Corriger une incohérence d'extension en renommant les fichiers et en mettant à jour le JSON.
    
    Args:
        media_path: Chemin du fichier image/vidéo
        json_path: Chemin du fichier JSON associé (sidecar)
        
    Retourne:
        Un tuple ``(new_media_path, new_json_path)``
    """
    # Détecter le type réel du fichier
    actual_ext = detect_file_type(media_path)
    if not actual_ext or actual_ext == media_path.suffix.lower():
        # Aucune incohérence détectée ou la détection a échoué
        return media_path, json_path
    
    # Créer de nouveaux chemins avec la bonne extension
    new_media_path = media_path.with_suffix(actual_ext)
    new_json_path = json_path.with_name(new_media_path.name + ".supplemental-metadata.json")
    
    logger.info("Correction automatique : Extension de fichier incorrecte détectée pour %s (devrait être %s). "
                "Renommage en cours...", media_path.name, actual_ext)
    
    image_renamed = False
    try:
        # Renommer le fichier image
        media_path.rename(new_media_path)
        image_renamed = True
        logger.info("✅ Fichier renommé avec succès : %s → %s", media_path.name, new_media_path.name)
        
        # Mettre à jour le contenu JSON et renommer le fichier JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        # Mettre à jour le champ title
        json_data['title'] = new_media_path.name
        
        # Écrire le JSON mis à jour au nouvel emplacement
        with open(new_json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        # Supprimer l'ancien fichier JSON
        json_path.unlink()
        logger.info("✅ Fichier JSON mis à jour et renommé : %s → %s", json_path.name, new_json_path.name)
        
        return new_media_path, new_json_path
        
    except (OSError, IOError, json.JSONDecodeError) as exc:
        logger.warning("❌ Échec de la correction d'extension pour %s : %s. "
                       "Le fichier sera traité avec son extension actuelle.", media_path.name, exc)
        
        # Si l'image a été renommée mais que des étapes ultérieures échouent, tenter un rollback
        if image_renamed:
            try:
                # Supprimer tout nouveau JSON éventuellement créé
                if new_json_path.exists():
                    new_json_path.unlink()
                    logger.info("🔄 Fichier JSON partiellement créé supprimé : %s", new_json_path.name)
                
                # Renommer l'image avec son nom d'origine
                new_media_path.rename(media_path)
                logger.info("🔄 Annulation réussie du renommage : %s → %s", new_media_path.name, media_path.name)
                return media_path, json_path
            except (OSError, IOError) as rollback_exc:
                logger.error("❌ Échec de l'annulation du renommage %s → %s : %s. "
                           "ATTENTION : Le répertoire est dans un état incohérent - "
                           "le fichier image a le nouveau nom mais le JSON référence l'ancien nom.", 
                           new_media_path.name, media_path.name, rollback_exc)
                # Retourner les nouveaux chemins afin de refléter l'état courant
                return new_media_path, json_path
        
        return media_path, json_path


def _is_sidecar_file(path: Path) -> bool:
    """Vérifier si un fichier peut être un JSON annexe (Google Photos).
    
    Cette fonction est permissive car ``parse_sidecar()`` fait une
    validation stricte en comparant le champ ``title`` avec le nom attendu.
    
    Formats supportés :
    - Nouveau format : photo.jpg.supplemental-metadata.json
    - Ancien format : photo.jpg.json
    """
    if not path.suffix.lower() == ".json":
        return False
    
    suffixes = [s.lower() for s in path.suffixes]
    
    # Nouveau format Google Takeout : photo.jpg.supplemental-metadata.json
    if len(suffixes) >= 3 and suffixes[-2] == ".supplemental-metadata" and suffixes[-3] in ALL_MEDIA_EXTS:
        return True
    
    # Format hérité : photo.jpg.json
    if len(suffixes) >= 2 and suffixes[-2] in ALL_MEDIA_EXTS:
        return True
    
    # Format plus ancien : photo.json (moins spécifique mais validé ultérieurement)
    # Ne considérer ceci que si le nom de base sans .json pourrait être une image
    stem_parts = path.stem.split('.')
    if len(stem_parts) >= 2:
        potential_ext = '.' + stem_parts[-1].lower()
        if potential_ext in ALL_MEDIA_EXTS:
            return True
    
    return False


def process_sidecar_file(json_path: Path, use_localtime: bool = False, append_only: bool = True, clean_sidecars: bool = False) -> None:
    """Traiter un fichier annexe ``.json``.
    
    Args:
        json_path: Chemin du fichier JSON annexe
        use_localtime: Convertir les dates en heure locale au lieu d'UTC
        append_only: Ajouter uniquement les champs manquants
        clean_sidecars: Supprimer le JSON après un traitement réussi
    """

    meta = parse_sidecar(json_path)
    
    # Trouver les albums du répertoire
    directory_albums = find_albums_for_directory(json_path.parent)
    meta.albums.extend(directory_albums)
    
    media_path = json_path.with_name(meta.filename)
    if not media_path.exists():
        raise FileNotFoundError(f"Fichier image introuvable pour le sidecar {json_path}")
    
    # Tenter d'écrire les métadonnées dans l'image
    try:
        write_metadata(media_path, meta, use_localtime=use_localtime, append_only=append_only)
        current_json_path = json_path
    except RuntimeError as exc:
        # Vérifier s'il s'agit d'une erreur d'incohérence d'extension
        error_msg = str(exc).lower()
        if ("not a valid png" in error_msg and "looks more like a jpeg" in error_msg) or \
           ("not a valid jpeg" in error_msg and "looks more like a png" in error_msg) or \
           ("charset option" in error_msg):
            
            logger.info("🔍 Détection possible d'une extension incorrecte pour %s. "
                        "Tentative de correction automatique...", media_path.name)
            
            # Tenter de corriger l'incohérence d'extension
            fixed_media_path, fixed_json_path = fix_file_extension_mismatch(media_path, json_path)
            
            if fixed_media_path != media_path or fixed_json_path != json_path:
                # Les fichiers ont été renommés (au moins partiellement), re-analyser le JSON et réessayer
                # Gérer le cas où l'image a été renommée mais pas le JSON (échec de rollback partiel)
                actual_json_path = fixed_json_path if fixed_json_path.exists() else json_path
                
                meta = parse_sidecar(actual_json_path)
                directory_albums = find_albums_for_directory(actual_json_path.parent)
                meta.albums.extend(directory_albums)
                
                write_metadata(fixed_media_path, meta, use_localtime=use_localtime, append_only=append_only)
                current_json_path = actual_json_path
                logger.info("Traitement réussi de %s après correction d'extension", fixed_media_path)
            else:
                # Échec de la correction d'extension, relancer l'erreur originale
                raise
        else:
            # Ce n'est pas une erreur d'incohérence d'extension, relancer
            raise
    
    # Nettoyer le sidecar si demandé et si l'écriture a réussi
    if clean_sidecars:
        try:
            current_json_path.unlink()
            logger.info("Fichier sidecar supprimé : %s", current_json_path)
        except OSError as exc:
            logger.warning("Échec de la suppression du fichier sidecar %s : %s", current_json_path, exc)


def process_directory(root: Path, use_localtime: bool = False, append_only: bool = True, clean_sidecars: bool = False) -> None:
    """Traiter récursivement tous les fichiers annexes sous ``root``.
    
    Args:
        root: Répertoire racine à parcourir récursivement
        use_localtime: Convertir les dates en heure locale au lieu d'UTC
        append_only: Ajouter uniquement les champs manquants
        clean_sidecars: Supprimer les JSON après un traitement réussi
    """
    count = 0
    cleaned_count = 0
    
    for json_file in root.rglob("*.json"):
        
        if not _is_sidecar_file(json_file):
            continue
        count += 1
        try:
            process_sidecar_file(json_file, use_localtime=use_localtime, append_only=append_only, clean_sidecars=clean_sidecars)
            if clean_sidecars:
                cleaned_count += 1
        except (FileNotFoundError, ValueError, RuntimeError) as exc:  # pragma: no cover - logging
            logger.warning("Échec du traitement de %s : %s", json_file, exc, exc_info=True)
    
    logger.info("%d fichier(s) sidecar traité(s) dans %s", count, root)
    if clean_sidecars and cleaned_count > 0:
        logger.info("%d fichier(s) sidecar supprimé(s)", cleaned_count)
    if count == 0:
        logger.warning("Aucun fichier sidecar trouvé dans %s", root)

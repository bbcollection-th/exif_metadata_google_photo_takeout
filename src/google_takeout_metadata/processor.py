"""Traitement de haut niveau des répertoires contenant des métadonnées Google Takeout."""

from __future__ import annotations

from pathlib import Path
import logging
import json
import subprocess
import shutil
import os
from datetime import datetime

from .sidecar import parse_sidecar, find_albums_for_directory
from .exif_writer import write_metadata
from . import sidecar_safety
from . import statistics
from . import geocoding
from .file_organizer import FileOrganizer, should_organize_file

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
            elif "heic" in output:
                return ".heic"
            elif "heif" in output:
                return ".heif"
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
    
    logger.info("🔧 Extension incorrecte détectée pour %s (devrait être %s). Correction automatique...", 
                media_path.name, actual_ext)
    
    image_renamed = False
    try:
        # Renommer le fichier image
        media_path.rename(new_media_path)
        image_renamed = True
        logger.info("✅ Fichier renommé : %s → %s", media_path.name, new_media_path.name)
        
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
        logger.info("✅ Métadonnées mises à jour : %s → %s", json_path.name, new_json_path.name)
        
        # Enregistrer la correction dans les statistiques
        statistics.stats.add_fixed_extension(media_path.name, new_media_path.name)
        
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
                logger.info("🔄 Annulation du renommage : %s → %s", new_media_path.name, media_path.name)
                return media_path, json_path
            except (OSError, IOError) as rollback_exc:
                logger.exception("❌ Échec de l'annulation du renommage %s → %s : %s. "
                           "ATTENTION : État incohérent - fichier image renommé mais JSON non mis à jour.", 
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


def _organize_file_if_needed(media_path: Path, json_path: Path, meta, organize_files: bool) -> tuple[Path, Path]:
    """Helper pour organiser un fichier selon son statut si l'organisation est activée.
    
    Args:
        media_path: Chemin actuel du fichier média
        json_path: Chemin actuel du fichier sidecar
        meta: Métadonnées du fichier
        organize_files: Si l'organisation des fichiers est activée
        
    Returns:
        Tuple (nouveau_media_path, nouveau_json_path) ou (media_path, json_path) si pas d'organisation
    """
    if not organize_files or not should_organize_file(meta):
        return media_path, json_path
    
    try:
        organizer = FileOrganizer(media_path.parent)
        new_media_path, new_sidecar_path = organizer.move_file_with_sidecar(
            media_path, json_path, meta
        )
        
        # Mettre à jour les chemins si déplacement effectué
        if new_media_path and new_sidecar_path:
            logger.info(f"📁 Fichier organisé selon statut: {meta.filename}")
            return new_media_path, new_sidecar_path
        else:
            return media_path, json_path
            
    except (OSError, shutil.Error) as exc:
        logger.warning(f"Échec de l'organisation du fichier {media_path.name}: {exc}")
        # Continuer le traitement même si l'organisation échoue
        return media_path, json_path


def _enrich_with_reverse_geocode(meta, json_path: Path, geocode: bool) -> None:
    """Compléter les champs de localisation en utilisant le géocodage inverse."""

    if (not geocode) or (meta.latitude is None) or (meta.longitude is None):
        return

    if not os.getenv("GOOGLE_MAPS_API_KEY"):
        logger.debug(
            "Clé API Google Maps absente, géocodage ignoré pour %s", json_path.name
        )
        return

    try:
        results = geocoding.reverse_geocode(meta.latitude, meta.longitude)
    except RuntimeError as exc:
        logger.warning("Échec du géocodage inverse pour %s: %s", json_path.name, exc)
        return

    if not results:
        return

    first = results[0]
    components = first.get("address_components", [])
    city = state = country = None
    for comp in components:
        types = comp.get("types", [])
        if "locality" in types and city is None:
            city = comp.get("long_name")
        elif "administrative_area_level_1" in types and state is None:
            state = comp.get("long_name")
        elif "country" in types and country is None:
            country = comp.get("long_name")

    # Mutations après succès uniquement, en conservant l'existant si partiel
    meta.city = city or meta.city
    meta.state = state or meta.state
    meta.country = country or meta.country
    meta.place_name = first.get("formatted_address") or meta.place_name


def process_sidecar_file(json_path: Path, use_localtime: bool = False, append_only: bool = True, immediate_delete: bool = False, organize_files: bool = False, geocode: bool = False) -> None:
    """Traiter un fichier annexe ``.json``.
    
    Args:
        json_path: Chemin du fichier JSON annexe
        use_localtime: Convertir les dates en heure locale au lieu d'UTC
        append_only: Ajouter uniquement les champs manquants
        immediate_delete: Mode destructeur - supprimer immédiatement le JSON après succès 
                         (par défaut: mode sécurisé avec préfixe OK_)
        organize_files: Organiser les fichiers selon leur statut (archivé/supprimé)
        geocode: Activer le géocodage inverse (False par défaut; nécessite GOOGLE_MAPS_API_KEY)
    """
    
    # Vérifier si ce sidecar a déjà été traité (préfixe OK_)
    if sidecar_safety.is_sidecar_processed(json_path):
        logger.debug("Sidecar déjà traité, ignoré: %s", json_path)
        statistics.stats.add_skipped_file(json_path, "Déjà traité (préfixe OK_)")
        return

    try:
        meta = parse_sidecar(json_path)
    except ValueError as exc:
        statistics.stats.add_failed_file(json_path, "parse_error", f"Erreur de lecture JSON : {exc}")
        raise

    _enrich_with_reverse_geocode(meta, json_path, geocode)

    # Trouver les albums du répertoire
    directory_albums = find_albums_for_directory(json_path.parent)
    meta.albums.extend(directory_albums)
    
    media_path = json_path.with_name(meta.filename)
    if not media_path.exists():
        error_msg = f"Fichier image introuvable : {meta.filename}"
        statistics.stats.add_failed_file(json_path, "file_not_found", error_msg)
        raise FileNotFoundError(error_msg)
    
    # Détecter le type de fichier (image ou vidéo)
    is_image = media_path.suffix.lower() in IMAGE_EXTS
    
    # Tenter d'écrire les métadonnées dans l'image
    try:
        write_metadata(media_path, meta, use_localtime=use_localtime, append_only=append_only)
        current_json_path = json_path
        
        # Enregistrer le succès
        statistics.stats.add_processed_file(is_image)
        
        # Organisation des fichiers selon leur statut (si activée)
        media_path, current_json_path = _organize_file_if_needed(media_path, current_json_path, meta, organize_files)
        
    except RuntimeError as exc:
        # Vérifier s'il s'agit d'une erreur d'incohérence d'extension
        error_msg = str(exc).lower()
        if ("not a valid png" in error_msg and "looks more like a jpeg" in error_msg) or \
           ("not a valid jpeg" in error_msg and "looks more like a png" in error_msg) or \
           ("charset option" in error_msg):
            
            logger.info("🔍 Extension possiblement incorrecte pour %s. Tentative de correction...", media_path.name)
            
            # Tenter de corriger l'incohérence d'extension
            fixed_media_path, fixed_json_path = fix_file_extension_mismatch(media_path, json_path)
            

            if fixed_media_path != media_path or fixed_json_path != json_path:
                # Les fichiers ont été renommés (au moins partiellement), re-analyser le JSON et réessayer
                # Gérer le cas où l'image a été renommée mais pas le JSON (échec de rollback partiel)
                is_image_after_fix = fixed_media_path.suffix.lower() in IMAGE_EXTS
                actual_json_path = fixed_json_path if fixed_json_path.exists() else json_path

                meta = parse_sidecar(actual_json_path)
                _enrich_with_reverse_geocode(meta, actual_json_path, geocode)
                directory_albums = find_albums_for_directory(actual_json_path.parent)
                meta.albums.extend(directory_albums)
                
                write_metadata(fixed_media_path, meta, use_localtime=use_localtime, append_only=append_only)
                current_json_path = actual_json_path
                
                # Enregistrer le succès après correction
                statistics.stats.add_processed_file(is_image_after_fix)
                logger.info("✅ Traitement réussi de %s après correction d'extension", fixed_media_path.name)
                
                # Organisation des fichiers selon leur statut (si activée) - après correction d'extension
                fixed_media_path, current_json_path = _organize_file_if_needed(fixed_media_path, current_json_path, meta, organize_files)
            else:
                # Échec de la correction d'extension, relancer l'erreur originale
                statistics.stats.add_failed_file(media_path, "extension_mismatch", str(exc))
                raise
        else:
            # Ce n'est pas une erreur d'incohérence d'extension, relancer
            statistics.stats.add_failed_file(media_path, "metadata_write_error", str(exc))
            raise
    
    # Gestion du sidecar après succès
    if immediate_delete:
        # Mode destructeur : suppression immédiate (ancien comportement)
        try:
            current_json_path.unlink()
            statistics.stats.sidecars_cleaned += 1
            logger.info("🗑️ Fichier de métadonnées supprimé : %s", current_json_path.name)
        except OSError as exc:
            logger.warning("Échec de la suppression du fichier de métadonnées %s : %s", current_json_path, exc)
    else:
        # Mode sécurisé : marquage avec préfixe OK_ (nouveau comportement par défaut)
        try:
            if sidecar_safety.mark_sidecar_as_processed(current_json_path):
                statistics.stats.sidecars_cleaned += 1  # Compteur réutilisé pour les "traités"
                logger.info("✅ Sidecar marqué comme traité : %s", current_json_path.name)
        except OSError as exc:
            logger.warning("Échec du marquage du sidecar %s : %s", current_json_path, exc)


def process_directory(root: Path, use_localtime: bool = False, append_only: bool = True, immediate_delete: bool = False, organize_files: bool = False, geocode: bool = False) -> None:
    """Traiter récursivement tous les fichiers annexes sous ``root``.
    
    Args:
        root: Répertoire racine à parcourir récursivement
        use_localtime: Convertir les dates en heure locale au lieu d'UTC
        append_only: Ajouter uniquement les champs manquants
        immediate_delete: Mode destructeur - supprimer immédiatement les JSON après succès
                         (par défaut: mode sécurisé avec préfixe OK_)
        organize_files: Organiser les fichiers selon leur statut (archivé/supprimé)
        geocode: Activer le géocodage inverse si l'API est disponible
    """
    
    # Initialiser les statistiques
    statistics.stats.start_processing()
    
    # Exclure les sidecars déjà traités (préfixe OK_)
    all_json_files = [path for path in root.rglob("*.json") if _is_sidecar_file(path)]
    sidecar_files = [path for path in all_json_files if not sidecar_safety.is_sidecar_processed(path)]
    
    # Afficher les statistiques de filtrage et les comptabiliser
    processed_count = len(all_json_files) - len(sidecar_files)
    if processed_count > 0:
        logger.info("📋 %d sidecars déjà traités ignorés (préfixe OK_)", processed_count)
        # Ajouter les fichiers déjà traités aux statistiques
        for path in all_json_files:
            if sidecar_safety.is_sidecar_processed(path):
                statistics.stats.add_skipped_file(path, "Déjà traité (préfixe OK_)")
    
    statistics.stats.total_sidecars_found = len(sidecar_files)
    
    if statistics.stats.total_sidecars_found == 0:
        logger.warning("Aucun fichier de métadonnées (.json) trouvé dans %s", root)
        statistics.stats.end_processing()
        return

    logger.info("🔍 Traitement de %d fichier(s) de métadonnées dans %s", statistics.stats.total_sidecars_found, root)
    
    for json_file in sidecar_files:
            
        try:
            process_sidecar_file(json_file, use_localtime=use_localtime, append_only=append_only, immediate_delete=immediate_delete, organize_files=organize_files, geocode=geocode)
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            logger.warning("❌ Échec du traitement de %s : %s", json_file.name, exc)
            # Les statistiques sont déjà mises à jour dans process_sidecar_file
    
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

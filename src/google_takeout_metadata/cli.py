"""Interface en ligne de commande."""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

from .processor import process_directory
from .processor_batch import process_directory_batch
from .statistics import ProcessingStats
import google_takeout_metadata.statistics as stats_module

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Fusionner les métadonnées Google Takeout dans les images")
    parser.add_argument("path", type=Path, help="Répertoire à analyser récursivement")
    parser.add_argument(
        "--localtime", action="store_true",
        help="Convertir les horodatages en heure locale au lieu de l'UTC (par défaut : UTC)"
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Autoriser l'écrasement des champs de métadonnées existants (par défaut, les métadonnées existantes sont préservées)"
    )
    parser.add_argument(
        "--immediate-delete", action="store_true",
        help="Mode destructeur: supprimer immédiatement les sidecars JSON après succès (par défaut: mode sécurisé avec préfixe OK_)"
    )
    parser.add_argument(
        "--organize-files", action="store_true",
        help="Organiser les fichiers selon leur statut: déplacer les fichiers archivés vers '_Archive' et supprimés vers '_Corbeille'"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Activer les logs détaillés (niveau DEBUG)"
    )
    parser.add_argument(
        "--batch", action="store_true",
        help="Traiter les fichiers par lots"
    )
    args = parser.parse_args(argv)

    # Configuration du logging avec le niveau approprié
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level, 
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    # Gestion de la compatibilité du système de sécurité
    immediate_delete = args.immediate_delete
    
    if immediate_delete:
        logging.info("🔥 Mode destructeur activé : les sidecars seront supprimés immédiatement après succès")
    else:
        logging.info("🔐 Mode sécurisé activé : les sidecars seront marqués avec le préfixe 'OK_' (défaut)")
    
    if not args.path.is_dir():
        logging.error("Le chemin indiqué n'est pas un répertoire : %s", args.path)
        sys.exit(1)
    
    # Réinitialiser les statistiques pour cette exécution (nouvelle instance)
    stats_module.stats = ProcessingStats()
    
    # Le mode par défaut est maintenant append_only=True (sécurité par défaut)
    # L'option --overwrite permet d'écraser les métadonnées existantes
    append_only = not args.overwrite

    # Vérifier que exiftool est disponible uniquement si on va traiter
    if shutil.which("exiftool") is None:
        logging.error("exiftool introuvable. Veuillez l'installer pour utiliser ce script.")
        sys.exit(1)

    if args.batch:
        process_directory_batch(args.path, use_localtime=args.localtime, append_only=append_only, immediate_delete=immediate_delete, organize_files=args.organize_files)
    else:
        process_directory(args.path, use_localtime=args.localtime, append_only=append_only, immediate_delete=immediate_delete, organize_files=args.organize_files)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()

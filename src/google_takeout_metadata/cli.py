"""Interface en ligne de commande."""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

from .processor import process_directory
from .processor_batch import process_directory_batch

def main(argv: list[str] | None = None) -> None:
    # Vérifier que exiftool est disponible
    if shutil.which("exiftool") is None:
        logging.error("exiftool introuvable. Veuillez l'installer pour utiliser ce script.")
        sys.exit(1)

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
        "--append-only", action="store_true",
        help=argparse.SUPPRESS  # Cache l'option dépréciée de l'aide
    )
    parser.add_argument(
        "--clean-sidecars", action="store_true",
        help="Supprimer les fichiers JSON annexes après un transfert de métadonnées réussi"
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
    
    # Gestion de la rétrocompatibilité et validation des options
    if args.append_only and args.overwrite:
        logging.error("Impossible d'utiliser simultanément --append-only (obsolète) et --overwrite")
        sys.exit(1)
    
    if args.append_only:
        logging.warning("--append-only est obsolète et correspond désormais au comportement par défaut. Utilisez --overwrite pour autoriser l'écrasement des métadonnées existantes.")
    
    if not args.path.is_dir():
        logging.error("Le chemin indiqué n'est pas un répertoire : %s", args.path)
        sys.exit(1)
    # Le mode par défaut est maintenant append_only=True (sécurité par défaut)
    # L'option --overwrite permet d'écraser les métadonnées existantes
    append_only = not args.overwrite

    if args.batch:
        process_directory_batch(args.path, use_localtime=args.localtime, append_only=append_only, clean_sidecars=args.clean_sidecars)
    else:
        process_directory(args.path, use_localtime=args.localtime, append_only=append_only, clean_sidecars=args.clean_sidecars)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()

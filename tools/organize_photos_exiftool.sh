#!/bin/bash
# Script ExifTool pur pour organiser les photos par date
# Usage: ./organize_photos_exiftool.sh "/chemin/vers/photos" [dossier_destination]

set -e

# Configuration
SOURCE_DIR="$1"
TARGET_DIR="${2:-$SOURCE_DIR}"
DRY_RUN="${DRY_RUN:-false}"

# Vérifications
if [ -z "$SOURCE_DIR" ]; then
    echo "Usage: $0 \"/chemin/vers/photos\" [dossier_destination]"
    echo ""
    echo "Variables d'environnement:"
    echo "  DRY_RUN=true    # Mode simulation"
    echo ""
    echo "Exemples:"
    echo "  $0 \"/home/user/Photos\""
    echo "  $0 \"/home/user/Photos\" \"/home/user/Photos_Organisees\""
    echo "  DRY_RUN=true $0 \"/home/user/Photos\""
    exit 1
fi

if [ ! -d "$SOURCE_DIR" ]; then
    echo "ERREUR: Dossier source '$SOURCE_DIR' non trouvé"
    exit 1
fi

# Vérifier ExifTool
if ! command -v exiftool &> /dev/null; then
    echo "ERREUR: ExifTool non trouvé"
    echo "Installation:"
    echo "  Windows: scoop install exiftool"
    echo "  macOS: brew install exiftool"
    echo "  Linux: sudo apt install libimage-exiftool-perl"
    exit 1
fi

echo "=========================================="
echo " ORGANISATEUR DE PHOTOS PAR DATE"
echo "=========================================="
echo "Source: $SOURCE_DIR"
echo "Destination: $TARGET_DIR"
if [ "$DRY_RUN" = "true" ]; then
    echo "Mode: SIMULATION (aucun fichier ne sera déplacé)"
else
    echo "Mode: RÉEL (les fichiers seront déplacés)"
fi
echo "=========================================="
echo ""

# Créer le dossier de destination
if [ "$DRY_RUN" != "true" ]; then
    mkdir -p "$TARGET_DIR"
fi

# Fonction pour obtenir la date d'un fichier
get_file_date() {
    local file="$1"
    
    # Essayer différents tags de date par ordre de priorité
    local date_tags=(
        "DateTimeOriginal"
        "CreateDate"
        "CreationDate"
        "DateCreated"
        "FileModifyDate"
    )
    
    for tag in "${date_tags[@]}"; do
        date_str=$(exiftool -s -s -s -d "%Y-%m" -"$tag" "$file" 2>/dev/null)
        if [ ! -z "$date_str" ] && [ "$date_str" != "-" ] && [ "$date_str" != "0000-00" ]; then
            echo "$date_str"
            return 0
        fi
    done
    
    # Aucune date trouvée
    echo "unknown_date"
}

# Fonction pour déplacer un fichier
move_file() {
    local file="$1"
    local date_folder="$2"
    local filename=$(basename "$file")
    local target_dir="$TARGET_DIR/$date_folder"
    local target_file="$target_dir/$filename"
    
    # Créer le dossier de destination
    if [ "$DRY_RUN" != "true" ]; then
        mkdir -p "$target_dir"
    fi
    
    # Gérer les conflits de noms
    local counter=1
    local base_name="${filename%.*}"
    local extension="${filename##*.}"
    
    while [ -f "$target_file" ]; do
        if [ "$base_name" = "$filename" ]; then
            # Pas d'extension
            target_file="$target_dir/${base_name}_$(printf "%03d" $counter)"
        else
            target_file="$target_dir/${base_name}_$(printf "%03d" $counter).$extension"
        fi
        ((counter++))
    done
    
    # Déplacer le fichier
    if [ "$DRY_RUN" = "true" ]; then
        echo "[DRY-RUN] Déplacerait: $file -> $target_file"
    else
        mv "$file" "$target_file"
        echo "Déplacé: $(basename "$file") -> $date_folder/"
    fi
}

# Variables de statistiques
declare -A stats
total_files=0
processed_files=0

# Traiter tous les fichiers d'images/vidéos
echo "Recherche et traitement des fichiers..."
echo ""

while IFS= read -r -d '' file; do
    ((total_files++))
    
    # Obtenir la date du fichier
    date_folder=$(get_file_date "$file")
    
    # Incrémenter les statistiques
    if [ -z "${stats[$date_folder]}" ]; then
        stats[$date_folder]=0
    fi
    ((stats[$date_folder]++))
    
    # Déplacer le fichier
    move_file "$file" "$date_folder"
    ((processed_files++))
    
    # Afficher la progression
    if [ $((processed_files % 10)) -eq 0 ]; then
        echo "Traité: $processed_files/$total_files fichiers"
    fi
    
done < <(find "$SOURCE_DIR" -type f \( \
    -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.jpe" -o \
    -iname "*.png" -o -iname "*.gif" -o -iname "*.bmp" -o \
    -iname "*.tiff" -o -iname "*.tif" -o -iname "*.heic" -o \
    -iname "*.heif" -o -iname "*.webp" -o -iname "*.raw" -o \
    -iname "*.cr2" -o -iname "*.nef" -o -iname "*.arw" -o \
    -iname "*.dng" -o -iname "*.mp4" -o -iname "*.mov" -o \
    -iname "*.avi" -o -iname "*.mkv" -o -iname "*.wmv" -o \
    -iname "*.m4v" \
\) -print0)

# Afficher les statistiques finales
echo ""
echo "=================================================="
echo "                STATISTIQUES FINALES"
echo "=================================================="

for date_folder in $(printf '%s\n' "${!stats[@]}" | sort); do
    printf "%-20s : %4d fichiers\n" "$date_folder" "${stats[$date_folder]}"
done

echo ""
echo "Total traité: $processed_files/$total_files fichiers"

if [ "$DRY_RUN" = "true" ]; then
    echo ""
    echo "⚠️  MODE DRY-RUN: Aucun fichier n'a été réellement déplacé"
    echo "   Pour exécuter réellement: DRY_RUN=false $0 \"$SOURCE_DIR\""
fi

echo ""
echo "Terminé!"
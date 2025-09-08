# Assets de Test

Ce dossier contient des fichiers de référence pour les tests d'intégration.

## Fichiers disponibles

### Images
- **test_clean.jpg** : Image JPEG 100x100 sans métadonnées (nettoye avec `exiftool -all=`)
- **test_with_metadata.jpg** : Image JPEG 100x100 avec métadonnées de base
  - Description : "Existing description"
  - Rating : 3
  - Keywords : "Existing keyword"

### Vidéos
- **test_video_clean.mp4** : Vidéo MP4 sans métadonnées (nettoyée avec `exiftool -all=`)
- **test_video_with_metadata.mp4** : Vidéo MP4 avec métadonnées de base
  - Description : "Existing video description"
  - DateTimeOriginal : "2020:01:01 12:00:00"
  - Keywords : "Existing video keyword"

## Utilisation dans les tests

Les tests d'intégration utilisent la fonction `_copy_test_asset(asset_name, dest_path)` pour copier ces fichiers vers des répertoires temporaires avant chaque test. Cela garantit :

1. **Reproductibilité** : Chaque test commence avec les mêmes conditions
2. **Isolation** : Les tests ne s'interfèrent pas entre eux
3. **Contrôle** : Les métadonnées existantes sont connues et prévisibles

## Régénération des assets

Si nécessaire, les assets peuvent être régénérés avec :

```bash
# Se placer dans le dossier test_assets
cd test_assets

# Créer les images
python -c "
from PIL import Image
img = Image.new('RGB', (100, 100), color='red')
img.save('test_clean.jpg')
img2 = Image.new('RGB', (100, 100), color='blue') 
img2.save('test_with_metadata.jpg')
"

# Copier la vidéo de référence
cp "../Google Photos/essais/1686356837983.mp4" "test_video_clean.mp4"
cp "test_video_clean.mp4" "test_video_with_metadata.mp4"

# Nettoyer les fichiers clean
exiftool -overwrite_original -all= test_clean.jpg test_video_clean.mp4

# Ajouter des métadonnées aux fichiers with_metadata
exiftool -overwrite_original -EXIF:ImageDescription="Existing description" -XMP:Rating=3 -IPTC:Keywords="Existing keyword" test_with_metadata.jpg
exiftool -overwrite_original -api QuickTimeUTC=1 -XMP-dc:Description="Existing video description" -DateTimeOriginal="2020:01:01 12:00:00" -IPTC:Keywords="Existing video keyword" test_video_with_metadata.mp4
```

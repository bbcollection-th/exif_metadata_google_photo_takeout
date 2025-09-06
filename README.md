# exif_metadata_google_photo_takeout

Ce projet permet d'incorporer les métadonnées des fichiers JSON produits par Google Takeout dans les photos correspondantes.

## Fonctionnalités

✅ **Métadonnées supportées:**
- Descriptions/légendes
- Personnes identifiées (avec déduplication automatique)
- Dates de prise de vue et de création
- Coordonnées GPS (filtrage automatique des coordonnées 0/0 peu fiables)
- Favoris (mappés sur Rating=5)
- **Albums** (détectés depuis les fichiers metadata.json de dossier et ajoutés comme mots-clés "Album: <nom>")

✅ **Mode de fonctionnement sûr par défaut:**
- **Append-only par défaut**: Les métadonnées existantes sont préservées
- Les descriptions ne sont écrites que si elles n'existent pas déjà
- Les personnes et albums sont ajoutés aux listes existantes sans suppression
- Utiliser `--overwrite` pour forcer l'écrasement des métadonnées existantes

✅ **Options avancées:**
- `--localtime`: Conversion des timestamps en heure locale au lieu d'UTC
- `--overwrite`: Force l'écrasement des métadonnées existantes (mode destructif)

✅ **Qualité:**
- Tests unitaires complets
- Tests d'intégration E2E avec exiftool
- Support des formats photo et vidéo

## Installation

Prérequis: `exiftool` doit être installé et accessible dans le PATH.

```bash
pip install -e .
```

## Utilisation

### Utilisation basique (mode sûr par défaut)
```bash
# Mode append-only par défaut - préserve les métadonnées existantes
google-takeout-metadata /chemin/vers/le/dossier
```

### Avec options
```bash
# Utiliser l'heure locale pour les timestamps
google-takeout-metadata --localtime /chemin/vers/le/dossier

# Mode destructif: écraser les métadonnées existantes (à utiliser avec précaution)
google-takeout-metadata --overwrite /chemin/vers/le/dossier

# Nettoyer les fichiers sidecars après traitement
google-takeout-metadata --clean-sidecars /chemin/vers/le/dossier

# Combiner les options (mode sûr avec heure locale)
google-takeout-metadata --localtime /chemin/vers/le/dossier
```

Le programme parcourt récursivement le dossier, cherche les fichiers `*.json` et écrit les informations pertinentes dans les fichiers image correspondants à l'aide d'`exiftool`.

## Comportement par défaut (Sécurisé)

**Le mode append-only est désormais activé par défaut** pour éviter la perte accidentelle de métadonnées:

### ✅ Métadonnées préservées:
- **Descriptions existantes** ne sont jamais écrasées
- **Dates existantes** ne sont jamais modifiées
- **Coordonnées GPS existantes** ne sont jamais remplacées
- **Ratings existants** ne sont jamais changés

### ✅ Métadonnées ajoutées:
- **Personnes** sont ajoutées aux listes existantes (pas de suppression)
- **Albums** sont ajoutés aux mots-clés existants (pas de suppression)

### ⚠️ Mode destructif:
Utilisez `--overwrite` seulement si vous voulez explicitement écraser les métadonnées existantes.

## Tests

```bash
# Tests unitaires
pytest tests/ -m "not integration"

# Tests complets (nécessite exiftool)
pytest tests/

# Tests d'intégration uniquement
pytest tests/ -m "integration"
```

Les tests comprennent:
- **Tests unitaires**: Parsing des sidecars, génération des arguments exiftool
- **Tests d'intégration**: Écriture et relecture effective des métadonnées avec exiftool

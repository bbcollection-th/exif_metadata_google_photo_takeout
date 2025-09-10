# exif_metadata_google_photo_takeout

Ce projet permet d'incorporer les métadonnées des fichiers JSON produits par Google Takeout dans les photos correspondantes.

## Fonctionnalités

✅ **Métadonnées supportées:**
- Descriptions/légendes
- Personnes identifiées (avec déduplication automatique)
- Dates de prise de vue et de création
- Coordonnées GPS (filtrage automatique des coordonnées 0/0 peu fiables)
- Favoris (mappés sur le tag Favorite booléen)
- **Albums** (détectés depuis les fichiers metadata.json de dossier et ajoutés comme mots-clés "Album: <nom>")

✅ **Mode de fonctionnement sûr par défaut:**
- **Append-only par défaut**: Les métadonnées existantes sont préservées
- Les descriptions ne sont écrites que si elles n'existent pas déjà
- Les personnes et albums sont ajoutés aux listes existantes sans suppression
- Utiliser `--overwrite` pour forcer l'écrasement des métadonnées existantes

✅ **Options avancées:**
- `--localtime`: Conversion des timestamps en heure locale au lieu d'UTC
- `--overwrite`: Force l'écrasement des métadonnées existantes (mode destructif)
- `--batch`: Mode batch pour traitement optimisé de gros volumes de fichiers

✅ **Qualité:**
- Tests unitaires complets
- Tests d'intégration E2E avec exiftool
- Support des formats photo et vidéo
- **Arguments sécurisés** : Protection contre l'injection shell avec noms contenant des espaces
- **Opérateur `+=` optimisé** : Utilise l'opérateur exiftool `+=` pour accumulation sûre des tags de type liste

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

### Mode batch (optimisé pour gros volumes)
```bash
# Mode batch: traitement optimisé pour de nombreux fichiers
google-takeout-metadata --batch /chemin/vers/le/dossier

# Mode batch avec autres options
google-takeout-metadata --batch --localtime /chemin/vers/le/dossier
google-takeout-metadata --batch --overwrite /chemin/vers/le/dossier

# Exemple concret avec toutes les options (pointer vers le dossier Takeout)
google-takeout-metadata --batch --localtime --clean-sidecars "C:\Users\anthony\Downloads\google photos\Takeout"
```

**Si la commande `google-takeout-metadata` n'est pas trouvée:**
```bash
# Option 1: Utiliser le module Python directement (attention aux underscores)
python -m google_takeout_metadata --batch --localtime --clean-sidecars "/chemin/vers/dossier"

# Option 2: Utiliser l'environnement virtuel complet avec le module
C:/Users/anthony/Documents/PROJETS/exif_metadata_google_photo_takeout/.venv/Scripts/python.exe -m google_takeout_metadata --batch --localtime --clean-sidecars "C:\Users\anthony\Downloads\google photos\Takeout"

# Option 3: Utiliser l'exécutable directement depuis l'environnement virtuel
C:/Users/anthony/Documents/PROJETS/exif_metadata_google_photo_takeout/.venv/Scripts/google-takeout-metadata.exe --batch --localtime --clean-sidecars "C:\Users\anthony\Downloads\google photos\Takeout"

# Option 4: Activer l'environnement virtuel d'abord
.venv/Scripts/activate  # Sur Windows
google-takeout-metadata --batch --localtime --clean-sidecars "/chemin/vers/dossier"
```

**Avantages du mode batch:**
- **Performance améliorée** : Traitement par lots avec exiftool pour réduire le nombre d'appels système
- **Idéal pour gros volumes** : Optimisé pour traiter des milliers de fichiers
- **Moins de fragmentation** : Réduit la charge système en groupant les opérations
- **Même sécurité** : Conserve le comportement append-only par défaut

**Quand utiliser le mode batch:**
- Traitement de bibliothèques photo importantes (>100 fichiers)
- Archives Google Takeout volumineuses
- Situations où la performance est critique

**Note de performance:**
Le mode batch réduit significativement le temps de traitement en groupant les appels à exiftool. 
Pour 1000 fichiers, le gain peut être de 50-80% selon la configuration système.

Le programme parcourt récursivement le dossier, cherche les fichiers `*.json` et écrit les informations pertinentes dans les fichiers image correspondants à l'aide d'`exiftool`.

## Comportement par défaut (Sécurisé)

**Le mode append-only est désormais activé par défaut** pour éviter la perte accidentelle de métadonnées:

### ✅ Métadonnées préservées:
- **Descriptions existantes** ne sont jamais écrasées
- **Dates existantes** ne sont jamais modifiées
- **Coordonnées GPS existantes** ne sont jamais remplacées
- **Ratings existants** ne sont jamais changés

### ✅ Métadonnées ajoutées:
- **Personnes** sont ajoutées aux listes existantes avec déduplication intelligente
- **Albums** sont ajoutés aux mots-clés existants avec déduplication intelligente

### 🔧 Déduplication intelligente:
**Nouvelle fonctionnalité** : Le système évite automatiquement les doublons dans les tags de liste.

- **Normalisation des noms** : "anthony vincent" et "Anthony Vincent" sont reconnus comme identiques
- **Gestion des cas spéciaux** : Support intelligent pour "McDonald", "O'Connor", "van der Berg", etc.
- **Déduplication robuste** : Utilise l'approche "supprimer puis ajouter" (-TAG-=val -TAG+=val) pour garantir zéro doublon final
- **Performance optimisée** : Logs -efile pour reprises intelligentes en cas d'interruption

### ⚠️ Mode destructif:
Utilisez `--overwrite` seulement si vous voulez explicitement écraser les métadonnées existantes.

## Détails techniques

### Opérateur exiftool `+=` pour les listes
Notre implémentation utilise l'opérateur `+=` d'exiftool pour une gestion sûre des tags de type liste :

```bash
# ✅ Correct : L'opérateur += ajoute ET crée le tag si nécessaire
exiftool "-XMP-iptcExt:PersonInImage+=John Doe" photo.jpg

# ❌ Incorrect : L'opérateur += seul ne crée pas un tag inexistant
# (ancien comportement qui échouait)
```

**Avantages de notre approche :**
- **Création automatique** : `+=` crée le tag s'il n'existe pas
- **Accumulation sûre** : Ajoute aux listes existantes sans duplication
- **Sécurité** : Arguments séparés préviennent l'injection shell avec espaces
- **Mode overwrite** : Vide explicitement puis reremplit avec `+=`

### Format Google Takeout supporté
```json
{
  "title": "IMG_20240716_200232.jpg",
  "description": "Description de la photo",
  "photoTakenTime": {"timestamp": "1721152952"},
  "creationTime": {"timestamp": "1721152952"},
  "geoData": {
    "latitude": 48.8566,
    "longitude": 2.3522,
    "altitude": 35.0
  },
  "people": [
    {"name": "John Doe"},
    {"name": "Jane Smith"}
  ],
  "favorited": true,
  "archived": false
}
```

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
- **Tests du mode batch**: Vérification des performances et de la compatibilité du traitement par lots
- **Tests CLI**: Validation de l'interface en ligne de commande et de toutes les options

# 📸 EXIF Metadata Google Photo Takeout

**Outil simple pour appliquer automatiquement les métadonnées JSON de Google Photos à vos fichiers images/vidéos.**

---

## 🎯 Ce que fait cet outil

1. **Lit** vos fichiers JSON de Google Photos Takeout
2. **Découvre** automatiquement tous les champs disponibles  
3. **Mappe** intelligemment vers les tags EXIF/XMP standard
4. **Applique** les métadonnées à vos photos et vidéos

## ⚡ Démarrage Ultra-Rapide

```bash
# 1. Découvrir vos données automatiquement
python tools/discover_fields.py "data/Google Photos/" --output config/exif_mapping.json

# 2. Traiter vos photos
python -m google_takeout_metadata.processor "data/Google Photos/"
```

**C'est tout !** 🎉

## 📁 Structure Simple

```
📁 Votre projet/
├── 📁 config/          ← UNE SEULE configuration
│   └── exif_mapping.json
├── 📁 data/            ← Vos photos Google
│   └── Google Photos/
├── 📁 tools/           ← Outils de découverte
├── 📁 src/             ← Code principal
└── 📁 tests/           ← Tests
```

## 🔧 Outils Disponibles

| Outil | Usage | Description |
|-------|-------|-------------|
| `tools/discover_fields.py` | Analyse automatique | Découvre tous vos champs JSON |
| `tools/validate_config.py` | Validation | Vérifie et nettoie la config |
| `src/google_takeout_metadata/` | Traitement | Applique les métadonnées |

## 📖 Documentation

- **Débutant** : Ce README suffit !
- **Avancé** : [`docs/`](docs/) pour plus de détails
- **Développeur** : [`tests/`](tests/) pour les exemples

---

**Questions ?** Regardez dans [`docs/`](docs/) ou lancez les outils avec `--help`

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
- **Mode sécurisé des sidecars**: Par défaut, les sidecars JSON sont marqués avec le préfixe "OK_" après traitement réussi
- Utiliser `--overwrite` pour forcer l'écrasement des métadonnées existantes
- Utiliser `--immediate-delete` pour supprimer immédiatement les sidecars (mode destructeur)

✅ **Options avancées:**
- `--localtime`: Conversion des timestamps en heure locale au lieu d'UTC
- `--overwrite`: Force l'écrasement des métadonnées existantes (mode destructif)
- `--immediate-delete`: Mode destructeur - supprime immédiatement les sidecars JSON après succès
- `--batch`: Mode batch pour traitement optimisé de gros volumes de fichiers
- `--organize-files`: Organisation automatique des fichiers selon leur statut trashed/inLockedFolder/archived (→ `_Corbeille` / `_Verrouillé` / `_Archive`)
✅ **Qualité:**
- Tests unitaires complets
- Tests d'intégration E2E avec exiftool
- Support des formats photo et vidéo
- **Arguments sécurisés** : Protection contre l'injection shell avec noms contenant des espaces
- **Opérateur `+=` optimisé** : Utilise l'opérateur exiftool `+=` pour accumulation sûre des tags de type liste

## Installation

Prérequis:

- `exiftool` doit être installé et accessible dans le PATH
- Une clé API **Google Maps Geocoding** est nécessaire pour la résolution d'adresses (optionnelle, utilisée avec `--geocode`)

```bash
pip install -e .

# Définir la clé API pour l'application
export GOOGLE_MAPS_API_KEY="votre_clé_api"
```

### Créer une clé API Google Geocoding

1. Se connecter à la [Google Cloud Console](https://console.cloud.google.com/)
2. Créer ou sélectionner un projet existant
3. Activer l'API **Geocoding** depuis la bibliothèque d'API
4. Aller dans **APIs & Services > Identifiants** et créer une clé API
5. (Optionnel) Restreindre la clé pour l'API Geocoding
6. Copier la clé générée puis la définir dans la variable d'environnement `GOOGLE_MAPS_API_KEY`

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

# Mode destructeur: supprimer les sidecars immédiatement après traitement
google-takeout-metadata --immediate-delete /chemin/vers/le/dossier

# Organisation automatique des fichiers selon leur statut
google-takeout-metadata --organize-files /chemin/vers/le/dossier

# Combiner les options (mode sûr avec heure locale)
google-takeout-metadata --localtime /chemin/vers/le/dossier

# Exemple complet avec toutes les options utiles
google-takeout-metadata --batch --localtime --organize-files /chemin/vers/le/dossier
```

### Mode batch (optimisé pour gros volumes)
```bash
# Mode batch: traitement optimisé pour de nombreux fichiers
google-takeout-metadata --batch /chemin/vers/le/dossier

# Mode batch avec autres options
google-takeout-metadata --batch --localtime /chemin/vers/le/dossier
google-takeout-metadata --batch --overwrite /chemin/vers/le/dossier

# Exemple concret avec toutes les options (pointer vers le dossier Takeout)
google-takeout-metadata --batch --localtime --immediate-delete "C:\Users\anthony\Downloads\google photos\Takeout"
```

**Si la commande `google-takeout-metadata` n'est pas trouvée:**
```bash
# Option 1: Utiliser le module Python directement (attention aux underscores)
python -m google_takeout_metadata --batch --localtime --immediate-delete "/chemin/vers/dossier"

# Option 2: Utiliser l'environnement virtuel complet avec le module
C:/Users/anthony/Documents/PROJETS/exif_metadata_google_photo_takeout/.venv/Scripts/python.exe -m google_takeout_metadata --batch --localtime --immediate-delete "C:\Users\anthony\Downloads\google photos\Takeout"

# Option 3: Utiliser l'exécutable directement depuis l'environnement virtuel
C:/Users/anthony/Documents/PROJETS/exif_metadata_google_photo_takeout/.venv/Scripts/google-takeout-metadata.exe --batch --localtime --immediate-delete "C:\Users\anthony\Downloads\google photos\Takeout"

# Option 4: Activer l'environnement virtuel d'abord
.venv/Scripts/activate  # Sur Windows
google-takeout-metadata --batch --localtime --immediate-delete "/chemin/vers/dossier"
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

## Organisation automatique des fichiers

**Nouvelle fonctionnalité** : Organisation automatique des fichiers selon leur statut dans Google Takeout.

```bash
# Activer l'organisation automatique
google-takeout-metadata --organize-files /chemin/vers/le/dossier

# Combiner avec d'autres options
google-takeout-metadata --batch --organize-files --localtime /chemin/vers/le/dossier
```

### 📁 Fonctionnement:

**Statuts détectés** dans les sidecars JSON Google Takeout:
- `"trashed": true` → Fichier déplacé vers `_Corbeille/`
- `"inLockedFolder": true` → Fichier déplacé vers `_Verrouillé/` (dossiers verrouillés)
- `"archived": true` → Fichier déplacé vers `_Archive/`
- **Priorité** : `trashed > inLockedFolder > archived`
  - Si `trashed` et `inLockedFolder`/`archived` coexistent → `trashed` gagne
  - Si `inLockedFolder` et `archived` coexistent → `inLockedFolder` gagne

**Structure créée automatiquement:**
```
dossier_source/
├── _Archive/         # Fichiers avec "archived": true
├── _Corbeille/       # Fichiers avec "trashed": true  
├── _Verrouillé/      # Fichiers avec "inLockedFolder": true
└── autres_fichiers/  # Fichiers sans statut spécial
```

### 🔒 Sécurité:

- **Gestion des conflits** : Si un fichier existe déjà dans le dossier de destination, un suffixe numérique est ajouté
- **Déplacement avec sidecar** : Le fichier JSON correspondant est déplacé avec le fichier média
- **Préservation** : Tous les fichiers sont déplacés, jamais supprimés
- **Logs détaillés** : Information sur chaque déplacement effectué

### ⚙️ Avantages:

- **Nettoyage automatique** : Sépare automatiquement les fichiers selon leur statut Google Photos
- **Préservation de l'historique** : Les fichiers "trashés" restent accessibles dans `_Corbeille/`
- **Respect des dossiers verrouillés** : Les fichiers de dossiers verrouillés sont isolés dans `_Verrouillé/`
- **Workflow Google Takeout** : Respecte parfaitement la hiérarchie de statut de Google Photos
- **Combinable** : Fonctionne avec toutes les autres options (batch, localtime, etc.)

**Exemple concret:**
```bash
# Traitement complet d'un export Google Takeout avec organisation
google-takeout-metadata --batch --localtime --organize-files "C:\Downloads\Takeout\Google Photos"
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
- **Personnes** sont ajoutées aux listes existantes avec déduplication intelligente
- **Albums** sont ajoutés aux mots-clés existants avec déduplication intelligente

### 🔧 Déduplication intelligente:
**Nouvelle fonctionnalité** : Le système évite automatiquement les doublons dans les tags de liste.

- **Normalisation des noms** : "anthony vincent" et "Anthony Vincent" sont reconnus comme identiques
- **Gestion des cas spéciaux** : Support intelligent pour "McDonald", "O'Connor", "van der Berg", etc.
- **Approche robuste** : Utilise la stratégie "supprimer puis ajouter" (-TAG-=val -TAG+=val) pour garantir zéro doublon final
- **Performance optimisée** : Logs -efile pour reprises intelligentes en cas d'interruption
- **Gestion des `-wm cg`** : Logic groupée pour optimiser les arguments ExifTool en mode append-only

### ⚠️ Mode destructif:
Utilisez `--overwrite` seulement si vous voulez explicitement écraser les métadonnées existantes.

### 🔐 Gestion des sidecars JSON:
**Mode sécurisé par défaut** : Les sidecars sont préservés avec un préfixe après traitement réussi.

- **Mode sécurisé** (défaut) : Les sidecars sont renommés avec le préfixe "OK_" après succès
- **Mode destructeur** (`--immediate-delete`) : Les sidecars sont supprimés immédiatement après traitement réussi
- **Sécurité** : En cas d'erreur, les sidecars restent intacts pour permettre de retenter
- **Traçabilité** : Les fichiers "OK_" permettent de voir quels sidecars ont été traités avec succès

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
- **Logic `-wm cg` optimisée** : Arguments groupés pour éviter la fragmentation des paramètres

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
  "favorited": true,
  "archived": false,
  "trashed": false,
  "inLockedFolder": false,
  "localFolderName": "Instagram"
}
```

**Champs supportés pour l'organisation des fichiers:**
- `archived`: Déplace le fichier vers le dossier `archive/` si `true`
- `trashed`: Déplace le fichier vers le dossier `corbeille/` si `true` (priorité sur `archived`)
 

## Géocodage des coordonnées GPS

L'option `--geocode` permet d'enrichir les photos en transformant les coordonnées GPS en informations lisibles.
Elle repose sur l'API **Google Maps Geocoding** via la bibliothèque `requests`.

### Fournir la clé API

1. Obtenir une clé pour l'API **Geocoding** dans la Google Cloud Console.
2. Définir la variable d'environnement `GOOGLE_MAPS_API_KEY` :

```bash
export GOOGLE_MAPS_API_KEY="votre_clé_api"
```

Un cache local (`~/.cache/google_takeout_metadata/geocode_cache.json`) est utilisé et peut être redéfini via `GOOGLE_TAKEOUT_METADATA_CACHE`.

### Activer depuis la CLI

```bash
google-takeout-metadata --geocode /chemin/vers/le/dossier
```

### Tags Exif ajoutés

Lorsque le géocodage est actif, les tags suivants sont ajoutés si absents :

- `XMP:City` / `IPTC:City`
- `XMP:Country` / `IPTC:Country-PrimaryLocationName`
- `XMP:Location` (adresse formatée)

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
- **Tests de l'approche robuste**: Validation de la déduplication et de la logique "supprimer puis ajouter"
- **Tests P1**: Vérification du fix pour l'écrasement des timestamps en mode append-only
- **Tests d'organisation**: Validation du déplacement automatique des fichiers archived/trashed

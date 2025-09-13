# 📸 Google Photos Takeout Metadata Processor

**Outil professionnel pour appliquer automatiquement les métadonnées JSON de Google Photos Takeout à vos fichiers images/vidéos avec un système de stratégies avancé.**

[![Tests](https://img.shields.io/badge/tests-129%20passing-green)](tests/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![ExifTool](https://img.shields.io/badge/exiftool-13.34%2B-orange)](https://exiftool.org)

---

## 🎯 Fonctionnalités Principales

✅ **Système de stratégies sophistiqué** - Contrôle précis de l'écriture des métadonnées  
✅ **Configuration JSON flexible** - Mapping personnalisable des champs vers les tags EXIF/XMP  
✅ **Gestion intelligente des doublons** - Évite la duplication des personnes et albums  
✅ **Support GPS et géolocalisation** - Préservation des coordonnées géographiques  
✅ **Rating/Favoris avancé** - Logique spéciale pour les photos favorites  
✅ **Normalisation automatique** - Casse intelligente pour noms de personnes  
✅ **129 tests automatisés** - Fiabilité et robustesse garanties  

## ⚡ Installation et Démarrage Rapide

### Prérequis
```bash
# 1. Installer ExifTool (requis)
# Windows: scoop install exiftool
# macOS: brew install exiftool  
# Linux: sudo apt install libimage-exiftool-perl

# 2. Installer les dépendances Python
pip install -r requirements.txt
```

### Usage de base
```bash
# Traiter un dossier Google Photos Takeout
python -m google_takeout_metadata.processor "data/Google Photos/"

# Avec options avancées
python -m google_takeout_metadata.processor "data/Google Photos/" \
    --batch \
    --local-time \
    --overwrite
```

## 🏗️ Architecture et Stratégies

### Stratégies de Métadonnées Disponibles

| Stratégie | Description | Usage |
|-----------|-------------|-------|
| `write_if_missing` | Écrit seulement si le tag n'existe pas | Titres, champs de base |
| `write_if_blank_or_missing` | Écrit si absent ou vide (robuste) | Descriptions |
| `replace_all` | Remplace toujours la valeur | Dates, coordonnées GPS |
| `preserve_existing` | Ne touche jamais aux valeurs existantes | Protection de données |
| `clean_duplicates` | Ajoute sans doublons (remove→add) | Personnes, mots-clés |
| `preserve_positive_rating` | Logique spéciale favoris/rating | Photos favorites |

### Configuration par Défaut

```json
{
  "exif_mapping": {
    "description": {
      "target_tags": ["MWG:Description"],
      "default_strategy": "write_if_blank_or_missing"
    },
    "people_name": {
      "target_tags": ["XMP-iptcExt:PersonInImage"],
      "default_strategy": "clean_duplicates",
      "normalize": "person_name"
    },
    "favorited": {
      "target_tags": ["XMP:Rating"],
      "default_strategy": "preserve_positive_rating",
      "value_mapping": {"true": "5", "false": null}
    }
  }
}
```

## 📋 Champs Supportés

### Métadonnées Texte
- **Description** → `MWG:Description`
- **Titre** → `IPTC:ObjectName`, `XMP-dc:Title`
- **Personnes** → `XMP-iptcExt:PersonInImage`, mots-clés
- **Albums** → Mots-clés avec préfixe "Album: "

### Métadonnées Techniques
- **Dates de création** → `EXIF:DateTimeOriginal`, `EXIF:CreateDate`
- **GPS (latitude/longitude/altitude)** → Tags GPS standard
- **Rating/Favoris** → `XMP:Rating` (5 si favori)

### Normalisation Automatique
- **Noms de personnes** : "john DOE" → "John Doe"
- **Mots-clés** : Capitalisation intelligente
- **Petits mots** : "de", "du", "van", etc. en minuscules

## 🔧 Outils de Développement

### Scripts Utilitaires
```bash
# Découverte automatique des champs
python tools/discover_fields.py "data/Google Photos/"

# Validation de la configuration
python tools/validate_config.py

# Nettoyage de la configuration
python tools/clean_config_file.py
```

### Tests et Validation
```bash
# Exécuter tous les tests
python -m pytest tests/ -v

# Tests d'intégration uniquement
python -m pytest tests/test_integration.py -v

# Tests par stratégie
python -m pytest tests/test_integration.py -k "strategy_pure" -v
```

## � Structure du Projet

```
📁 exif_metadata_google_photo_takeout/
├── 📁 config/
│   ├── exif_mapping.json          ← Configuration principale
│   └── debug_exif_mapping.json    ← Version debug
├── 📁 src/google_takeout_metadata/
│   ├── processor.py               ← Point d'entrée principal
│   ├── exif_writer.py            ← Système de stratégies
│   ├── config_loader.py          ← Chargement configuration
│   └── sidecar.py                ← Parsing JSON Google
├── 📁 tests/
│   ├── test_integration.py       ← Tests complets (10 tests)
│   ├── test_exif_writer.py       ← Tests unitaires
│   └── test_*.py                 ← 129 tests au total
├── 📁 tools/
│   ├── discover_fields.py        ← Découverte automatique
│   ├── validate_config.py        ← Validation config
│   └── demo_discovery.py         ← Démonstrations
└── 📁 docs/
    ├── strategies.md              ← Guide des stratégies
    └── discovery.md               ← Processus de découverte
```

## 🚀 Cas d'Usage Avancés

### Traitement par Lots
```bash
# Mode batch avec toutes les options
python -m google_takeout_metadata.processor \
    "data/Google Photos/" \
    --batch \
    --local-time \
    --overwrite \
    --immediate-delete \
    --geocode
```

### Configuration Personnalisée
```bash
# Utiliser une configuration spécifique
EXIF_CONFIG_PATH="config/custom_mapping.json" \
    python -m google_takeout_metadata.processor "data/"
```

### Debugging et Logs
```bash
# Mode verbose avec logs détaillés
python -m google_takeout_metadata.processor \
    "data/Google Photos/" \
    --verbose \
    --log-level DEBUG
```

## 🔍 Logique Métier Spéciale

### Photos Favorites (preserve_positive_rating)
- `favorited=true` + `Rating>0` → **Préserver** le rating existant
- `favorited=true` + `Rating=0/absent` → **Écrire** Rating=5
- `favorited=false` → **Ne jamais toucher** au rating

### Gestion des Personnes (clean_duplicates)
- Normalisation automatique : "jane doe" → "Jane Doe"  
- Déduplication robuste : évite les doublons lors d'ajouts
- Pattern ExifTool : `-PersonInImage-=Nom` puis `-PersonInImage+=Nom`

### Descriptions (write_if_blank_or_missing)
- Condition robuste : `not defined $tag or not length($tag) or not length($tag[0])`
- Support multi-langues et lang-alt
- Préservation des descriptions existantes

## 🧪 Tests et Qualité

### Couverture de Tests
- **129 tests** au total
- **10 tests d'intégration** complets
- **6 tests purs par stratégie**
- **Tests GPS, favoris, personnes**
- **Validation ExifTool directe**

### Tests Spécifiques par Stratégie
```bash
# Test preserve_positive_rating
python -m pytest tests/test_integration.py::test_preserve_positive_rating_strategy_pure -v

# Test clean_duplicates  
python -m pytest tests/test_integration.py::test_clean_duplicates_strategy_pure -v

# Test write_if_blank_or_missing
python -m pytest tests/test_integration.py::test_write_if_blank_or_missing_strategy_pure -v
```

## 🐛 Debugging et Dépannage

### Logs et Diagnostics
```bash
# Activer les logs debug
python -m google_takeout_metadata.processor \
    "data/" --verbose --log-level DEBUG

# Tester ExifTool directement
exiftool -ver  # Vérifier version ExifTool
```

### Problèmes Courants

**ExifTool introuvable**
```bash
# Vérifier l'installation
exiftool -ver
# Si erreur: installer ExifTool ou l'ajouter au PATH
```

**Files failed condition**
```
# Normal ! Signifie que la condition de stratégie a échoué
# Ex: preserve_existing sur un champ déjà rempli
```

**Encodage des caractères**
```bash
# L'outil gère UTF-8 automatiquement
# Options ExifTool : -charset utf8 -codedcharacterset=utf8
```

## 🤝 Contribution

### Développement Local
```bash
# Cloner et installer
git clone <repo>
cd exif_metadata_google_photo_takeout
pip install -r requirements.txt

# Exécuter les tests
python -m pytest tests/ -v

# Vérifier la qualité du code  
python -m pytest tests/ --tb=short
```

### Ajouter une Nouvelle Stratégie

1. **Définir dans config** : `config/exif_mapping.json`
2. **Implémenter la logique** : `src/google_takeout_metadata/exif_writer.py`
3. **Ajouter des tests** : `tests/test_integration.py`
4. **Documenter** : `docs/strategies.md`

## 📄 Licence

[Voir LICENSE](LICENSE)

---

**🎉 Prêt à traiter vos photos Google ?**

```bash
python -m google_takeout_metadata.processor "data/Google Photos/"
```

**Questions ?** Consultez [`docs/`](docs/) ou ouvrez une issue !

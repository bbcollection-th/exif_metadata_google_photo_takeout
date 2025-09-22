# 📸 EXIF Metadata Google Photo Takeout

**Outil pour appliquer automatiquement les métadonnées JSON de Google Photos aux fichiers images/vidéos.**

## 🚀 Démarrage Rapide

### 1. Installation
```bash
pip install -e .
```

### 2. Configuration Automatique
```bash
# Découvrir automatiquement vos champs JSON
python tools/discover_fields.py "data/Google Photos/" --output config/exif_mapping.json

# Valider la configuration
python tools/validate_config.py config/exif_mapping.json
```

### 3. Traitement
```bash
# Traiter vos photos
python -m google_takeout_metadata "data/Google Photos/"
```

## 📁 Structure du Projet

```
├── 📁 src/                          # Code principal
│   └── google_takeout_metadata/     # Package Python
├── 📁 tools/                        # Outils de découverte
│   ├── discover_fields.py           # Découverte automatique des champs
│   ├── validate_config.py           # Validation de configuration
│   └── clean_config_file.py         # Nettoyage de config
├── 📁 config/                       # Configuration unique
│   ├── exif_mapping.json            # Mapping JSON → EXIF
│   └── .env.example                 # Variables d'environnement
├── 📁 data/                         # Vos données
│   └── Google Photos/               # Dossier Google Takeout
├── 📁 tests/                        # Tests automatisés
├── 📁 docs/                         # Documentation
└── 📁 archive/                      # Anciens fichiers
```

## ⚙️ Configuration

Le fichier `config/exif_mapping.json` définit :
- **Mappings** : Champs JSON → Tags EXIF/XMP
- **Stratégies** : Comment traiter les conflits
- **Paramètres globaux** : Options communes

### Stratégies Disponibles
- `preserve_existing` : Garder les métadonnées existantes
- `replace_all` : Remplacer complètement
- `write_if_missing` : Écrire seulement si absent
- `clean_duplicates` : Nettoyer les doublons

## 🔧 Outils

### Découverte Automatique
```bash
python tools/discover_fields.py "data/Google Photos/" --summary
```
Analyse vos fichiers JSON et génère automatiquement la configuration.

### Validation
```bash
python tools/validate_config.py config/exif_mapping.json --clean
```
Valide et nettoie votre configuration.

## 📚 Documentation

- [`docs/discovery.md`](docs/discovery.md) - Système de découverte automatique
- [`docs/strategies.md`](docs/strategies.md) - Guide des stratégies
- [`tests/`](tests/) - Tests et exemples d'usage

## 🛠️ Développement

```bash
# Tests
pytest

# Installation en mode développement  
pip install -e .

# Linting
ruff check src/
```

## 📄 Licence

Voir [LICENSE](LICENSE)

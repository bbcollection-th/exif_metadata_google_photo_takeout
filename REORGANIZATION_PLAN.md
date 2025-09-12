# 🧹 PLAN DE RÉORGANISATION DU WORKSPACE

## 📊 État Actuel (CHAOS!)
- ❌ 50+ fichiers dans le root
- ❌ Multiples versions de config (exif_mapping_config.json, discovered_config.json, clean_config.json)
- ❌ Scripts éparpillés partout
- ❌ Documentation mélangée avec le code
- ❌ Impossible de savoir ce qui est actuel vs obsolète

## 🎯 Structure Cible

```
📁 exif_metadata_google_photo_takeout/
├── 📁 src/                          # CODE PRINCIPAL
│   └── google_takeout_metadata/     # Package principal existant
├── 📁 tools/                        # OUTILS DE DÉCOUVERTE
│   ├── discover_fields.py           # Découverte automatique  
│   ├── validate_config.py           # Validation
│   ├── clean_config_file.py         # Nettoyage
│   └── README.md                    # Doc des outils
├── 📁 config/                       # CONFIGURATIONS
│   ├── exif_mapping.json            # Config principale SEULE
│   └── .env.example                 # Exemple d'environnement
├── 📁 docs/                         # DOCUMENTATION
│   ├── README.md                    # Doc principale
│   ├── strategies/                  # Doc des stratégies
│   └── examples/                    # Exemples
├── 📁 tests/                        # TESTS (existant)
├── 📁 test_assets/                  # DONNÉES DE TEST (existant)
├── 📁 archive/                      # FICHIERS OBSOLÈTES
│   ├── old_configs/                 # Anciennes configs
│   ├── experiments/                 # Expérimentations
│   └── old_docs/                    # Anciennes docs
└── 📁 data/                         # DONNÉES UTILISATEUR
    └── Google Photos/               # Vos photos (optionnel)
```

## 🚀 Actions

### 1. Créer la nouvelle structure
### 2. Déplacer les fichiers actifs
### 3. Archiver les obsolètes  
### 4. Créer UN SEUL point d'entrée clair
### 5. Documentation simple et claire

## 📋 Fichiers à Classer

### ✅ CODE ACTUEL (à garder)
- src/ → GARDER
- tests/ → GARDER  
- pyproject.toml, requirements.txt → GARDER

### 🔧 OUTILS RÉCENTS (à organiser)
- discover_fields.py → tools/
- validate_config.py → tools/
- clean_config_file.py → tools/
- demo_discovery.py → tools/ ou archive/

### ⚙️ CONFIGURATIONS (à simplifier)
- exif_mapping_config.json → config/exif_mapping.json (principal)
- discovered_config.json → SUPPRIMER (temporaire)
- clean_config.json → SUPPRIMER (temporaire)

### 📚 DOCUMENTATION (à organiser)
- README.md → docs/README.md (principal)
- DISCOVERY_SYSTEM_README.md → docs/discovery.md
- EXEMPLES_STRATEGIES.md → docs/strategies/
- Autres *.md → docs/ ou archive/

### 🗄️ À ARCHIVER (probablement obsolète)
- repomix-output.md.txt → archive/
- doc_exiftool_full.txt → archive/
- error_files.txt, unchanged_files.txt → archive/
- AUDIT_*, REFACTOR_*, TERMINOLOGY_* → archive/

### 📁 DONNÉES
- Google Photos/ → data/ (optionnel)
- Google Photos copy/ → archive/ ou SUPPRIMER

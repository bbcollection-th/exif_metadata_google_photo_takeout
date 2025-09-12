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

# 🔧 Outils de Découverte EXIF

Outils pour découvrir automatiquement et configurer les mappings EXIF depuis vos données Google Photos.

## 🔍 discover_fields.py

**Découverte automatique des champs JSON**

```bash
# Découvrir tous les champs dans vos données
python discover_fields.py "../data/Google Photos/" --summary

# Générer une configuration personnalisée
python discover_fields.py "../data/Google Photos/" --output ../config/my_config.json
```

**Fonctionnalités :**
- ✅ Scan récursif des fichiers JSON
- ✅ Détection intelligente des types de données
- ✅ Mapping automatique vers tags EXIF/XMP
- ✅ Assignation de stratégies par défaut
- ✅ Statistiques détaillées

## ✅ validate_config.py

**Validation et nettoyage de configuration**

```bash
# Valider une configuration
python validate_config.py ../config/exif_mapping.json

# Nettoyer et optimiser
python validate_config.py ../config/exif_mapping.json --clean --min-frequency 5
```

**Fonctionnalités :**
- ✅ Validation de la structure
- ✅ Détection des doublons et conflits
- ✅ Nettoyage basé sur la fréquence
- ✅ Suggestions d'amélioration

## 🧹 clean_config_file.py

**Nettoyage des informations de debug**

```bash
# Nettoyer un fichier de configuration
python clean_config_file.py ../config/exif_mapping.json
```

**Fonctionnalités :**
- ✅ Supprime les informations de debug (`_discovery_info`)
- ✅ Garde seulement les propriétés essentielles
- ✅ Crée une sauvegarde automatiquement

## 🚀 Workflow Recommandé

1. **Découverte** : `discover_fields.py` pour analyser vos données
2. **Validation** : `validate_config.py` pour vérifier la configuration
3. **Nettoyage** : `clean_config_file.py` pour épurer le fichier final
4. **Utilisation** : Configuration prête pour le traitement

## 📋 Exemples

### Découverte Complète
```bash
# Analyse complète avec nettoyage automatique
python discover_fields.py "../data/Google Photos/" --output ../config/exif_mapping.json --summary
python validate_config.py ../config/exif_mapping.json --clean --min-frequency 3
python clean_config_file.py ../config/exif_mapping.json
```

### Configuration Personnalisée
```bash
# Pour des champs très fréquents seulement
python discover_fields.py "../data/Google Photos/" --min-frequency 10 --output ../config/frequent_only.json
```

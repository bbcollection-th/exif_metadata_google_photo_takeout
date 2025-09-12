# 🔍 Système de Découverte et Configuration EXIF

Ce système permet de découvrir automatiquement les champs de métadonnées dans vos fichiers JSON Google Photos et de générer une configuration optimisée pour l'écriture EXIF.

## 🚀 Aperçu Rapide

```bash
# 1. Découverte automatique des champs
python discover_fields.py "Google Photos/" --output discovered_config.json --summary

# 2. Validation et nettoyage
python validate_config.py discovered_config.json --clean --output clean_config.json

# 3. Démonstration complète
python demo_discovery.py "Google Photos/"
```

## 📋 Composants

### 🔍 `discover_fields.py` - Découverte Automatique

Scanne récursivement vos fichiers JSON Google Photos pour découvrir tous les champs disponibles.

**Fonctionnalités :**
- ✅ Analyse récursive des structures JSON
- ✅ Détection intelligente des types de données
- ✅ Calcul de fréquence d'apparition
- ✅ Génération automatique de stratégies par défaut
- ✅ Mapping intelligent vers tags EXIF/XMP
- ✅ Rapport détaillé des découvertes

**Usage :**
```bash
python discover_fields.py /path/to/google/photos/ [options]

Options:
  --output FILE         Fichier de sortie (défaut: exif_mapping_config.json)
  --summary            Afficher un résumé détaillé
  --min-frequency N    Fréquence minimale pour inclure un champ (défaut: 1)
```

**Exemple de sortie :**
```
🔍 Analyse de : /Google Photos/
📁 Répertoires analysés : 15
📄 Fichiers JSON traités : 1,247
🔥 Champs uniques découverts : 87

🔥 TOP 10 DES CHAMPS LES PLUS FRÉQUENTS:
   photoTakenTime.timestamp (1,247x) → EXIF:DateTimeOriginal
   title (1,198x) → EXIF:ImageDescription
   geoData.latitude (892x) → GPS:GPSLatitude
   description (745x) → XMP-dc:Description
   people[].name (623x) → XMP-iptcExt:PersonInImage
```

### ✅ `validate_config.py` - Validation et Nettoyage

Valide la configuration générée et propose un nettoyage intelligent.

**Fonctionnalités :**
- ✅ Validation de la structure de configuration
- ✅ Vérification des stratégies valides
- ✅ Détection des doublons de tags
- ✅ Nettoyage basé sur la fréquence
- ✅ Suppression des champs techniques
- ✅ Rapport de validation détaillé

**Usage :**
```bash
python validate_config.py config.json [options]

Options:
  --clean              Nettoyer la configuration
  --min-frequency N    Fréquence minimale pour garder un champ (défaut: 5)
  --output FILE        Fichier de sortie pour la version nettoyée
  --verbose           Mode verbeux
```

**Exemple de sortie :**
```
============================================================
📋 RAPPORT DE VALIDATION
============================================================

🚨 PROBLÈMES DÉTECTÉS (2):
   ⚠️ Tag XMP:Location utilisé par plusieurs mappings : ['geoData_location', 'address_formatted']
   ⚠️ Stratégie inconnue : auto_detect

💡 SUGGESTIONS (5):
   💡 Champ rare (3x) : debug_info - considérer la suppression
   💡 Tag possiblement incorrect : XMP-custom:PersonCount
```

### 🚀 `demo_discovery.py` - Démonstration Complète

Script de démonstration qui illustre le workflow complet.

**Workflow :**
1. 📡 Découverte automatique des champs
2. ✅ Validation de la configuration
3. 🧹 Nettoyage et optimisation
4. 🔗 Intégration avec le système

**Usage :**
```bash
python demo_discovery.py /path/to/google/photos/ [--keep-temp]
```

## 🔧 Configuration Générée

La configuration générée suit cette structure :

```json
{
  "metadata_mappings": {
    "photoTakenTime_timestamp": {
      "source_fields": ["photoTakenTime.timestamp"],
      "target_tags": ["EXIF:DateTimeOriginal", "EXIF:CreateDate"],
      "default_strategy": "write_if_missing",
      "data_transformer": "timestamp_to_datetime",
      "description": "Date et heure de prise de vue",
      "_discovery_info": {
        "frequency": 1247,
        "data_types": ["int"],
        "sample_values": [1640995200, 1641081600]
      }
    }
  },
  "strategies": {
    "preserve_existing": {
      "description": "Préserver les métadonnées existantes",
      "exiftool_args": ["-if", "not $EXIF:ImageDescription"]
    },
    "replace_all": {
      "description": "Remplacer toutes les métadonnées",
      "exiftool_args": ["-wm", "cg"]
    },
    "write_if_missing": {
      "description": "Écrire seulement si absent",
      "exiftool_args": ["-if", "not defined $EXIF:ImageDescription"]
    },
    "clean_duplicates": {
      "description": "Nettoyer les doublons",
      "exiftool_args": ["-wm", "cg", "-duplicates"]
    }
  },
  "global_settings": {
    "default_strategy": "write_if_missing",
    "backup_original": true,
    "verify_write": true
  }
}
```

## 🎯 Stratégies Intelligentes

Le système assigne automatiquement des stratégies basées sur le type de données :

| Type de Champ | Stratégie par Défaut | Raison |
|---------------|---------------------|---------|
| `photoTakenTime.*` | `write_if_missing` | Dates critiques à préserver |
| `title` | `preserve_existing` | Titres souvent modifiés manuellement |
| `description` | `preserve_existing` | Descriptions personnalisées |
| `geoData.*` | `replace_all` | Coordonnées GPS précises |
| `people[].name` | `replace_all` | Reconnaissance faciale à jour |

## 📊 Mapping Intelligent des Tags

Le système mappe automatiquement les champs JSON vers des tags EXIF/XMP standard :

```
photoTakenTime.timestamp → EXIF:DateTimeOriginal, EXIF:CreateDate
title → EXIF:ImageDescription, XMP-dc:Title
description → XMP-dc:Description, IPTC:Caption-Abstract
geoData.latitude → GPS:GPSLatitude
geoData.longitude → GPS:GPSLongitude
people[].name → XMP-iptcExt:PersonInImage
```

## 🔄 Intégration avec `config_loader.py`

Le système s'intègre parfaitement avec le module de configuration existant :

```python
from google_takeout_metadata.config_loader import ConfigLoader

# Chargement automatique de la configuration découverte
loader = ConfigLoader()
config = loader.load_config()

# La configuration est maintenant prête pour exif_writer.py
```

## 🛠️ Cas d'Usage Typiques

### 1. Première Configuration

```bash
# Scan initial de vos photos Google
python discover_fields.py "Google Photos/" --summary

# Validation et nettoyage
python validate_config.py exif_mapping_config.json --clean --min-frequency 10

# Test avec vos données
python demo_discovery.py "Google Photos/"
```

### 2. Mise à Jour de Configuration

```bash
# Re-scan après ajout de nouvelles photos
python discover_fields.py "Google Photos/" --output new_discovery.json

# Comparaison et validation
python validate_config.py new_discovery.json --verbose
```

### 3. Configuration Personnalisée

```bash
# Découverte avec seuil élevé pour les champs fréquents uniquement
python discover_fields.py "Google Photos/" --min-frequency 50 --output frequent_fields.json
```

## 📈 Métriques et Optimisation

Le système fournit des métriques détaillées pour optimiser votre configuration :

- **Fréquence d'apparition** : Priorité aux champs les plus communs
- **Types de données** : Optimisation des transformateurs
- **Couverture** : Pourcentage de fichiers concernés par chaque mapping
- **Performance** : Temps de traitement estimé

## 🎉 Résultat Final

Après ce processus, vous obtenez :

1. ✅ **Configuration optimisée** adaptée à vos données spécifiques
2. ✅ **Stratégies intelligentes** basées sur l'analyse réelle
3. ✅ **Mappings validés** vers des tags EXIF/XMP standard
4. ✅ **Performance optimisée** avec suppression des champs rares
5. ✅ **Intégration transparente** avec votre workflow existant

Votre configuration est maintenant prête pour traiter efficacement toutes vos photos Google Photos ! 🚀

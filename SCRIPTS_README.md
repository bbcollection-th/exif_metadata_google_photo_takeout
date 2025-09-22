# 🚀 Scripts de Traitement Automatique

Ces scripts permettent un traitement simple par **glisser-déposer** de vos dossiers Google Photos Takeout.

## 📁 Utilisation Rapide (Glisser-Déposer)

### Windows Batch (.bat)
1. **Glissez-déposez** votre dossier `Google Photos` directement sur `google_photos_processor.bat`
2. Suivez le menu interactif pour choisir vos options
3. Le traitement se lance automatiquement

### PowerShell (.ps1) - Recommandé
1. **Glissez-déposez** votre dossier `Google Photos` directement sur `google_photos_processor.ps1`
2. Interface plus moderne avec couleurs et progression
3. Meilleure gestion d'erreurs et diagnostic

## 🔧 Options Disponibles

| Mode | Description | Arguments |
|------|-------------|-----------|
| **Standard** | Traitement de base (recommandé) | Aucun |
| **Organisation** | Organise les fichiers par date | `--batch` |
| **Géocodage** | Ajoute la géolocalisation | `--geocode` |
| **Complet** | Organisation + géocodage | `--batch --geocode` |
| **Test** | Aperçu sans modification | `--dry-run` |
| **Heure locale** | Utilise l'heure locale | `--local-time` |

## 💻 Utilisation en Ligne de Commande

### Batch
```cmd
google_photos_processor.bat "C:\Takeout\Google Photos"
```

### PowerShell
```powershell
.\google_photos_processor.ps1 "C:\Takeout\Google Photos"
.\google_photos_processor.ps1 "C:\Takeout\Google Photos" -Batch -Geocode
.\google_photos_processor.ps1 "C:\Takeout\Google Photos" -DryRun
```

## ⚙️ Prérequis Automatiquement Vérifiés

Les scripts vérifient automatiquement :

- ✅ **Python** (environnement virtuel `.venv` ou système)
- ✅ **ExifTool** (version 13.34+ recommandée)
- ✅ **Fichiers JSON** dans le dossier source
- ✅ **Permissions** d'écriture

## 🏗️ Fonctionnement Interne

1. **Détection automatique** de l'environnement Python
2. **Vérification** des prérequis (ExifTool, fichiers JSON)
3. **Menu interactif** pour choisir les options
4. **Exécution** de `python -m google_takeout_metadata`
5. **Rapport** de fin avec statistiques

## 🐛 Résolution de Problèmes

### "Python non trouvé"
- Installez Python depuis [python.org](https://python.org)
- Ou créez un environnement virtuel : `python -m venv .venv`

### "ExifTool non trouvé"
- Installez ExifTool depuis [exiftool.org](https://exiftool.org)
- Ajoutez-le au PATH système

### "Aucun fichier JSON trouvé"
- Vérifiez que le dossier contient des fichiers `.json` de Google Photos
- Structure attendue : `IMG_20231225_120000.jpg` + `IMG_20231225_120000.jpg.json`

### PowerShell bloqué par la politique d'exécution
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## 📋 Exemple de Sortie

```
============================================================
   Google Photos Takeout Metadata Processor
   Script PowerShell de traitement automatique
============================================================

🔍 Vérification de l'environnement...
✅ Dossier source: C:\Takeout\Google Photos
✅ 1,247 fichier(s) JSON trouvé(s)
✅ Python trouvé dans l'environnement virtuel local
✅ ExifTool trouvé, version: 13.34

🔧 Options de traitement:
   [1] Traitement standard (recommandé)
   [2] Traitement avec organisation des fichiers
   [...]

🚀 Démarrage du traitement...
📂 Commande: .venv\Scripts\python.exe -m google_takeout_metadata "C:\Takeout\Google Photos"

[... traitement en cours ...]

✅ Traitement terminé avec succès !
⏱️ Durée du traitement: 00:05:23

📊 Résultats:
   • Métadonnées appliquées aux fichiers images/vidéos
   • Fichiers JSON traités

🎯 Vos fichiers sont maintenant enrichis avec leurs métadonnées !
```

## 🎯 Avantages

- **Simplicité** : Glisser-déposer sans ligne de commande
- **Fiabilité** : Vérifications automatiques des prérequis
- **Flexibilité** : Menu d'options pour tous les besoins
- **Transparence** : Affichage des commandes exécutées
- **Cross-platform** : Support Windows Batch et PowerShell

---

💡 **Astuce** : Créez un raccourci de ces scripts sur votre bureau pour un accès encore plus rapide !
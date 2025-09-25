# 📁 Organisateur de Photos par Date

Ce dossier contient plusieurs outils pour organiser automatiquement vos photos par date en utilisant les métadonnées EXIF.

## 🎯 Résultat

Tous les outils créent une structure de dossiers basée sur la date de prise de vue :

```
/vos_photos/
├── 2023-01/         # Photos de janvier 2023
├── 2023-02/         # Photos de février 2023  
├── 2024-12/         # Photos de décembre 2024
└── unknown_date/    # Photos sans date dans les métadonnées
```

## 🛠️ Outils Disponibles

### 1. Script Python Avancé (`organize_by_date.py`)

**Le plus complet et robuste**

```bash
# Installation des dépendances (une seule fois)
pip install -r requirements.txt

# Usage de base
python tools/organize_by_date.py "/chemin/vers/photos"

# Mode simulation (voir ce qui serait fait)  
python tools/organize_by_date.py "/chemin/vers/photos" --dry-run

# Organiser vers un autre dossier
python tools/organize_by_date.py "/chemin/vers/photos" --target-dir "/dossier/organisé"

# Mode verbose (logs détaillés)
python tools/organize_by_date.py "/chemin/vers/photos" --verbose
```

**Avantages :**
- ✅ **Traitement par lots** (très rapide)
- ✅ **Gestion intelligente des conflits** de noms
- ✅ **119 formats** d'images/vidéos supportés
- ✅ **Logs détaillés** et statistiques
- ✅ **Gestions d'erreurs complètes** (permissions, espace disque, timeouts, etc.)
- 🏆 **SEUL SCRIPT VRAIMENT ROBUSTE**

---

### 2. Script Batch Windows (`organize_photos_by_date.bat`)

**Pour les utilisateurs Windows - Glisser-déposer**

```bash
# Méthode 1: Glisser-déposer
# → Glissez votre dossier de photos sur organize_photos_by_date.bat

# Méthode 2: Ligne de commande  
organize_photos_by_date.bat "C:\Mes Photos"
```

**Avantages :**
- 🖱️ **Interface simple** → Menu interactif
- ✅ **Glisser-déposer** → Aucune ligne de commande
- 🎯 **3 modes** → Simulation, Organisation, Autre dossier

⚠️ **Limitation** : Appelle le script Python basique, **pas les nouvelles gestions d'erreurs**

---

### 3. Script PowerShell (`organize_photos.ps1`)

**Pour Windows PowerShell**

```powershell  
# Usage de base
.\tools\organize_photos.ps1 "C:\Mes Photos"

# Mode simulation
.\tools\organize_photos.ps1 "C:\Mes Photos" -DryRun

# Vers autre dossier avec logs détaillés
.\tools\organize_photos.ps1 "C:\Mes Photos" -TargetDir "C:\Photos Organisées" -Verbose
```

**Avantages :**
- ⚡ **Natif Windows** → Aucune dépendance Python
- 🎨 **Interface colorée** et progress
- 📊 **Statistiques détaillées**

⚠️ **Limitation** : Code séparé, **pas les gestions d'erreurs avancées** du Python

---

### 4. Script Bash/Linux (`organize_photos_exiftool.sh`)

**Pour Linux/macOS - ExifTool pur**

```bash
# Rendre exécutable (une seule fois)
chmod +x tools/organize_photos_exiftool.sh

# Usage de base
./tools/organize_photos_exiftool.sh "/home/user/Photos"

# Mode simulation
DRY_RUN=true ./tools/organize_photos_exiftool.sh "/home/user/Photos"

# Vers autre dossier
./tools/organize_photos_exiftool.sh "/home/user/Photos" "/home/user/Photos_Organisées"
```

**Avantages :**
- 🐧 **Linux/macOS natif**
- ⚡ **ExifTool pur** → Très rapide  
- 📦 **Aucune dépendance** Python

⚠️ **Limitation** : Prototype basique, **aucune gestion d'erreurs avancée**

---

## 🎯 Quel Outil Choisir ?

| Situation | Outil Recommandé | Pourquoi |
|-----------|------------------|----------|
| **🏆 RECOMMANDÉ** | `organize_by_date.py` | **Seul avec gestion d'erreurs complète** |
| **Windows simple** | `organize_photos_by_date.bat` | ⚠️ Appelle le Python (wrapper) |
| **Collection importante** | `organize_by_date.py` | Gestion permissions, espace disque, timeouts |
| **Linux/macOS** | `organize_photos_exiftool.sh` | ⚠️ Basique, pas de gestions d'erreurs |

⚠️ **ATTENTION** : Les scripts Batch/PowerShell/Bash sont des **prototypes basiques** sans les gestions d'erreurs avancées ajoutées récemment au script Python.

## 📋 Formats Supportés

**Images :**
- JPG/JPEG, PNG, GIF, BMP, TIFF
- HEIC/HEIF (iPhone), WebP  
- RAW : CR2, NEF, ARW, DNG

**Vidéos :**
- MP4, MOV, AVI, MKV, WMV, M4V

## 🔍 Priorité des Dates

Les outils recherchent les dates dans cet ordre :

1. **`DateTimeOriginal`** (EXIF) → Date de prise de vue
2. **`CreateDate`** (EXIF) → Date de création  
3. **`CreationDate`** (QuickTime) → Vidéos
4. **`DateCreated`** (XMP/IPTC) → Métadonnées
5. **`FileModifyDate`** → Date de modification du fichier

## ⚠️ Précautions

- **Testez d'abord** avec `--dry-run` ou le mode simulation
- **Sauvegardez** vos photos avant organisation
- Les fichiers **sans date** vont dans `unknown_date/`
- **Conflits de noms** → Suffixe automatique `_001`, `_002`

## 🚀 Exemples Rapides

```bash
# Windows : Glisser-déposer sur organize_photos_by_date.bat
# OU
python tools/organize_by_date.py "C:\Mes Photos" --dry-run

# Linux/macOS
./tools/organize_photos_exiftool.sh "$HOME/Photos"

# PowerShell
.\tools\organize_photos.ps1 "C:\Photos" -DryRun -Verbose
```

## 🔧 Dépannage

**ExifTool non trouvé :**
```bash
# Windows  
scoop install exiftool

# macOS
brew install exiftool

# Linux
sudo apt install libimage-exiftool-perl
```

**Python non trouvé :**
```bash
# Installer Python 3.10+
# puis: pip install -r requirements.txt
```

**Permissions :**
```bash  
# Linux/macOS : rendre exécutable
chmod +x tools/organize_photos_exiftool.sh

# Windows : exécuter en tant qu'administrateur si nécessaire
```

## 📊 Exemple de Sortie

```
==========================================
                STATISTIQUES FINALES  
==========================================
2023-01          :   45 fichiers
2023-02          :   67 fichiers  
2024-12          :  123 fichiers
unknown_date     :    8 fichiers

Total traité: 243/243 fichiers
```
# 🛡️ Gestion d'Erreurs - Script `organize_by_date.py`

## ✅ Erreurs Complètement Gérées

### **1. Erreurs Système/Environnement**
- **ExifTool non installé** → `RuntimeError` avec message d'installation
- **Dossier source inexistant** → `FileNotFoundError` avec chemin précis
- **Permissions lecture source** → `PermissionError` avec diagnostic
- **Permissions écriture destination** → Test automatique avec fichier temporaire
- **Espace disque insuffisant** → Calcul automatique + marge 20%

### **2. Erreurs Validation Dossiers**
- **Source = Destination** → Warning (organisation en sous-dossiers)
- **Destination sous-dossier de Source** → `ValueError` (évite boucles infinies)
- **Chemins invalides** → `Path.resolve()` normalise automatiquement

### **3. Erreurs ExifTool**
- **Timeout** → 5 minutes max, puis erreur explicite
- **Ligne commande trop longue** → Détection + réduction automatique batch
- **Formats non supportés** → Filtrage par extensions (ignorés silencieusement)  
- **Métadonnées corrompues** → `json.JSONDecodeError` → batch ignoré
- **Processus ExifTool échoué** → `subprocess.CalledProcessError` avec stderr

### **4. Erreurs Fichiers**
- **Conflits noms** → Suffixe automatique `_001`, `_002`, etc.
- **Fichier source disparu** → Vérification existence avant déplacement
- **Fichier verrouillé** → `OSError errno=32` détecté et signalé
- **Caractères spéciaux** → `UnicodeError` catchée spécifiquement
- **Permissions fichier** → `PermissionError` spécifique vs générale

### **5. Erreurs Performance**
- **Trop de fichiers** → Traitement par batch de 50 (vs 100 original)
- **Mémoire** → Traitement streaming, pas de chargement complet
- **JSON volumineux** → Parsing par batch, pas global

## 📊 Résumé des Améliorations Ajoutées

| Type d'Erreur | Avant | Après |
|---------------|--------|--------|
| **Permissions** | ❌ Non géré | ✅ Test automatique + erreurs spécifiques |
| **Espace disque** | ❌ Non géré | ✅ Calcul + estimation + marge |
| **Timeout ExifTool** | ❌ Blocage infini | ✅ 5min max + message clair |
| **Ligne commande** | ❌ Erreur cryptique | ✅ Détection + batch réduit |
| **Validation dossiers** | ❌ Boucles possibles | ✅ Validation + protection |
| **Fichiers verrouillés** | ❌ Exception générale | ✅ Message spécifique |
| **Caractères spéciaux** | ❌ Crash possible | ✅ `UnicodeError` catchée |
| **Batch size** | ❌ 100 (risqué) | ✅ 50 (plus sûr) |

## 🔍 Messages d'Erreur Exemple

```bash
# Permissions
❌ "Permissions insuffisantes pour écrire dans: /destination. Erreur: [Errno 13] Permission denied"

# Espace disque  
❌ "Espace disque insuffisant. Requis: 1250.3MB, Disponible: 1100.5MB"

# Timeout
❌ "Timeout ExifTool (>5min) pour 50 fichiers. Réduisez la taille du lot."

# Ligne commande
❌ "Ligne de commande trop longue (50 fichiers). Réduisez batch_size."

# Fichier verrouillé
❌ "Fichier verrouillé ou en cours d'utilisation: photo.jpg"

# Validation dossiers
❌ "Le dossier de destination (/source/organized) ne peut pas être un sous-dossier du source (/source)"
```

## 🚀 Script Maintenant Robuste

Le script peut maintenant gérer :
- ✅ **Grandes collections** (>10 000 photos)
- ✅ **Permissions complexes** (réseaux, USB, etc.)
- ✅ **Fichiers problématiques** (verrouillés, caractères spéciaux)
- ✅ **Ressources limitées** (espace disque, mémoire)
- ✅ **Configurations diverses** (même dossier, sous-dossiers)

**Mode d'emploi sûr :**
```bash
# Test toujours d'abord
python tools/organize_by_date.py "/mes/photos" --dry-run

# Puis exécution réelle
python tools/organize_by_date.py "/mes/photos" --verbose
```
# 📋 Fiche Stratégies - Aide-mémoire

## Situation : Image a `[A, B, C]` + JSON a `[C, D, F]`

| Stratégie | Résultat final | Note |
|-----------|---------------|------|
| **preserve_existing** | `[A, B, C]` | ⚠️ Rien d'écrit (tags existent) |
| **replace_all** | `[C, D, F]` | 🔄 Remplace complètement |
| **write_if_missing** | `[A, B, C, D, F]` | ➕ Ajoute seulement nouveaux |
| **clean_duplicates** | `[A, B, C, D, F]` | ✨ Ajoute + évite doublons |

---

## 🎯 Combinaisons utiles

```python
# Mode sécurisé : préserver + enrichir
description_strategy="preserve_existing"
people_strategy="write_if_missing"

# Mode nettoyage intelligent 
description_strategy="replace_all"
people_strategy="clean_duplicates"

# Mode reprise safe
tout="write_if_missing"
```
---
# Fiche des Stratégies d'Écriture - Exemples Concrets

## Situation de départ

**Image existante contient :**
- PersonInImage: `["Alice", "Bob", "Charlie"]`
- Description: `"Vacances été 2023"`
- Rating: `4`
- Keywords: `["Famille", "Vacances"]`

**Fichier .json contient :**
- PersonInImage: `["Charlie", "David", "Eve"]`  
- Description: `"Voyage en montagne"`
- Rating: `5`
- Keywords: `["Montagne", "Randonnée"]`

---

## Résultats selon les stratégies

### 1. **preserve_existing** (utilise `-wm cg`)

**Commande ExifTool générée :**
```bash
exiftool -wm cg \
  -EXIF:ImageDescription="Voyage en montagne" \
  -XMP:Rating=5 \
  image.jpg
```

**Résultat final dans l'image :**
- PersonInImage: `["Alice", "Bob", "Charlie"]` ← **PRÉSERVÉ**
- Description: `"Vacances été 2023"` ← **PRÉSERVÉ** 
- Rating: `4` ← **PRÉSERVÉ**
- Keywords: `["Famille", "Vacances"]` ← **PRÉSERVÉ**

> ⚠️ **Avec -wm cg, RIEN n'est écrit car tous les tags existent déjà**

---

### 2. **replace_all** (mode normal)

**Commande ExifTool générée :**
```bash
exiftool \
  -EXIF:ImageDescription="Voyage en montagne" \
  -XMP-iptcExt:PersonInImage= \
  -XMP-iptcExt:PersonInImage+=Charlie \
  -XMP-iptcExt:PersonInImage+=David \
  -XMP-iptcExt:PersonInImage+=Eve \
  -XMP:Rating=5 \
  -XMP-dc:Subject= \
  -IPTC:Keywords= \
  -XMP-dc:Subject+=Montagne \
  -XMP-dc:Subject+=Randonnée \
  -IPTC:Keywords+=Montagne \
  -IPTC:Keywords+=Randonnée \
  image.jpg
```

**Résultat final dans l'image :**
- PersonInImage: `["Charlie", "David", "Eve"]` ← **REMPLACÉ**
- Description: `"Voyage en montagne"` ← **REMPLACÉ**
- Rating: `5` ← **REMPLACÉ**
- Keywords: `["Montagne", "Randonnée"]` ← **REMPLACÉ**

---

### 3. **write_if_missing** (utilise `-if`)

**Commande ExifTool générée :**
```bash
exiftool \
  -if "not $EXIF:ImageDescription" \
  -EXIF:ImageDescription="Voyage en montagne" \
  -if "not $XMP-iptcExt:PersonInImage=~/Charlie/i" \
  -XMP-iptcExt:PersonInImage+=Charlie \
  -if "not $XMP-iptcExt:PersonInImage=~/David/i" \
  -XMP-iptcExt:PersonInImage+=David \
  -if "not $XMP-iptcExt:PersonInImage=~/Eve/i" \
  -XMP-iptcExt:PersonInImage+=Eve \
  -if "not $XMP:Rating" \
  -XMP:Rating=5 \
  image.jpg
```

**Résultat final dans l'image :**
- PersonInImage: `["Alice", "Bob", "Charlie", "David", "Eve"]` ← **David et Eve AJOUTÉS**
- Description: `"Vacances été 2023"` ← **PRÉSERVÉ** (condition failed)
- Rating: `4` ← **PRÉSERVÉ** (condition failed)
- Keywords: `["Famille", "Vacances", "Montagne", "Randonnée"]` ← **Montagne et Randonnée AJOUTÉS**

---

### 4. **clean_duplicates** (utilise `-=` puis `+=`)

**Commande ExifTool générée :**
```bash
exiftool \
  -EXIF:ImageDescription="Voyage en montagne" \
  -XMP-iptcExt:PersonInImage-=Charlie \
  -XMP-iptcExt:PersonInImage+=Charlie \
  -XMP-iptcExt:PersonInImage-=David \
  -XMP-iptcExt:PersonInImage+=David \
  -XMP-iptcExt:PersonInImage-=Eve \
  -XMP-iptcExt:PersonInImage+=Eve \
  -XMP:Rating=5 \
  -XMP-dc:Subject-=Montagne \
  -XMP-dc:Subject+=Montagne \
  -XMP-dc:Subject-=Randonnée \
  -XMP-dc:Subject+=Randonnée \
  image.jpg
```

**Résultat final dans l'image :**
- PersonInImage: `["Alice", "Bob", "Charlie", "David", "Eve"]` ← **Charlie nettoyé, David et Eve ajoutés**
- Description: `"Voyage en montagne"` ← **REMPLACÉ**
- Rating: `5` ← **REMPLACÉ**
- Keywords: `["Famille", "Vacances", "Montagne", "Randonnée"]` ← **Nouveaux mots-clés ajoutés sans doublons**

---

## Combinaisons de stratégies

### Exemple : Stratégie mixte
```python
args = build_exiftool_args(
    meta,
    description_strategy="write_if_missing",     # Description seulement si absente
    people_keywords_strategy="clean_duplicates", # Nettoyer doublons personnes
    rating_strategy="preserve_existing"          # Garder rating existant
)
```

**Commande ExifTool générée :**
```bash
exiftool -wm cg \  # Pour rating
  -if "not $EXIF:ImageDescription" \
  -EXIF:ImageDescription="Voyage en montagne" \
  -wm w \  # Revenir au mode normal pour clean_duplicates
  -XMP-iptcExt:PersonInImage-=Charlie \
  -XMP-iptcExt:PersonInImage+=Charlie \
  -XMP-iptcExt:PersonInImage-=David \
  -XMP-iptcExt:PersonInImage+=David \
  -XMP-iptcExt:PersonInImage-=Eve \
  -XMP-iptcExt:PersonInImage+=Eve \
  -XMP:Rating=5 \
  image.jpg
```

**Résultat final dans l'image :**
- PersonInImage: `["Alice", "Bob", "Charlie", "David", "Eve"]` ← **Nettoyé et enrichi**
- Description: `"Vacances été 2023"` ← **PRÉSERVÉ** (condition failed)
- Rating: `4` ← **PRÉSERVÉ** (grâce à -wm cg)
- Keywords: `["Famille", "Vacances", "Montagne", "Randonnée"]` ← **Enrichi sans doublons**

---

## Cas d'usage recommandés

| Stratégie | Quand l'utiliser | Avantages | Inconvénients |
|-----------|------------------|-----------|---------------|
| `preserve_existing` | 1ère passe, données précieuses | Sécurisé, rien perdu | Peut ne rien écrire |
| `replace_all` | Nettoyage, réorganisation | Prévisible, cohérent | Destructeur |
| `write_if_missing` | Reprises, enrichissement | Respectueux, enrichit | Peut créer des incohérences |
| `clean_duplicates` | Listes (personnes/mots-clés) | Évite doublons | Plus complexe |

---

## Notes techniques

- **`-wm cg`** : Copy Group - n'écrit que si le groupe (EXIF/XMP) n'existe pas déjà
- **`-if "not $TAG"`** : Condition - n'écrit que si le tag est vide/absent
- **`-TAG-=val`** puis **`-TAG+=val`** : Supprime toutes les occurrences de 'val' puis en ajoute une
- Les stratégies peuvent être mélangées selon les besoins de chaque type de métadonnée

# Exemples d'utilisation des stratégies d'écriture flexibles

Le nouveau système permet de combiner différentes stratégies d'écriture selon les besoins :

## Stratégies disponibles

### 1. **preserve_existing** 
- Utilise `-wm cg` pour préserver l'existant
- Idéal pour préserver les métadonnées déjà présentes

### 2. **replace_all**
- Remplace complètement les valeurs
- Idéal pour nettoyer et réécrire

### 3. **write_if_missing** 
- Utilise `-if` pour n'écrire que si absent
- Idéal pour les reprises et éviter d'écraser

### 4. **clean_duplicates** (pour listes)
- Supprime puis ajoute pour éviter les doublons
- Idéal pour personnes/mots-clés

## Exemples d'utilisation

```python
from google_takeout_metadata.exif_writer import build_exiftool_args

# Exemple 1: Mode conservateur (défaut actuel)
args = build_exiftool_args(meta, append_only=True)
# ↓ Équivaut à :
args = build_exiftool_args(
    meta,
    description_strategy="preserve_existing",
    people_keywords_strategy="clean_duplicates", 
    rating_strategy="preserve_existing",
    source_app_strategy="write_if_missing"
)

# Exemple 2: Mode agressif de nettoyage
args = build_exiftool_args(meta, append_only=False)
# ↓ Équivaut à :
args = build_exiftool_args(
    meta,
    description_strategy="replace_all",
    people_keywords_strategy="replace_all",
    rating_strategy="replace_all",
    source_app_strategy="replace_all"
)

# Exemple 3: Stratégie mixte personnalisée
args = build_exiftool_args(
    meta,
    description_strategy="write_if_missing",     # N'écrire que si absent
    people_keywords_strategy="clean_duplicates", # Éviter doublons
    rating_strategy="preserve_existing",         # Préserver existant
    source_app_strategy="write_if_missing"       # N'écrire que si absent
)

# Exemple 4: Cas spécial - préserver description mais nettoyer personnes
args = build_exiftool_args(
    meta,
    description_strategy="preserve_existing",    # Garder description existante
    people_keywords_strategy="replace_all",      # Nettoyer complètement personnes
    rating_strategy="write_if_missing",          # Rating seulement si absent
    source_app_strategy="write_if_missing"
)

# Exemple 5: Mode "reprise safe" - ne toucher à rien qui existe déjà
args = build_exiftool_args(
    meta,
    description_strategy="write_if_missing",
    people_keywords_strategy="write_if_missing", 
    rating_strategy="write_if_missing",
    source_app_strategy="write_if_missing"
)
```

## Cas d'usage typiques

### Première importation (mode normal)
```python
# Première fois - on veut préserver mais éviter doublons
args = build_exiftool_args(meta, append_only=True)
```

### Nettoyage/réorganisation 
```python
# On veut tout nettoyer et réécrire proprement
args = build_exiftool_args(meta, append_only=False)
```

### Reprise après interruption
```python
# Mode super safe - ne toucher qu'aux métadonnées manquantes
args = build_exiftool_args(
    meta,
    description_strategy="write_if_missing",
    people_keywords_strategy="write_if_missing",
    rating_strategy="write_if_missing",
    source_app_strategy="write_if_missing"
)
```

### Mise à jour sélective
```python
# Mettre à jour uniquement les personnes, préserver le reste
args = build_exiftool_args(
    meta,
    description_strategy="preserve_existing",    # Garder description
    people_keywords_strategy="replace_all",      # Refaire personnes
    rating_strategy="preserve_existing",         # Garder rating
    source_app_strategy="preserve_existing"      # Garder source
)
```

Cette approche est beaucoup plus flexible et claire que les "modes" rigides !

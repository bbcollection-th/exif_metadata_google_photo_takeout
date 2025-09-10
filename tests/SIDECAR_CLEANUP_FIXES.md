# Correction de la terminologie obsolète dans les tests de suppression des sidecars

## Problèmes identifiés et corrigés

### 1. Terminologie obsolète `clean_sidecars` → `immediate_delete`

**Fichiers corrigés :**
- `tests/test_processor_batch.py` (✅ déjà corrigé)
- `tests/test_improvements.py` (✅ corrigé maintenant)

**Changements effectués dans `test_improvements.py` :**

1. **`test_batch_sidecar_cleanup_with_real_failure`** :
   ```python
   # AVANT
   result = process_batch(batch, clean_sidecars=True)
   
   # APRÈS  
   result = process_batch(batch, immediate_delete=True)
   ```

2. **`test_batch_sidecar_cleanup_with_condition_success`** :
   ```python
   # AVANT
   process_sidecar_file(json_path, append_only=True, clean_sidecars=True)
   
   # APRÈS
   process_sidecar_file(json_path, append_only=True, immediate_delete=True)
   ```

3. **`test_batch_cleanup_logic_unit`** :
   ```python
   # AVANT
   result = process_batch(batch, clean_sidecars=True)
   
   # APRÈS
   result = process_batch(batch, immediate_delete=True)
   ```

### 2. Logique `'files failed condition'` toujours valide ✅

**Vérification :** La logique `'files failed condition'` est toujours d'actualité et correctement implémentée dans :
- `src/google_takeout_metadata/exif_writer.py` (lignes 421-423)
- `src/google_takeout_metadata/processor_batch.py` (ligne 118)

**Comportement correct :** En mode append-only, quand exiftool retourne "files failed condition", c'est normal (métadonnées existantes) et le sidecar peut être supprimé en toute sécurité.

### 3. Signatures de fonctions mises à jour ✅

**Vérification des signatures actuelles :**
```python
# process_batch utilise bien immediate_delete
def process_batch(batch: List[Tuple[Path, Path, List[str]]], immediate_delete: bool) -> int

# process_sidecar_file utilise bien immediate_delete  
def process_sidecar_file(json_path: Path, use_localtime: bool = False, 
                        append_only: bool = True, immediate_delete: bool = False) -> None
```

### 4. Tests validés ✅

- ✅ **16 tests unitaires** dans `test_improvements.py` passent
- ✅ **Logique de suppression des sidecars** cohérente avec l'implémentation
- ✅ **Terminologie unifiée** dans tout le codebase

## Impact

Ces corrections assurent que :
1. **Cohérence terminologique** : Plus de confusion entre `clean_sidecars` et `immediate_delete`
2. **Tests à jour** : Les tests reflètent l'API actuelle
3. **Logique préservée** : Le comportement `'files failed condition'` reste correct
4. **Maintenance facilitée** : Plus de paramètres obsolètes dans les tests

## Fichiers déplacés vers tests/

Les fichiers de test créés précédemment ont été déplacés dans le bon répertoire :
- `test_wm_cg_fix.py` → `tests/test_wm_cg_fix.py`
- `test_p1_specific.py` → `tests/test_p1_specific.py`  
- `test_sidecar_integration.py` → `tests/test_sidecar_integration.py`

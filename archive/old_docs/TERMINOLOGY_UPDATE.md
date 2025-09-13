# Mise à jour de la terminologie du codebase

## Changements effectués

### Terminologie unifiée (cohérente avec exif_writer.py) :

1. **"Approche hybride" → "Approche robuste"**
   - Fonction : `test_hybrid_approach_*` → `test_robust_approach_*`
   - Fichiers : `test_hybrid_approach.py` → `test_robust_approach.py`
   - Commentaires : "approche hybride" → "approche robuste (remove-then-add)"

2. **Terminologie technique cohérente :**
   - **"Robuste"** = Stratégie `-TAG-=val` puis `-TAG+=val` (garantit zéro doublon)
   - **"Conditional"** = Stratégie `-if not $TAG=~/regex/i` puis `-TAG+=val` (performance)
   - **"Overwrite"** = Stratégie `-TAG=` puis `-TAG+=val` (écrasement complet)

### Fichiers modifiés :

1. `tests/test_hybrid_approach.py` → `tests/test_robust_approach.py`
2. `tests/CORRECT_test_hybrid_approach.py` → `tests/CORRECT_test_robust_approach.py`  
3. `experiments/test_tony1.py` (commentaire mis à jour)

### Correspondance avec exif_writer.py :

```python
# Alternative "conditional" pour performance  
args.extend(build_conditional_add_args_for_people(meta.people_name))

# Mode overwrite_mode=True
args.extend(build_overwrite_args_for_people(meta.people_name))
```

## Justification

Cette mise à jour assure la cohérence terminologique dans tout le codebase :
- Les tests utilisent maintenant les mêmes termes que l'implémentation
- La documentation reflète les vrais noms de fonctions
- Évite la confusion entre "hybride" (terme ad-hoc) et "robuste" (terme technique établi)

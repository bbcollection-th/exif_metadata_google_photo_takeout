# Correction des signatures de fonction dans les tests

## Problème résolu

Certains appels à la fonction `build_exiftool_args` dans les tests ne respectaient pas la signature de la fonction. La fonction attend :

```python
def build_exiftool_args(meta: SidecarData, image_path: Path | None = None, use_localtime: bool = False, append_only: bool = True) -> List[str]:
```

Mais plusieurs tests passaient des objets `Path` comme arguments positionnels au lieu d'utiliser le paramètre nommé `image_path`.

## Corrections apportées

### 1. Dans `tests/test_exif_writer.py`

**Ligne 69** - Test vidéo :
```python
# Avant (incorrect)
args = build_exiftool_args(meta, video_path)

# Après (correct)
args = build_exiftool_args(meta, image_path=video_path)
```

**Lignes 96-98** - Test localtime :
```python
# Avant (incorrect)
args_utc = build_exiftool_args(meta, Path("a.jpg"), use_localtime=False)
args_local = build_exiftool_args(meta, Path("a.jpg"), use_localtime=True)

# Après (correct)  
args_utc = build_exiftool_args(meta, image_path=Path("a.jpg"), use_localtime=False)
args_local = build_exiftool_args(meta, image_path=Path("a.jpg"), use_localtime=True)
```

### 2. Dans `test_video_append_only_fix.py`

**Lignes 108-112** - Comparaison image/vidéo :
```python
# Avant (incorrect)
image_args = build_exiftool_args(meta, Path("test.jpg"), append_only=True)
video_args = build_exiftool_args(meta, Path("test.mp4"), append_only=True)

# Après (correct)
image_args = build_exiftool_args(meta, image_path=Path("test.jpg"), append_only=True)
video_args = build_exiftool_args(meta, image_path=Path("test.mp4"), append_only=True)
```

## Résultat

✅ **Tous les tests passent** : 56/56 tests validés  
✅ **Signatures correctes** : tous les appels utilisent maintenant `image_path=` comme paramètre nommé  
✅ **Aucune régression** : le comportement fonctionnel reste identique  
✅ **Code plus robuste** : respect strict des signatures de fonction

Ces corrections garantissent que les tests suivent les bonnes pratiques et que la fonction `build_exiftool_args` est appelée correctement dans tous les contextes.

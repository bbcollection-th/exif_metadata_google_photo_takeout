# Plan de refactorisation : Amélioration de la déduplication PersonInImage

## 🎯 Objectif
Implémenter l'approche "supprimer puis ajouter" (`-TAG-=val -TAG+=val`) pour garantir zéro doublon final dans les tags de liste, tout en conservant les performances élevées.

## 📋 Tâches à effectuer

### 1. Modifications du code principal

#### 1.1 Modifier `exif_writer.py` ## 📌 Mini-checklist « commande » de référence

**Commande unique avec nettoyage/dédup (approche robuste) :**
```bash
exiftool \
  -overwrite_original \
  -q -q \
  -codedcharacterset utf8 -charset title=UTF8 -charset iptc=UTF8 -charset exif=UTF8 \
  -XMP-iptcExt:PersonInImage-="Anthony Vincent" -XMP-iptcExt:PersonInImage+="Anthony Vincent" \
  -XMP-iptcExt:PersonInImage-=Bernard        -XMP-iptcExt:PersonInImage+=Bernard        \
  -XMP-iptcExt:PersonInImage-=Jean           -XMP-iptcExt:PersonInImage+=Jean           \
  -XMP-iptcExt:PersonInImage-=Cindy          -XMP-iptcExt:PersonInImage+=Cindy          \
  img.jpg
```

**Variante "ajouter si absent" (tests de performance) :**
```bash
# Ligne de commande avec -common_args correct
exiftool \
  -codedcharacterset utf8 -charset title=UTF8 -charset iptc=UTF8 -charset exif=UTF8 \
  -@ args_conditional.txt \
  -common_args \
  -overwrite_original \
  -q -q

# Contenu args_conditional.txt
-if 'not $XMP-iptcExt:PersonInImage=~/\bAnthony Vincent\b/i'
-XMP-iptcExt:PersonInImage+="Anthony Vincent"
img.jpg
-execute
-if 'not $XMP-iptcExt:PersonInImage=~/\bBernard\b/i'
-XMP-iptcExt:PersonInImage+=Bernard
img.jpg
-execute
```

**En batch (argfile) :** 
- **Ligne de commande :** `charset` options → `-@` argfile → `-common_args` → options communes
- **Argfile :** Uniquement les blocs `options + fichier + -execute`ld_exiftool_args()`
**Localisation :** Lignes ~75-85 (mode append-only pour PersonInImage)

**⚠️ IMPORTANT :** Ne pas utiliser `-wm cg` avec `-TAG-=` (incompatible - suppression = édition)

**Changement :**
```python
# ❌ Code actuel
if meta.people_name:
    for person in meta.people_name:
        args.append(f"-XMP-iptcExt:PersonInImage+={person}")

# ✅ Nouveau code (Option A) - Sans -wm cg pour cette étape
if meta.people_name:
    # Normalisation de casse AVANT écriture (crucial pour déduplication)
    normalized_people_name = [normalize_person_name(person) for person in meta.people_name]
    for person in normalized_people_name:
        args.extend([
            f"-XMP-iptcExt:PersonInImage-={person}",
            f"-XMP-iptcExt:PersonInImage+={person}"
        ])
```

**Nouvelle fonction à ajouter :**
```python
# Éviter .title() brute (problèmes avec McDonald, O'Connor, etc.)
SMALL_WORDS = {"de", "du", "des", "la", "le", "les", "van", "von", "da", "di", "of", "and"}

def normalize_person_name(name: str) -> str:
    """Normaliser les noms de personnes (gestion intelligente de la casse)."""
    if not name: 
        return ""
    
    parts = [p.strip() for p in name.strip().split()]
    fixed = []
    
    for i, p in enumerate(parts):
        low = p.lower()
        # Mots de liaison en minuscules (sauf en début)
        if i > 0 and low in SMALL_WORDS:
            fixed.append(low)
        # Cas spéciaux : O'Connor, McDonald, etc.
        elif low.startswith("o'") and len(p) > 2:
            fixed.append("O'" + p[2:].capitalize())
        elif low.startswith("mc") and len(p) > 2:
            fixed.append("Mc" + p[2:].capitalize())
        else:
            fixed.append(p[:1].upper() + p[1:].lower())
    
    return " ".join(fixed)

def normalize_keyword(keyword: str) -> str:
    """Normaliser les mots-clés (capitalisation simple)."""
    return keyword.strip().capitalize() if keyword else ""
```

**Résultat attendu :** Déduplication garantie des PersonInImage existants avec normalisation de casse

#### 1.2 Modifier les mots-clés (Keywords/Subject)
**Localisation :** Lignes ~80-90 (all_keywords processing)

**⚠️ IMPORTANT :** Normalisation + pas de `-wm cg` avec `-TAG-=`

**Changement :**
```python
# ❌ Code actuel
if all_keywords:
    for keyword in all_keywords:
        args.append(f"-XMP-dc:Subject+={keyword}")
        args.append(f"-IPTC:Keywords+={keyword}")

# ✅ Nouveau code (Option A)
if all_keywords:
    # Normalisation des mots-clés
    normalized_keywords = [normalize_keyword(kw) for kw in all_keywords]
    for keyword in normalized_keywords:
        args.extend([
            f"-XMP-dc:Subject-={keyword}",
            f"-XMP-dc:Subject+={keyword}",
            f"-IPTC:Keywords-={keyword}",
            f"-IPTC:Keywords+={keyword}"
        ])
```

#### 1.3 Conserver `-api NoDups=1` pour le mode batch
**Localisation :** `processor_batch.py` ligne 43

**Action :** GARDER l'option (utile pour déduplication intra-lot)

**Justification :** Complémentaire avec l'approche "supprimer-ajouter"

### 2. Optimisations de performance

#### 2.1 Évaluer l'impact performance
**Tests à effectuer :**
- Mesurer le temps d'exécution avant/après sur un échantillon de 100 fichiers
- Comparer la taille des argfiles générés
- Vérifier l'impact sur les gros lots (>1000 fichiers)

#### 2.2 Implémenter la journalisation `-efile` (CRITIQUE pour gros volumes)
**Localisation :** `processor_batch.py` et `exif_writer.py`

**⚠️ CORRECTION flags -efile :**
> mappage correct :
errors = 1 (ou option sans nombre)
unchanged = 2
failed -if condition = 4
updated = 8
created = 16

**Changement :**
```python
# Ajouter aux commandes exiftool + charset UTF-8 correct
cmd = [
    "exiftool",
    "-charset", "title=UTF8",    # ✅ AVANT -@ (Windows/Unicode, noms de fichiers)
    "-@", argfile_path,
    "-common_args",                 # ✅ APRÈS toutes les options, appliqué à chaque bloc
    "-q", "-q",
    "-overwrite_original",
    "-codedcharacterset", "utf8",   # ✅ Détection UTF-8 par autres logiciels
    "-charset", "iptc=UTF8",        # ✅ Pour écriture IPTC
    "-charset", "exif=UTF8",        # ✅ Pour écriture EXIF
    "-api", "NoDups=1",
    "-efile1", "error_files.txt",
    "-efile2", "unchanged_files.txt",
    "-efile4", "failed_condition_files.txt",
    "-efile8", "updated_files.txt"
]
```

**Structure argfile corrigée :**
```
# Fichier args.txt - NE PAS inclure -common_args ici !

# --- Image 1 ---
-XMP-iptcExt:PersonInImage-="Anthony Vincent"
-XMP-iptcExt:PersonInImage+="Anthony Vincent"
-XMP-iptcExt:PersonInImage-=Bernard
-XMP-iptcExt:PersonInImage+=Bernard
image1.jpg
-execute

# --- Image 2 ---
-XMP-iptcExt:PersonInImage-=Alice
-XMP-iptcExt:PersonInImage+=Alice
image2.jpg
-execute
```

**⚠️ RÈGLES CRUCIALES :**
- **Ordre du bloc :** `options + fichier + -execute` (fichier AVANT -execute)
- **Guillemets obligatoires :** `-TAG-="Anthony Vincent"` (valeurs avec espaces)
- **Pas de -wm cg :** Incompatible avec `-TAG-=` (suppression = édition)
- **-common_args :** JAMAIS dans l'argfile, toujours sur la ligne de commande APRÈS -@
- **-charset title=UTF8 :** AVANT -@ (spécificité Windows/Unicode)

**Fonctionnement :**
- `-execute` exécute le bloc précédent + applique les options `-common_args`
- Les options `-common_args` sont automatiquement ajoutées à chaque bloc exécuté

**Bénéfices :**
- **Reprises intelligentes** : traiter uniquement les "unchanged" + "errors" 
- **Monitoring** : suivi précis des traitements
- **Performance** : gain massif sur ré-exécutions (50Go Takeout)
- **UTF-8** : Support complet accents/emoji

#### 2.3 Logique de reprise automatique avec `-efile`
**Nouveau module :** `resume_handler.py`
```python
def build_resume_batch(error_files: List[Path], unchanged_files: List[Path] = None, resume_mode: str = "errors") -> List[Path]:
    """Construire un lot de reprise à partir des logs -efile."""
    files_to_resume = error_files.copy()  # Toujours reprendre les erreurs
    
    if resume_mode == "all" and unchanged_files:
        files_to_resume.extend(unchanged_files)  # Reprendre aussi les inchangés si policy modifiée
    
    return files_to_resume

def should_resume(output_dir: Path) -> bool:
    """Détecter si des fichiers de log -efile existent."""
    return any(output_dir.glob("*_files.txt"))

def parse_efile_logs(output_dir: Path) -> tuple[List[Path], List[Path], List[Path]]:
    """Parser les logs -efile pour extraire les listes de fichiers."""
    error_files = _read_file_list(output_dir / "error_files.txt")
    updated_files = _read_file_list(output_dir / "updated_files.txt") 
    unchanged_files = _read_file_list(output_dir / "unchanged_files.txt")
    return error_files, updated_files, unchanged_files
```

**Options de reprise recommandées :**
- **Par défaut** : `--resume=errors` (rejouer uniquement les erreurs)
- **Policy modifiée** : `--resume=all` (rejouer errors + unchanged)

#### 2.4 Optimisation conditionnelle - Approche "ajouter si absent"
**Approche hybride pour tests de performance :**
```python
# Option B : "ajouter si absent" (économise écritures en relance)
# Utile pour comparaisons de performance
def build_conditional_args(people: List[str]) -> List[str]:
    """Construire args conditionnels -if + regex pour tests de perf."""
    args = []
    for person in people:
        # Échappement des caractères spéciaux pour regex
        escaped_person = re.escape(person)
        args.extend([
            f"-if", f"not $XMP-iptcExt:PersonInImage=~/\\b{escaped_person}\\b/i",
            f"-XMP-iptcExt:PersonInImage+={person}"
        ])
    return args
```

**Usage recommandé :**
- **Premier traitement** : Approche robuste `-=/+=` (nettoyage complet)
- **Relances/tests perf** : Approche conditionnelle (évite écritures inutiles)

### 3. Nettoyage et cohérence

#### 3.1 Stratégie `-wm` différenciée
**CRUCIAL :** Séparer les modes selon les opérations

**Actions :**
- **Mode nettoyage** (avec `-TAG-=`) : Pas de `-wm cg` (mode write par défaut)
- **Mode append-only pur** : Conserver `-wm cg` pour tags scalaires (description, GPS, etc.)

#### 3.2 Supprimer l'ancienne logique `-api NoDups=1` redondante
**Localisation :** `exif_writer.py` - rechercher les occurrences inutiles

**Action :** Nettoyer les références devenues obsolètes dans le mode simple (garder en batch)

#### 3.3 Documentation du code
**Actions :**
- Commenter pourquoi l'approche `-=/+=` est utilisée
- Référencer le document `astuces.md` dans les commentaires
- Expliquer la différence avec l'approche précédente
- Documenter la normalisation de casse obligatoire

### 4. Tests à développer/modifier

#### 4.1 Test de déduplication robuste
**Nouveau test :** `test_remove_then_add_deduplication()`
```python
def test_remove_then_add_deduplication(tmp_path: Path) -> None:
    """Tester que l'approche -=/+= élimine les doublons pré-existants."""
    # 1. Créer une image avec doublons pré-existants
    # 2. Ajouter manuellement "Anthony Vincent, anthony vincent" 
    # 3. Traiter avec sidecar contenant "Anthony Vincent"
    # 4. Vérifier qu'il n'y a qu'une seule occurrence finale
```

#### 4.2 Test de performance avec `-efile`
**Nouveau test :** `test_performance_with_efile_logging()`
```python
def test_performance_with_efile_logging(tmp_path: Path) -> None:
    """Tester la performance avec journalisation -efile."""
    # 1. Premier traitement avec génération des logs
    # 2. Deuxième traitement en mode reprise (unchanged + errors)
    # 3. Mesurer le gain de performance
```

#### 4.3 Test de reprise automatique
**Nouveau test :** `test_resume_from_efile_logs()`
```python
def test_resume_from_efile_logs(tmp_path: Path) -> None:
    """Tester la reprise automatique depuis les logs -efile."""
    # 1. Traitement partiel avec interruption simulée
    # 2. Détection automatique des logs
    # 3. Reprise sur unchanged + errors uniquement
    # 4. Vérification de la cohérence finale
```

#### 4.3 Tests d'idempotence renforcés
**Modifier :** Tests existants pour vérifier que les ré-exécutions multiples donnent le même résultat

#### 4.4 Test de cas limites - Normalisation de casse
**Nouveau test :** `test_case_normalization_deduplication()`
```python
def test_case_normalization_deduplication(tmp_path: Path) -> None:
    """Tester la normalisation de casse en amont (pas matching insensible)."""
    # 1. Parser sidecar avec ["anthony vincent","CINDY","Bob"]
    # 2. Vérifier normalisation en "Anthony Vincent","Cindy","Bob"
    # 3. Écrire et vérifier que seules les versions normalisées sont présentes
    # ⚠️ NE PAS tester l'ordre (bag XMP), tester l'ensemble des valeurs
```

**⚠️ IMPORTANT pour tous les tests de listes :**
```python
# ❌ Incorrect - teste l'ordre (non garanti pour les bags XMP)
assert metadata["PersonInImage"] == ["Alice", "Bob", "Charlie"]

# ✅ Correct - teste l'ensemble des valeurs
people = set(metadata.get("PersonInImage", []))
expected = {"Alice", "Bob", "Charlie"}
assert people == expected
```

### 5. Tests de régression

#### 5.1 Tests d'intégration existants
**Actions :**
- Exécuter `test_integration.py` complet
- Vérifier `test_end_to_end.py`
- Valider `test_processor_batch.py`

#### 5.2 Tests sur assets réels
**Actions :**
- Tester sur les échantillons dans `Google Photos/`
- Vérifier le comportement sur fichiers avec métadonnées complexes

#### 5.3 Tests de performance batch
**Actions :**
- Mesurer l'impact sur `process_directory_batch()`
- Comparer les temps d'exécution sur différentes tailles de lots

### 6. Validation et documentation

#### 6.1 Mise à jour de la documentation
**Fichiers à modifier :**
- `README.md` : Mentionner l'amélioration de déduplication
- `astuces.md` : Ajouter une section sur l'implémentation choisie

#### 6.2 Tests de validation finale
**Checklist :**
- [ ] Aucun doublon dans PersonInImage après traitement
- [ ] Performance acceptable (max +20% de temps d'exécution)
- [ ] Tous les tests existants passent
- [ ] Idempotence parfaite (ré-exécutions identiques)
- [ ] Compatibilité avec mode batch et mode simple

### 7. Plan de déploiement

#### 7.1 Étapes de développement
1. **Phase 1 :** Modifier `build_exiftool_args()` pour PersonInImage uniquement
2. **Phase 2 :** Implémenter la journalisation `-efile` et logique de reprise
3. **Phase 3 :** Étendre aux Keywords/Subject si Phase 1 réussie
4. **Phase 4 :** Optimisations de performance avancées si nécessaire

#### 7.2 Tests de validation
1. **Tests unitaires :** Validation de la logique de base
2. **Tests d'intégration :** Validation sur cas réels
3. **Tests de performance :** Validation des seuils acceptables

#### 7.3 Critères de succès
- ✅ Zéro doublon dans PersonInImage après traitement
- ✅ Performance dégradée de moins de 20%
- ✅ Tous les tests existants passent
- ✅ Comportement idempotent garanti

## 🚨 Risques identifiés et mitigations

### Risque 1 : Dégradation de performance
**Mitigation :** Tests de performance systématiques et seuils acceptables définis

### Risque 2 : Régression fonctionnelle
**Mitigation :** Tests de régression complets avant merge

### Risque 3 : Complexité de debug
**Mitigation :** Logs détaillés et documentation claire

### Risque 4 : ⚠️ **NOUVEAU** - Incompatibilité `-wm cg` / `-TAG-=`
**Risque :** Suppressions non effectuées si `-wm cg` actif
**Mitigation :** Stratégie `-wm` différenciée selon les opérations

### Risque 5 : ⚠️ **NOUVEAU** - Normalisation de casse insuffisante
**Risque :** `"Cindy"` et `"cindy"` coexistent (suppression littérale)
**Mitigation :** Normalisation obligatoire en amont dans le parser

## � Mini-checklist « commande » de référence

**Commande unique avec nettoyage/dédup :**
```bash
exiftool \
  -overwrite_original \
  -codedcharacterset utf8 -charset title=UTF8 -charset iptc=UTF8 -charset exif=UTF8 \
  -XMP-iptcExt:PersonInImage-="Anthony Vincent" -XMP-iptcExt:PersonInImage+="Anthony Vincent" \
  -XMP-iptcExt:PersonInImage-=Bernard        -XMP-iptcExt:PersonInImage+=Bernard        \
  -XMP-iptcExt:PersonInImage-=Jean           -XMP-iptcExt:PersonInImage+=Jean           \
  -XMP-iptcExt:PersonInImage-=Cindy          -XMP-iptcExt:PersonInImage+=Cindy          \
  img.jpg
```

**En batch (argfile) :** un bloc par image, séparé par `-execute`, et facteurs communs via `-common_args`

## �📊 Métriques de réussite

1. **Qualité :** 0 doublon dans PersonInImage sur 100 fichiers tests
2. **Performance :** 
   - Temps d'exécution +20% maximum sur traitement initial
   - Gain de 80%+ sur reprises grâce à `-efile` (fichiers unchanged skippés)
3. **Robustesse :** 100% des tests existants passent
4. **Idempotence :** Résultats identiques sur 3 ré-exécutions consécutives
5. **Reprise :** Détection et reprise automatique des traitements interrompus

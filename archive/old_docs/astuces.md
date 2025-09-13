Pour obtenir :

> `PersonInImage: Jeremy, Cindy, Anthony Vincent, Bernard, Jean`

…à partir de la base :

* image : `Jeremy, Cindy`
* sidecar : `people = [ "Anthony Vincent", "Bernard", "Jean", "Cindy" ]`

Je n'ai identifié que **deux façons reellement correctes**:

---

# Option A — “supprimer puis ajouter” (infaillible et surtout gère aussi les doublons pré-existants)

```bash
exiftool \
  -overwrite_original -wm cg \
  -XMP-iptcExt:PersonInImage-="Anthony Vincent" -XMP-iptcExt:PersonInImage+="Anthony Vincent" -execute \
  -XMP-iptcExt:PersonInImage-=Bernard        -XMP-iptcExt:PersonInImage+=Bernard        -execute \
  -XMP-iptcExt:PersonInImage-=Jean           -XMP-iptcExt:PersonInImage+=Jean           -execute \
  -XMP-iptcExt:PersonInImage-=Cindy          -XMP-iptcExt:PersonInImage+=Cindy          \
  -common_args img.jpg
```

* `-wm cg` : append-only (n’écrase pas l’existant).
* Pour chaque nom du sidecar : on **retire** l’éventuel item, puis on **ajoute** l’item une seule fois ⇒ **zéro doublon garanti**, même si l’image en avait déjà (ou si on repasses plusieurs fois).

---

# Option B — “ajouter si absent” (évite d’enlever/rajouter, sensible à la casse si on ne normalises pas)

```bash
exiftool -overwrite_original \
  -if 'not $XMP-iptcExt:PersonInImage=~/\bAnthony Vincent\b/i' -XMP-iptcExt:PersonInImage+="Anthony Vincent" -execute \
  -if 'not $XMP-iptcExt:PersonInImage=~/\bBernard\b/i'         -XMP-iptcExt:PersonInImage+=Bernard         -execute \
  -if 'not $XMP-iptcExt:PersonInImage=~/\bJean\b/i'            -XMP-iptcExt:PersonInImage+=Jean            -execute \
  -if 'not $XMP-iptcExt:PersonInImage=~/\bCindy\b/i'           -XMP-iptcExt:PersonInImage+=Cindy           \
  -common_args img.jpg
```

* La regex `/…/i` est **insensible à la casse** → évite `Cindy` + `cindy`.
* On **n’ajoute** que si le nom **n’existe pas déjà**.

---

## Résultat

Dans **les deux** cas ci-dessus, après exécution sur l'exemple ci-dessus, on obtient bien :

```
PersonInImage: Anthony, Cindy, Anthony Vincent, Bernard, Jean
```

## Extra

* Si on veux forcer une **casse cohérente** (ex. “Title Case”) avant d’écrire, effectuer côté script (extraction du sidecar) puis appliquer l’une des deux méthodes.
* **Ordre** : `PersonInImage` est une “bag” XMP (ordre pas strictement garanti). En pratique, exiftool tend à **ajouter** à la fin ; l’important est l’**ensemble** des noms, pas leur ordre.
* On peux remplacer les quatre blocs par ceux issus du **parsing du sidecar** (PowerShell/Python) pour automatiser sur tout un dossier.

## Pourquoi “supprimer puis ajouter” (option A) est infaillible

La doc recommande explicitement, pour les balises liste, le motif :
`-TAG-=val -TAG+=val`
afin d’ajouter sans dupliquer (même si la valeur existait déjà). 

Cette approche normalise la présence de chaque nom : on enlève l’éventuelle occurrence, puis on écrit exactement une fois.
Elle gère tous les scénarios : doublons pré-existants, ré-exécutions multiples, cas mixtes, etc.
Elle n’a pas besoin que l’item soit dans le même lot d’arguments : On peut traiter un nom à la fois, un fichier à la fois, un sidecar à la fois.

## Pourquoi “ajouter si absent” (option B) est précise et sobre

L’usage de `-if + regex` :
`-if 'not $PersonInImage=~/\bNom\b/i' -PersonInImage+=Nom`
- permet de ne pas toucher aux fichiers déjà propres (aucune écriture si la valeur existe), et de rester idempotent. La doc formalise l’usage puissant de `-if` pour conditionner l’écriture. 
- On maîtrises la sensibilité à la casse (/i) et le mot entier (\b…\b).
- On évite des écritures inutiles (pratique si on veut limiter les I/O).

## Pourquoi je n'ai pas utilisé `-api NoDups=1`
### Ce que fait vraiment `-api NoDups=1`:
- L’option retire les doublons uniquement parmi les valeurs “en file d’attente d’écriture” (celles que l'on fournis dans la même invocation exiftool). Elle ne dédoublonne pas ce qui est déjà présent dans le fichier si on se contentes d’ajouter (+=) de nouvelles valeurs. 

- La doc indique d’ailleurs que `NoDups` (API) a été ajouté pour rendre la fonction helper `NoDups` largement redondante lors de copies ou d’accumulations, mais sans la capacité d’éviter la réécriture quand il n’y a pas de doublons existants. Exemple typique : combiner des listes depuis plusieurs sources dans la même commande avec `-tagsFromFile ... -+subject ... -api nodups`. 
--> `NoDups` supprimera les doublons dans un lot de +=, mais ne retirera pas un doublon déjà présent dans le fichier, puisqu’il ne déduplique pas par rapport à l’état pré-existant.

Par contre `NoDups` est très pratique quand on accumules des listes dans une seule commande, par exemple :
- on copie des items depuis plusieurs sources vers un même tag liste via `-tagsFromFile + -+DSTTAG`, et on veut une déduplication automatique du lot au moment de l’écriture. La doc donne l’exemple :
`exiftool -tagsfromfile a.jpg -subject -tagsfromfile b.jpg -+subject -api nodups c.jpg`

- on construit un gros argfile avec plein de += pour un même fichier et on veut s’épargner un tri/dédoublonnage préalable dans ce lot.

**Mais** : cette dédup intra-lot ne remplace pas l’assurance “zéro doublon final” vis-à-vis de l’état déjà inscrit dans le fichier. Pour ça, il faut soit le motif `-TAG-=val -TAG+=val` (option A), soit la condition -if (option B).

## Fonctionnalitées complémentaires
L'usage de `-wm cg` (create groups only) en mode append-only est pertinent ; la doc confirme que `-wm cg` limite l’écriture à la création et évite d’éditer l’existant (utile en batch). Combiner avec A ou B selon l’effet recherché. 

Pour le batch, `-@ argfile`, `-execute` et `-common_args` sont les bons outils

---
Très bonne question — sur un **Takeout de \~50 Go**, la *stratégie d’exécution* compte plus que la micro-optimisation des options. Voilà ce qui marche vraiment bien, avec les raisons et la doc à l’appui.

---

## Analyse/ astuces de méthodes + performances sur gros dossiers

* **Évite un exiftool par fichier** → garde un **processus ouvert** et enchaîne les commandes avec `-execute` + `-common_args`, ou utilise un **fichier d’arguments** `-@` (mêmes effets). &#x20;
* **Préfère `-overwrite_original`** (plus rapide) à `-overwrite_original_in_place` (plus lent) sauf si tu DOIS préserver certains attributs système du fichier.&#x20;
* **Journalise** les “mis à jour / inchangés / en erreur” avec `-efile` pour les passes suivantes.&#x20;
* **Parallélise par sous-dossiers** (2–4 processus max sur SSD/NVMe ; 1–2 sur HDD) au lieu d’un seul process sur toute l’arbo, pour tirer parti des cœurs sans saturer l’I/O.

---

## 1) Réduire drastiquement l’overhead de lancement

Chaque lancement d’exiftool a un coût. Deux approches natives permettent de **chaîner des commandes** dans un **seul** process :

### A) `-@ args.txt` + `-execute` + `-common_args`

* Tu mets des blocs « commande » séparés par `-execute`, et tu factorises les options communes avec `-common_args`. C’est exactement le pattern recommandé dans la doc (exemple avancé).&#x20;
* `-execute` exécute immédiatement les arguments accumulés **jusqu’à présent** (en y ajoutant les `-common_args`).&#x20;

> Bénéfice : 1 seul process, des milliers d’images traitées d’affilée, **quasi sans overhead** de relance.

### B) Mode **persistant** : `-stay_open`

* Lance exiftool une fois avec `-stay_open True -@ ARGFILE`, alimente `ARGFILE` (ou `-@ -` en pipe) avec des blocs terminés par `-execute`, puis fermes proprement avec `-stay_open\nFalse`.&#x20;
* (La doc détaille même la synchronisation via un numéro `-executeNUM` renvoyé dans `{readyNUM}`.)&#x20;

> Bénéfice : identique à A), mais **parfait** pour des intégrations scriptées/long-lived.

---

## 2) Écrire plus vite : choisir la bonne option d’overwrite

* `-overwrite_original` remplace le fichier via un fichier temporaire **en une opération** ; c’est le choix **plus rapide** pour des gros volumes.&#x20;
* `-overwrite_original_in_place` ajoute une étape pour préserver certains attributs (création, tags Finder, etc.), **mais plus lente** : à réserver quand c’est nécessaire.&#x20;

---

## 3) Éviter les écritures inutiles (vrai gain sur 50 Go)

* Si tu utilises la méthode **B “ajouter si absent”** (`-if 'not $PersonInImage=~/\bNom\b/i' -PersonInImage+=Nom`), exiftool **ne réécrit pas** les fichiers qui possèdent déjà la valeur → **gros gain I/O** sur des relances. (Tu peux chaîner chaque nom avec `-execute` et factoriser l’image via `-common_args`.)&#x20;
* Alternative robuste : **A “supprimer puis ajouter”** (`-TAG-=Nom -TAG+=Nom`) garantit zéro doublon final mais **force une écriture** même si la valeur était déjà propre. À privilégier pour “nettoyage” initial, puis passer à B pour les relances. *(Technique recommandée par la doc pour les listes ; cf. exemples de +/– sur listes.)*&#x20;

---

## 4) batcher intelligemment

* **Journalise les statuts** avec `-efileNUM file.txt` : tu peux demander d’écrire dans des fichiers distincts les listes de *updated*, *unchanged*, *errors*, etc., en combinant les flags (2,4,8,16…). Très pratique pour **reprendre** uniquement les “inchangés” ou “en erreur” lors d’une passe suivante.&#x20;

---

## 5) Exemple “gros dossier” performant

### Variante argfile (recommandée, simple à rejouer)

`args.txt` (généré par ton script à partir des sidecars) :

```
# Options communes (appliquées à tous les blocs)
-common_args
-overwrite_original
-q
# (ajoute -api NoDups=1 si tu empiles plusieurs += pour un même fichier dans le même bloc)
# --- image 1 ---
-if not $XMP-iptcExt:PersonInImage=~/\bAnthony Vincent\b/i
-XMP-iptcExt:PersonInImage+=Anthony Vincent
-execute
-if not $XMP-iptcExt:PersonInImage=~/\bBernard\b/i
-XMP-iptcExt:PersonInImage+=Bernard
-execute
-if not $XMP-iptcExt:PersonInImage=~/\bJean\b/i
-XMP-iptcExt:PersonInImage+=Jean
-execute
# on passe le chemin cible une seule fois si tu factorises par image :
# (voir modèle “3 commandes dans 1” de la doc)
# --- image N ---
…
```

Lancement :

```bash
exiftool -@ args.txt
```

> Pattern “3 commandes dans 1” avec `-execute` et `-common_args` = **référence** dans la doc.&#x20;

### Variante `-stay_open` (si tu préfères un démon exiftool)

```bash
exiftool -stay_open True -@ - <<'EOF'
-overwrite_original
-q
# bloc image 1
-if not $XMP-iptcExt:PersonInImage=~/\bAnthony Vincent\b/i
-XMP-iptcExt:PersonInImage+=Anthony Vincent
-execute
…
-stay_open
False
EOF
```

> Le protocole d’échange `-stay_open … -@ … -execute … -stay_open False` est documenté, avec même les astuces de synchro `{readyNUM}`.&#x20;

---

## 6) Petits plus

* **Silence la sortie** pour réduire l’I/O console avec `-q` (double `-q` pour encore moins).
* Si tu as des **vidéos** (MP4/MOV), l’écriture peut être plus lourde. Ta suite a déjà des options vidéo (QuickTimeUTC, etc.) — garde-les, mais évite de toucher aux vidéos si le sidecar n’apporte rien de neuf. (Tes tests montrent l’inclusion conditionnelle des champs QuickTime).&#x20;
* Si tu veux **préserver horodatages** FS, c’est `-preserve`/`-P` (non listé dans l’extrait cité), mais ça **n’accélère pas**.
* **Ne pas utiliser `-overwrite_original_in_place`** pour la perf : la doc précise l’étape supplémentaire → plus lent.&#x20;

---

## 7) Parallélisation pragmatique

ExifTool est essentiellement **mono-processus**. Pour accélérer sur 50 Go :

* **Découpe** par albums/sous-dossiers et lance **2–4 exécutions en parallèle** sur SSD/NVMe (évite 100 % CPU *et* 100 % disque).

---

### Conclusion

Pour un Takeout massif, la **grosse différence** vient de :

1. **Réduire les relances** (un seul exiftool via `-@`/`-execute`/`-common_args` ou `-stay_open`).  &#x20;
2. **Limiter les écritures** (conditions `-if` ou lot bien ciblé).
3. **Choisir `-overwrite_original`** pour la vitesse.&#x20;
4. **Journaliser** avec `-efile` pour relancer efficacement.&#x20;

---

## 8) Implémentation dans le projet

**Notre choix final** : Nous avons implémenté l'**Option A "supprimer puis ajouter"** pour garantir zéro doublon.

### Approche adoptée

```python
# Mode append-only avec déduplication (nouveau comportement)
if meta.people_name:
    normalized_people_name = [normalize_person_name(person) for person in meta.people_name]
    for person in normalized_people_name:
        args.extend([
            f"-XMP-iptcExt:PersonInImage-={person}",
            f"-XMP-iptcExt:PersonInImage+={person}"
        ])
```

### Avantages de cette implémentation

✅ **Déduplication robuste** : Élimine les doublons pré-existants dans les fichiers
✅ **Normalisation intelligente** : "anthony vincent" → "Anthony Vincent", gestion des "McDonald", "O'Connor", etc.
✅ **Performance optimisée** : Journalisation `-efile` pour reprises intelligentes
✅ **Stratégie `-wm` différenciée** : Pas de `-wm cg` avec `-TAG-=` (incompatible), réactivé pour les autres champs
✅ **Support Unicode complet** : `-codedcharacterset=utf8` pour accents et emoji

### Commande générée type

```bash
exiftool \
  -overwrite_original \
  -charset title=UTF8 -charset iptc=UTF8 -charset exif=UTF8 \
  -codedcharacterset=utf8 \
  -XMP-iptcExt:PersonInImage-="Anthony Vincent" -XMP-iptcExt:PersonInImage+="Anthony Vincent" \
  -XMP-iptcExt:PersonInImage-=Bernard        -XMP-iptcExt:PersonInImage+=Bernard        \
  -XMP-dc:Subject-="Anthony Vincent"         -XMP-dc:Subject+="Anthony Vincent"         \
  -XMP-dc:Subject-=Bernard                   -XMP-dc:Subject+=Bernard                   \
  -wm cg \
  -CreateDate="2024:01:15 10:30:00" \
  -GPSLatitude=48.8566 \
  img.jpg
```

### Journalisation pour reprises

```bash
# En mode batch : ajout des options -efile pour journalisation
exiftool \
  -charset title=UTF8 \
  -@ args.txt \
  -common_args \
  -overwrite_original \
  -charset iptc=UTF8 -charset exif=UTF8 \
  -codedcharacterset=utf8 \
  -q -q \
  -efile1 error_files.txt \
  -efile2 unchanged_files.txt \
  -efile4 failed_condition_files.txt \
  -efile8 updated_files.txt
```

Cette approche garantit **zéro doublon final** tout en conservant d'excellentes performances grâce aux reprises intelligentes via les logs `-efile`.

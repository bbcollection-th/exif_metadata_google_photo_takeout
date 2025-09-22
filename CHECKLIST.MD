# ✅ Checklist complète

## 1. Installation & environnement

* [X] Vérifier que tu utilises la **dernière version d’ExifTool** ([site officiel](https://exiftool.org/)) — certaines corrections GPS/QuickTime sont récentes.
* [X] Sur Windows : renommer `exiftool(-k).exe` en `exiftool.exe` pour une utilisation en ligne de commande.
* [X] S’assurer que le binaire est dans le **PATH**, ou utiliser un chemin absolu.
* [X] Ajouter `-charset filename=utf8 -charset iptc=UTF8 -charset exif=UTF8` dans les `common_args`.

---

## 2. Sauvegardes et écrasement

* [ ] Décider si tu veux conserver les fichiers `_original` :

  * Sauvegardes ON → ne pas utiliser `-overwrite_original`.
  * Sauvegardes OFF → utiliser `-overwrite_original` et `backup_original=false`.
* [ ] Vérifier cohérence entre `backup_original=true` et `-overwrite_original` (contradiction actuelle à corriger).

---

## 3. Champs texte (title, description, keywords)

* [ ] **Title** : bon choix (`IPTC:ObjectName`, `XMP-dc:Title`) → garder.
* [ ] **Description** : bon choix (`MWG:Description` + `XMP-dc:Description`).
* [ ] Vérifier que les écritures **lang-alt** sont bien en `x-default`.
* [ ] **Keywords/Subjects** : déduplication active ✅ ; envisager aussi `XMP-lr:HierarchicalSubject` si tu veux des hiérarchies (`People|Nom` ou `Albums|Nom`).

---

## 4. Dates & heures

* [ ] **Images** :

  * `EXIF:DateTimeOriginal` (moment de prise de vue) ✅
  * `EXIF:CreateDate` ✅
  * Ajouter `OffsetTimeOriginal` si tu connais le fuseau horaire.
* [ ] **Vidéos QuickTime** :

  * Ajouter `-api QuickTimeUTC=1` pour forcer l’écriture UTC.
  * Remplir **plusieurs champs** pour compat maximale :

    * `QuickTime:CreateDate`
    * `QuickTime:ModifyDate`
    * `TrackCreateDate` / `TrackModifyDate`
    * `MediaCreateDate` / `MediaModifyDate`
  * Garder `XMP-photoshop:DateCreated` et `XMP-xmp:CreateDate`.

---

## 5. GPS

* [ ] Écrire en **décimal signé** avec `-n`.
* [ ] Assurer la création de :

  * `GPSLatitude`, `GPSLongitude`
  * `GPSLatitudeRef`, `GPSLongitudeRef` (gérés auto si signé)
  * `GPSAltitude` **+** `GPSAltitudeRef` (0 = au-dessus mer, 1 = en dessous).
* [ ] Pour vidéos : `XMP-exif:*` est correct ; en bonus : `Keys:LocationISO6709` pour compatibilité iOS/Apple.

---

## 6. Personnes et albums

* [ ] `XMP-iptcExt:PersonInImage` + `Keywords/Subject` : ✅ bon choix.
* [ ] Normaliser les noms (`Prénom Nom`) pour cohérence.
* [ ] Ajouter hiérarchies optionnelles : `XMP-lr:HierarchicalSubject` (ex. `People|Nom` et `Albums|Nom`).
* [ ] Albums : ton prefix “Album: …” est une bonne pratique (évite mélange avec vrais mots-clés).

---

## 7. LocalFolderName

* [ ] ⚠️ Ne pas utiliser `EXIF:Software` (réservé au logiciel de capture).
* [ ] Utiliser à la place :

  * `XMP-xmp:CreatorTool` (images et vidéos)
  * ou transformer en `Subject/Keyword` si c’est juste organisationnel.

---

## 8. Favoris / Rating

* [ ] Bon mapping (`favorited=true → Rating=5`).
* [ ] Vérifier que tu utilises bien `XMP-xmp:Rating` (alias `XMP:Rating`).
* [ ] Optionnel : ajouter `XMP:Label=Favorite` pour compat avec Bridge/Windows.

---

## 9. Stratégies d’écriture

* [ ] Garder `write_if_blank_or_missing` pour éviter d’écraser du texte existant.
* [ ] `replace_all` → OK pour GPS, dates si Takeout est vérité absolue.
* [ ] `clean_duplicates` → OK pour Keywords, People, Albums.
* [ ] ⚠️ Attention à `preserve_existing` avec `-wm` : peut bloquer certaines écritures → mieux piloter tag par tag (tu le fais déjà).
* [ ] Vérifier que les conditions sont bien testées (`-if` correct).

---

## 10. Vérifications & contrôle qualité

* [ ] **Avant traitement** : tester sur un petit lot :

  ```bash
  exiftool -r -warning -s -G1 dossier/
  ```

  pour voir warnings et tags.
* [ ] **Après traitement** : vérifier cohérence :

  * Dates cohérentes (`DateTimeOriginal` = moment réel, UTC correct pour vidéos).
  * GPS lisible dans ton viewer (Google Photos, LR, Windows).
  * Titres/descriptions affichés correctement.
* [ ] Supprimer les warnings récurrents (`Unknown IFD0`, `Non-standard format GPS`, etc.).
* [ ] Sauvegarder la config `.json` + un export `-args` pour rejouer si besoin :

  ```bash
  exiftool -args -G1 fichier.jpg > sauvegarde.args
  ```

---

## 11. Automatisation

* [ ] Utiliser `-efile logs/errors.txt` pour loguer les erreurs.
* [ ] Script batch/PowerShell → glisser-déposer un dossier pour traitement.
* [ ] Documenter : quelles métadonnées viennent de Takeout, lesquelles sont recalculées/normalisées.

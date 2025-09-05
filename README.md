# exif_metadata_google_photo_takeout

Ce projet permet d'incorporer les métadonnées des fichiers JSON produits par Google Takeout dans les photos correspondantes.

## Utilisation

```
python -m google_takeout_metadata.cli /chemin/vers/le/dossier
```

Le programme parcourt récursivement le dossier, cherche les fichiers `*.json` et écrit les informations pertinentes dans les fichiers image correspondants à l'aide d'`exiftool`.

## Tests

```
pytest
```

Les tests comprennent des tests unitaires et un test de bout en bout qui vérifie l'écriture effective des métadonnées.

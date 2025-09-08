# Résultats Test 1: Lecture avec option -a

## Test effectué
Tester la différence entre lecture avec et sans `-a` pour comprendre les doublons.

## Résultats

### Étape 1: Ajout initial
```bash
exiftool -XMP-iptcExt:PersonInImage=Anthony -XMP-iptcExt:PersonInImage+=Bernard -XMP-dc:Subject=Anthony -XMP-dc:Subject+=Bernard -XMP-dc:Subject+=Album: Vacances
```

### Étape 2: Lecture SANS -a
```
Anthony, Bernard
Anthony, Bernard, Album: Vacances
```

### Étape 3: Lecture AVEC -a  
```
Anthony, Bernard
Anthony, Bernard, Album: Vacances
```

**📝 Observation**: Pas de différence entre avec et sans `-a` après l'ajout initial.

### Étape 4: Ajout de doublons
```bash
exiftool -XMP-iptcExt:PersonInImage+=Anthony -XMP-iptcExt:PersonInImage+=Cindy -XMP-dc:Subject+=Anthony -XMP-dc:Subject+=Cindy
```

### Étape 5: Lecture finale AVEC -a
```
Anthony, Bernard, Anthony, Cindy
Anthony, Bernard, Album: Vacances, Anthony, Cindy
```

## 🎯 Conclusions

1. **L'option `-a` fonctionne**: Elle montre bien tous les doublons après l'ajout de valeurs dupliquées
2. **Les doublons sont réels**: Anthony apparaît 2 fois dans PersonInImage et Subject
3. **Le problème est confirmé**: L'utilisation de `+=` ajoute même les doublons

## 🔄 Prochaine étape
Tester comment vider complètement un tag avant de le remplir avec les valeurs dédupliquées.

# Résultats Test 2: Stratégies de remplacement de tags

## Test effectué
Tester différentes méthodes pour remplacer complètement un tag de liste sans doublons.

## État initial
```
PersonInImage: 'Anthony, Bernard, Anthony'
```
(Contient un doublon volontaire)

## Stratégies testées

### Stratégie 1: Vider puis ajouter un par un
```bash
exiftool -XMP-iptcExt:PersonInImage= -XMP-iptcExt:PersonInImage=Anthony -XMP-iptcExt:PersonInImage+=Bernard -XMP-iptcExt:PersonInImage+=Cindy
```
**Résultat**: `Anthony, Bernard, Anthony, Anthony, Bernard, Cindy`

❌ **ÉCHEC**: Vider avec `=` n'efface pas complètement, et les valeurs s'accumulent.

### Stratégie 2: Assignation directe avec liste concaténée
```bash
exiftool -XMP-iptcExt:PersonInImage=Anthony,Bernard,Cindy
```
**Résultat**: `Anthony,Bernard,Cindy`

✅ **SUCCÈS**: Remplace complètement le tag avec la liste exacte.

### Stratégie 3: Assignations multiples directes (=)
```bash
exiftool -XMP-iptcExt:PersonInImage=Anthony -XMP-iptcExt:PersonInImage=Bernard -XMP-iptcExt:PersonInImage=Cindy
```
**Résultat**: `Anthony, Bernard, Cindy`

✅ **SUCCÈS**: Remplace complètement et formate avec des espaces.

## 🎯 Conclusions

1. **Stratégie 2 est la plus efficace**: Une seule assignation avec liste concaténée par virgules
2. **Stratégie 3 fonctionne aussi**: Assignations multiples avec `=` (pas `+=`)
3. **Vider avec `=` suivi de `+=` ne fonctionne pas**: Les anciennes valeurs persistent

## 🔄 Prochaine étape
Implémenter la stratégie 2 dans notre code: lire les valeurs existantes, dédupliquer en Python, puis assigner la liste complète d'un coup.

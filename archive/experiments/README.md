# Expérimentations pour la déduplication en mode append-only

Ce dossier contient les tests expérimentaux pour résoudre le problème de déduplication.

## Problème identifié
En mode append-only, quand on traite une photo qui a déjà des métadonnées (par exemple `["Anthony", "Bernard"]`) et qu'on reçoit un JSON complet avec `["Anthony", "Bernard", "Cindy"]`, on obtient des doublons au lieu d'ajouter seulement `Cindy`.

## Tests à effectuer
1. Test de lecture avec `-a` pour voir tous les tags dupliqués
2. Test d'assignation directe vs +=
3. Test de différentes stratégies de déduplication

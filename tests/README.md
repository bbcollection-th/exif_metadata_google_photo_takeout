# 🧪 Tests et Utilitaires de Debug

Ce dossier contient tous les tests du projet ainsi que des scripts utilitaires de debug.

## 📁 Structure

### Tests Principaux
- `test_*.py` - Tests unitaires et d'intégration du projet
- Ces tests sont exécutés avec `pytest tests/`

### Scripts Utilitaires de Debug
- `debug_*.py` - Scripts de debug et d'analyse
- Ces scripts peuvent être exécutés directement pour diagnostiquer des problèmes

## 🔧 Scripts de Debug Disponibles

### `debug_build_args_detailed.py`
- Analyse détaillée de la génération d'arguments ExifTool
- Utile pour comprendre comment les stratégies génèrent les commandes

### `debug_config_favorited.py`
- Test spécifique de la configuration des favoris (Rating + Label)
- Vérifie que la stratégie `preserve_positive_rating` fonctionne

### `debug_favorited_extraction.py` 
- Debug de l'extraction des champs favorited depuis les JSON
- Valide la logique de mapping value_mapping

## 🚀 Usage

### Exécuter tous les tests
```bash
pytest tests/ -v
```

### Exécuter un test spécifique
```bash
pytest tests/test_integration.py -v
```

### Exécuter un script de debug
```bash
python tests/debug_config_favorited.py
```

## 📊 Types de Tests

- **Tests Unitaires** : Testent des fonctions isolées
- **Tests d'Intégration** : Testent l'interaction entre composants
- **Tests End-to-End** : Testent le workflow complet
- **Scripts de Debug** : Analysent des cas spécifiques

Tous les tests sont conçus pour être reproductibles et ne pas modifier les fichiers de test permanents.
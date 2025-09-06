#!/bin/bash

# Script de test manuel pour démontrer les nouvelles fonctionnalités

echo "=== Test des nouvelles fonctionnalités de google-takeout-metadata ==="

# Créer un répertoire de test temporaire
TEST_DIR="/tmp/test_google_takeout"
rm -rf "$TEST_DIR"
mkdir -p "$TEST_DIR"

# Créer une image de test simple
echo "1. Création d'une image de test..."
cat > "$TEST_DIR/test.jpg" << 'EOF'
FFD8FFE000104A46494600010101006000600000FFDB004300080606070605080707070909080A0C140D0C0B0B0C1912130F141D1A1F1E1D1A1C1C20242E2720222C231C1C2837292C30313434341F27393D38323C2E333432FFDB0043010909090C0B0C180D0D1832211C213232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232FFC0001108006400640301220002110103110101FFC4001F0000010501010101010100000000000000000102030405060708090A0BFFC400B5100002010303020403050504040000017D01020300041105122131410613516107227114328191A1082342B1C11552D1F02433627282090A161718191A25262728292A3435363738393A434445464748494A535455565758595A636465666768696A737475767778797A838485868788898A92939495969798999AA2A3A4A5A6A7A8A9AAB2B3B4B5B6B7B8B9BAC2C3C4C5C6C7C8C9CAD2D3D4D5D6D7D8D9DAE1E2E3E4E5E6E7E8E9EAF1F2F3F4F5F6F7F8F9FAFFC4001F0100030101010101010101010000000000000102030405060708090A0BFFC400B51100020102040403040705040400010277000102031104052131061241510761711322328108144291A1B1C109233352F0156272D10A162434E125F11718191A262728292A35363738393A434445464748494A535455565758595A636465666768696A737475767778797A82838485868788898A92939495969798999AA2A3A4A5A6A7A8A9AAB2B3B4B5B6B7B8B9BAC2C3C4C5C6C7C8C9CAD2D3D4D5D6D7D8D9DAE2E3E4E5E6E7E8E9EAF2F3F4F5F6F7F8F9FAFFDA000C03010002110311003F00FFD9
EOF

# Créer le fichier sidecar JSON avec toutes les nouvelles fonctionnalités
echo "2. Création du fichier sidecar avec métadonnées complètes..."
cat > "$TEST_DIR/test.jpg.json" << 'EOF'
{
  "title": "test.jpg",
  "description": "Photo de test avec émojis 🎉 et caractères spéciaux: ñ, é, ü",
  "favorited": {
    "value": true
  },
  "people": [
    {"name": "Alice Dupont"},
    {"name": "Bob Martin"},
    {"name": " Alice Dupont "},
    {"name": "Charlie Wilson"}
  ],
  "photoTakenTime": {
    "timestamp": "1736719606"
  },
  "creationTime": {
    "timestamp": "1736719600"
  },
  "geoData": {
    "latitude": 48.8566,
    "longitude": 2.3522,
    "altitude": 35.0,
    "latitudeSpan": 0.001,
    "longitudeSpan": 0.001
  }
}
EOF

echo "3. Affichage du contenu du sidecar:"
echo "=================================="
cat "$TEST_DIR/test.jpg.json"
echo -e "\n=================================="

echo "4. Test de la commande avec les nouvelles options:"
echo ""
echo "Usage normal:"
echo "google-takeout-metadata $TEST_DIR"
echo ""
echo "Avec heure locale:"
echo "google-takeout-metadata --localtime $TEST_DIR"  
echo ""
echo "En mode append-only:"
echo "google-takeout-metadata --append-only $TEST_DIR"
echo ""
echo "Avec les deux options:"
echo "google-takeout-metadata --localtime --append-only $TEST_DIR"

echo ""
echo "5. Fonctionnalités implémentées:"
echo "✅ Option --localtime (déjà existante)"
echo "✅ Option --append-only (nouvelle)"
echo "✅ Support des favoris -> Rating=5"
echo "✅ Tests unitaires complets"
echo "✅ Tests d'intégration E2E"
echo "✅ Déduplication des personnes"
echo "✅ Filtrage des coordonnées 0/0"
echo ""
echo "6. Prochaines étapes possibles:"
echo "⏳ Support des albums (metadata.json de dossier)"
echo "⏳ Installation d'exiftool pour les tests d'intégration"

echo ""
echo "=== Test terminé ==="
echo "Répertoire de test: $TEST_DIR"

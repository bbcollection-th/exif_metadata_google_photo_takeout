#!/bin/bash

# Script de démonstration complète des fonctionnalités avec albums

echo "=== Démonstration complète des fonctionnalités avec support albums ==="

# Créer un répertoire de test temporaire
TEST_DIR="/tmp/test_google_takeout_albums"
rm -rf "$TEST_DIR"
mkdir -p "$TEST_DIR/Vacances_2024/Plage"

echo "1. Création de la structure de test avec albums..."

# Créer une image de test dans le sous-dossier
cat > "$TEST_DIR/Vacances_2024/Plage/photo_plage.jpg" << 'EOF'
FFD8FFE000104A46494600010101006000600000FFDB004300080606070605080707070909080A0C140D0C0B0B0C1912130F141D1A1F1E1D1A1C1C20242E2720222C231C1C2837292C30313434341F27393D38323C2E333432FFDB0043010909090C0B0C180D0D1832211C213232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232FFC0001108006400640301220002110103110101FFC4001F0000010501010101010100000000000000000102030405060708090A0BFFC400B5100002010303020403050504040000017D01020300041105122131410613516107227114328191A1082342B1C11552D1F02433627282090A161718191A25262728292A3435363738393A434445464748494A535455565758595A636465666768696A737475767778797A838485868788898A92939495969798999AA2A3A4A5A6A7A8A9AAB2B3B4B5B6B7B8B9BAC2C3C4C5C6C7C8C9CAD2D3D4D5D6D7D8D9DAE1E2E3E4E5E6E7E8E9EAF1F2F3F4F5F6F7F8F9FAFFC4001F0100030101010101010101010000000000000102030405060708090A0BFFC400B51100020102040403040705040400010277000102031104052131061241510761711322328108144291A1B1C109233352F0156272D10A162434E125F11718191A262728292A35363738393A434445464748494A535455565758595A636465666768696A737475767778797A82838485868788898A92939495969798999AA2A3A4A5A6A7A8A9AAB2B3B4B5B6B7B8B9BAC2C3C4C5C6C7C8C9CAD2D3D4D5D6D7D8D9DAE2E3E4E5E6E7E8E9EAF2F3F4F5F6F7F8F9FAFFDA000C03010002110311003F00FFD9
EOF

# Créer le metadata.json pour l'album principal "Vacances 2024"
cat > "$TEST_DIR/Vacances_2024/metadata.json" << 'EOF'
{
  "title": "Vacances Été 2024",
  "description": "Album des vacances d'été 2024 en famille",
  "albums": [
    {"title": "Souvenirs Famille"},
    "Vacances"
  ]
}
EOF

# Créer le metadata.json pour le sous-album "Plage"
cat > "$TEST_DIR/Vacances_2024/Plage/metadata.json" << 'EOF'
{
  "title": "Photos de Plage",
  "description": "Journée à la plage"
}
EOF

# Créer le fichier sidecar avec toutes les métadonnées
cat > "$TEST_DIR/Vacances_2024/Plage/photo_plage.jpg.json" << 'EOF'
{
  "title": "photo_plage.jpg",
  "description": "Belle journée ensoleillée à la plage 🏖️☀️",
  "favorited": {
    "value": true
  },
  "people": [
    {"name": "Alice Dupont"},
    {"name": "Bob Martin"},
    {"name": "Sophie Wilson"}
  ],
  "photoTakenTime": {
    "timestamp": "1736719606"
  },
  "geoData": {
    "latitude": 43.7102,
    "longitude": 7.2620,
    "altitude": 5.0
  }
}
EOF

echo "2. Structure créée:"
echo "=================================="
find "$TEST_DIR" -type f | sort
echo "=================================="

echo ""
echo "3. Contenu du metadata.json principal:"
echo "=================================="
cat "$TEST_DIR/Vacances_2024/metadata.json"
echo -e "\n=================================="

echo ""
echo "4. Contenu du metadata.json sous-dossier:"
echo "=================================="
cat "$TEST_DIR/Vacances_2024/Plage/metadata.json"  
echo -e "\n=================================="

echo ""
echo "5. Contenu du sidecar photo:"
echo "=================================="
cat "$TEST_DIR/Vacances_2024/Plage/photo_plage.jpg.json"
echo -e "\n=================================="

echo ""
echo "6. Cette photo devrait avoir les métadonnées suivantes après traitement:"
echo "- Description: 'Belle journée ensoleillée à la plage 🏖️☀️'"
echo "- Personnes: Alice Dupont, Bob Martin, Sophie Wilson"
echo "- Rating: 5 (car favorited = true)"
echo "- GPS: 43.7102, 7.2620, alt 5m (Côte d'Azur)"
echo "- Albums détectés automatiquement:"
echo "  * Album: Vacances Été 2024 (dossier parent)"
echo "  * Album: Souvenirs Famille (album secondaire)"
echo "  * Album: Vacances (album simple)" 
echo "  * Album: Photos de Plage (sous-dossier)"

echo ""
echo "7. Commande pour traiter:"
echo "google-takeout-metadata '$TEST_DIR'"

echo ""
echo "8. Pour vérifier les résultats après traitement:"
echo "exiftool -json -Keywords -Subject -Rating -GPSLatitude -GPSLongitude -Description '$TEST_DIR/Vacances_2024/Plage/photo_plage.jpg'"

echo ""
echo "=== Fonctionnalités complètement implémentées ==="
echo "✅ Option --localtime"
echo "✅ Option --append-only" 
echo "✅ Support des favoris -> Rating=5"
echo "✅ Support des albums (metadata.json de dossier)"
echo "✅ Tests unitaires complets"
echo "✅ Tests d'intégration E2E complets"
echo "✅ Déduplication des personnes"
echo "✅ Filtrage des coordonnées 0/0"
echo "✅ Support Unicode complet (accents, émojis)"
echo "✅ Support photos et vidéos"

echo ""
echo "=== Test terminé ==="
echo "Répertoire de test: $TEST_DIR"

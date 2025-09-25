"""Test d'intégration pour la correction automatique des erreurs de format de fichier PNG/JPEG."""

import json
import pytest
import subprocess
from unittest.mock import patch

from google_takeout_metadata.processor_batch import process_batch
from google_takeout_metadata import statistics


@pytest.fixture
def setup_real_jpeg_with_png_extension(tmp_path):
    """Créer un vrai fichier JPEG avec extension .PNG pour test d'intégration."""
    # Créer un fichier JPEG réel avec l'en-tête correct
    jpeg_header = (
        b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00'
        b'\xff\xfe\x00\x13Created with GIMP\xff\xdb\x00C\x00\x08\x06\x06'
        # Ajouter un peu plus de contenu pour que ce soit un JPEG valide minimal
        b'\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c'
        b'\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#'
        b'\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x11\x08\x00\x01\x00'
        b'\x01\x01\x01\x11\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x14\x00'
        b'\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08'
        b'\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xaa\xff\xd9'
    )
    
    # Créer le fichier avec extension .PNG
    fake_png_path = tmp_path / "image_format_test.PNG"
    fake_png_path.write_bytes(jpeg_header)
    
    # Créer le JSON sidecar correspondant
    json_data = {
        "title": "image_format_test.PNG",
        "description": "Test image avec incohérence de format",
        "photoTakenTime": {"timestamp": "1577836800"},
        "creationTime": {"timestamp": "1577836800"},
        "people": [{"name": "Test Person"}]
    }
    json_path = fake_png_path.with_suffix(".PNG.supplemental-metadata.json")
    json_path.write_text(json.dumps(json_data, indent=2))
    
    return fake_png_path, json_path


def test_integration_png_jpeg_format_correction(setup_real_jpeg_with_png_extension, tmp_path):
    """Test d'intégration complet pour la correction d'incohérence de format."""
    media_path, json_path = setup_real_jpeg_with_png_extension
    
    # Réinitialiser les statistiques
    statistics.stats = statistics.ProcessingStats()
    
    # Simuler l'erreur ExifTool puis le succès après correction
    def mock_subprocess_run(*args, **kwargs):
        cmd = args[0] if args else kwargs.get('args', [])
        
        # Si la commande contient le fichier .PNG original, simuler l'erreur
        if any('.PNG' in str(arg) and 'image_format_test.PNG' in str(arg) for arg in cmd):
            error = subprocess.CalledProcessError(
                returncode=2,
                cmd=cmd,
                stderr="Error: Not a valid PNG (looks more like a JPEG) - " + str(media_path)
            )
            raise error
        # Si la commande contient le fichier .jpg corrigé, simuler le succès
        elif any('.jpg' in str(arg) and 'image_format_test.jpg' in str(arg) for arg in cmd):
            # Simuler une sortie ExifTool de succès
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="1 image files updated\n",
                stderr=""
            )
        else:
            # Autres cas : succès par défaut
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="",
                stderr=""
            )
    
    # Mock des fonctions nécessaires pour le test
    with patch('subprocess.run', side_effect=mock_subprocess_run):
        with patch('google_takeout_metadata.processor_batch.parse_sidecar') as mock_parse:
            with patch('google_takeout_metadata.processor_batch.build_exiftool_args') as mock_build_args:
                
                # Configuration des mocks
                from unittest.mock import MagicMock
                mock_meta = MagicMock()
                mock_meta.description = "Test description"
                mock_parse.return_value = mock_meta
                mock_build_args.return_value = ["-Description=Test description"]
                
                # Préparer le batch
                batch = [(media_path, json_path, ["-Description=Test description"])]
                
                # Exécuter le traitement
                result = process_batch(batch, False, tmp_path / "logs")
                
                # Vérifications
                assert result == 1  # Succès après correction
                
                # Vérifier que le fichier a été renommé avec la bonne extension
                corrected_path = media_path.with_suffix(".jpg")
                assert corrected_path.exists(), f"Le fichier corrigé {corrected_path} devrait exister"
                assert not media_path.exists(), f"Le fichier original {media_path} ne devrait plus exister"
                
                # Vérifier que le JSON a été mis à jour
                corrected_json_path = json_path.with_name(corrected_path.name + ".supplemental-metadata.json")
                assert corrected_json_path.exists(), f"Le JSON corrigé {corrected_json_path} devrait exister"
                assert not json_path.exists(), f"Le JSON original {json_path} ne devrait plus exister"
                
                # Vérifier le contenu du JSON mis à jour
                with open(corrected_json_path, 'r', encoding='utf-8') as f:
                    updated_json = json.load(f)
                assert updated_json['title'] == corrected_path.name
                
                # Vérifier que les statistiques reflètent la correction
                assert statistics.stats.files_fixed_extension == 1
                assert len(statistics.stats.fixed_extensions) == 1
                assert "image_format_test.PNG" in statistics.stats.fixed_extensions[0]
                assert "image_format_test.jpg" in statistics.stats.fixed_extensions[0]


def test_integration_png_jpeg_detection_via_exiftool(setup_real_jpeg_with_png_extension):
    """Tester que ExifTool détecte bien l'incohérence de format sur un vrai fichier."""
    media_path, json_path = setup_real_jpeg_with_png_extension
    
    # Tester directement avec ExifTool (si disponible)
    try:
        result = subprocess.run(
            ['exiftool', '-FileType', str(media_path)],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            # ExifTool devrait détecter que c'est un JPEG, pas un PNG
            assert "JPEG" in result.stdout.upper() or "JPG" in result.stdout.upper()
            
            # Test de l'erreur réelle avec une commande d'écriture
            subprocess.run(
                ['exiftool', '-Description=Test', str(media_path)],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # ExifTool devrait réussir ou au moins ne pas donner l'erreur PNG
            # (car il détecte automatiquement le format dans les versions récentes)
            
    except (subprocess.TimeoutExpired, FileNotFoundError):
        # ExifTool non disponible ou timeout - ignorer ce test
        pytest.skip("ExifTool non disponible pour le test d'intégration réel")
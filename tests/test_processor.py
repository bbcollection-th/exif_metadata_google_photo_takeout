from pathlib import Path
import json
import unittest.mock
import os
from google_takeout_metadata.processor import (
    process_directory, 
    _is_sidecar_file, 
    fix_file_extension_mismatch
)


def test_ignore_non_sidecar(tmp_path: Path) -> None:
    (tmp_path / "data.json").write_text("{}", encoding="utf-8")
    process_directory(tmp_path, use_localtime=False, append_only=True, immediate_delete=False, organize_files=False, geocode=False)


def test_is_sidecar_file_standard_pattern() -> None:
    """Test standard pattern: photo.jpg.json"""
    assert _is_sidecar_file(Path("photo.jpg.json"))
    assert _is_sidecar_file(Path("video.mp4.json"))
    assert _is_sidecar_file(Path("image.PNG.JSON"))  # insensible à la casse


def test_is_sidecar_file_supplemental_metadata_pattern() -> None:
    """Vérifier le format Google Takeout: photo.jpg.supplemental-metadata.json"""
    assert _is_sidecar_file(Path("IMG_001.jpg.supplemental-metadata.json"))
    assert _is_sidecar_file(Path("video.mp4.supplemental-metadata.json"))
    assert _is_sidecar_file(Path("image.PNG.SUPPLEMENTAL-METADATA.JSON"))  # insensible à la casse
    assert _is_sidecar_file(Path("photo.heic.supplemental-metadata.json"))


def test_is_sidecar_file_older_pattern() -> None:
    """Vérifier l'ancien format: photo.json"""
    assert _is_sidecar_file(Path("IMG_1234.jpg.json"))  # devrait fonctionner avec la nouvelle logique
    # Note: photo.json sans extension dans le nom ne serait pas détecté
    # car c'est ambigu, mais c'est acceptable puisque parse_sidecar() valide


def test_is_sidecar_file_negative() -> None:
    """vérifier les fichiers qui ne devraient pas être détectés comme sidecars"""
    assert not _is_sidecar_file(Path("data.json"))  # pas d'extension d'image
    assert not _is_sidecar_file(Path("photo.txt"))  # pas un json
    assert not _is_sidecar_file(Path("photo.jpg"))  # pas un json
    assert not _is_sidecar_file(Path("metadata.json"))  # album metadata, pas un sidecar
    assert not _is_sidecar_file(Path("métadonnées.json"))  # album metadata, pas un sidecar


def test_fix_file_extension_mismatch_rollback_on_failure(tmp_path: Path) -> None:
    """Vérifier que fix_file_extension_mismatch annule correctement le renommage de l'image en cas d'échec"""
    # Créer un faux fichier JPEG avec une mauvaise extension
    media_path = tmp_path / "photo.png"
    media_path.write_bytes(b'\xff\xd8\xff\xe0')  # JPEG magic bytes

    # Créer le fichier JSON correspondant
    json_path = tmp_path / "photo.png.supplemental-metadata.json"
    json_data = {"title": "photo.png"}
    json_path.write_text(json.dumps(json_data), encoding='utf-8')
    
    # Simuler un échec de unlink pour le fichier JSON (fichier en lecture seule)
    original_unlink = Path.unlink
    def mock_unlink(self):
        if self.name.endswith('.supplemental-metadata.json') and 'photo.png' in str(self):
            raise OSError("Permission denied")
        return original_unlink(self)
    
    with unittest.mock.patch.object(Path, 'unlink', mock_unlink):
        result_image, result_json = fix_file_extension_mismatch(media_path, json_path)
        
        # Devrait retourner les chemins d'origine car le rollback a réussi
        assert result_image == media_path
        assert result_json == json_path
        assert media_path.exists()  # L'image originale devrait exister à nouveau
        assert not (tmp_path / "photo.jpg").exists()  # L'image renommée ne devrait pas exister
        assert not (tmp_path / "photo.jpg.supplemental-metadata.json").exists()  # Pas de JSON orphelin attendu
        
def test_fix_file_extension_mismatch_failed_rollback(tmp_path: Path) -> None:
    """Tester fix_file_extension_mismatch lorsque l'opération et le rollback échouent tous les deux"""
    # Créer un faux fichier JPEG avec une mauvaise extension
    media_path = tmp_path / "photo.png"
    media_path.write_bytes(b'\xff\xd8\xff\xe0')  # JPEG magic bytes

    # Créer le fichier JSON correspondant
    json_path = tmp_path / "photo.png.supplemental-metadata.json"
    json_data = {"title": "photo.png"}
    json_path.write_text(json.dumps(json_data), encoding='utf-8')
    
    # Simuler un échec à la fois pour le renommage de l'image et pour le rollback du JSON
    original_unlink = Path.unlink
    
    def mock_unlink(self):
        if self.name.endswith('.supplemental-metadata.json'):
            raise OSError("Permission denied")
        return original_unlink(self)
    
    def mock_rename(self, target):
        # Simuler un échec lors du rollback du renommage
        if str(target).endswith('.png') and str(self).endswith('.jpg'):
            raise OSError("Rollback failed")
        # Sinon, faire le renommage réel
        
        os.rename(str(self), str(target))
    
    with unittest.mock.patch.object(Path, 'unlink', mock_unlink), \
         unittest.mock.patch.object(Path, 'rename', mock_rename):
        
        result_image, result_json = fix_file_extension_mismatch(media_path, json_path)

        # Devrait retourner le nouveau chemin de l'image mais l'ancien chemin du JSON en raison du rollback échoué
        assert result_image == tmp_path / "photo.jpg"
        assert result_json == json_path  # Chemin JSON d'origine
        assert (tmp_path / "photo.jpg").exists()  # La nouvelle image devrait exister
        assert not media_path.exists()  # L'image originale ne devrait pas exister

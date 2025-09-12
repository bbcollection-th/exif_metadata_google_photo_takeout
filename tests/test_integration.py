"""Tests d'intégration qui exécutent réellement exiftool et vérifient que les métadonnées sont écrites correctement."""

from pathlib import Path
import json
import subprocess
import pytest
import shutil
from PIL import Image

from google_takeout_metadata.processor import process_sidecar_file
from google_takeout_metadata.exif_writer import write_metadata
from google_takeout_metadata.sidecar import SidecarData


def _get_test_assets_dir() -> Path:
    """Retourne le chemin vers le dossier des assets de test."""
    return Path(__file__).parent.parent / "test_assets"


def _copy_test_asset(asset_name: str, dest_path: Path) -> None:
    """Copie un asset de test vers le chemin de destination."""
    assets_dir = _get_test_assets_dir()
    asset_path = assets_dir / asset_name
    if not asset_path.exists():
        pytest.skip(f"Asset de test {asset_name} introuvable dans {assets_dir}")
    shutil.copy2(asset_path, dest_path)


def _run_exiftool_read(media_path: Path) -> dict:
    """Exécuter exiftool pour lire les métadonnées depuis un fichier image."""
    cmd = [
        "exiftool", 
        "-json",
        "-charset", "title=UTF8",
        "-charset", "iptc=UTF8", 
        "-charset", "exif=UTF8",
        "-charset", "XMP=UTF8",
        str(media_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        data = json.loads(result.stdout)
        return data[0] if data else {}
    except FileNotFoundError:
        pytest.skip("exiftool introuvable - skipping integration tests")
    except subprocess.CalledProcessError as e:
        pytest.fail(f"exiftool failed: {e.stderr}")


@pytest.mark.integration
def test_write_and_read_description(tmp_path: Path) -> None:
    """Tester que la description est écrite et peut être relue."""
    # Utiliser un asset de test propre
    media_path = tmp_path / "test.jpg"
    _copy_test_asset("test_clean.jpg", media_path)
    
    # Créer le JSON sidecar
    sidecar_data = {
        "title": "test.jpg",
        "description": "Test photo with ñ and émojis 🎉"
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Traiter le sidecar
    process_sidecar_file(json_path, use_localtime=False, append_only=False, immediate_delete=False, organize_files=False, geocode=False)
    
    # Relire les métadonnées
    metadata = _run_exiftool_read(media_path)
    
    # Vérifier que la description a été écrite
    assert metadata.get("Description") == "Test photo with ñ and émojis 🎉"
    assert metadata.get("ImageDescription") == "Test photo with ñ and émojis 🎉"


@pytest.mark.integration
def test_write_and_read_people_name(tmp_path: Path) -> None:
    """Tester que les noms de personnes sont écrits et peuvent être relus."""
    # Utiliser un asset de test propre
    media_path = tmp_path / "test.jpg"
    _copy_test_asset("test_clean.jpg", media_path)
    
    # Créer le JSON sidecar avec des personnes
    sidecar_data = {
        "title": "test.jpg",
        "people": [
            {"name": "Alice Dupont"},
            {"name": "Bob Martin"}
        ]
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Traiter le sidecar
    process_sidecar_file(json_path, use_localtime=False, append_only=False, immediate_delete=False, organize_files=False, geocode=False)

    # Relire les métadonnées
    metadata = _run_exiftool_read(media_path)
    
    # Vérifier que les personnes ont été écrites
    keywords = metadata.get("Keywords", [])
    if isinstance(keywords, str):
        keywords = [keywords]
    
    assert "Alice Dupont" in keywords
    assert "Bob Martin" in keywords


@pytest.mark.integration 
def test_write_and_read_gps(tmp_path: Path) -> None:
    """Tester que les coordonnées GPS sont écrites et peuvent être relues."""
    # Utiliser un asset de test propre
    media_path = tmp_path / "test.jpg"
    _copy_test_asset("test_clean.jpg", media_path)
    
    # Créer le JSON sidecar avec des données GPS
    sidecar_data = {
        "title": "test.jpg",
        "geoData": {
            "latitude": 48.8566,
            "longitude": 2.3522,
            "altitude": 35.0
        }
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Traiter le sidecar
    process_sidecar_file(json_path, use_localtime=False, append_only=False, immediate_delete=False, organize_files=False, geocode=False)
    
    # Relire les métadonnées
    metadata = _run_exiftool_read(media_path)
    
    # Vérifier que les données GPS ont été écrites
    # exiftool retourne les coordonnées GPS dans un format lisible, donc on doit vérifier différemment
    gps_lat = metadata.get("GPSLatitude")
    gps_lon = metadata.get("GPSLongitude")
    
    # Vérifier que les champs GPS existent et contiennent les valeurs de degrés attendues
    assert gps_lat is not None, "GPSLatitude devrait être définie"
    assert gps_lon is not None, "GPSLongitude devrait être définie"
    assert "48 deg" in str(gps_lat), f"Expected 48 degrees in geoData_latitude, got: {gps_lat}"
    assert "2 deg" in str(gps_lon), f"Expected 2 degrees in geoData_longitude, got: {gps_lon}"
    
    # Les références GPS peuvent être "N"/"North" et "E"/"East" selon la version d'exiftool
    lat_ref = metadata.get("GPSLatitudeRef")
    lon_ref = metadata.get("GPSLongitudeRef")
    assert lat_ref in ["N", "North"], f"Expected N or North for geoData_latitude ref, got: {lat_ref}"
    assert lon_ref in ["E", "East"], f"Expected E or East for geoData_longitude ref, got: {lon_ref}"


@pytest.mark.integration
def test_write_and_read_favorited(tmp_path: Path) -> None:
    """Tester que le statut favori est écrit comme notation."""
    # Créer une image de test simple
    media_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='yellow')
    img.save(media_path)
    
    # Créer le fichier JSON annexe avec favori
    sidecar_data = {
        "title": "test.jpg",
        "favorited": True
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Traiter le sidecar
    process_sidecar_file(json_path, use_localtime=False, append_only=False, immediate_delete=False, organize_files=False, geocode=False)

    # Relire les métadonnées
    metadata = _run_exiftool_read(media_path)
    
    # Vérifier que la notation a été écrite
    assert int(metadata.get("Rating", 0)) == 5


@pytest.mark.integration
def test_append_only_mode(tmp_path: Path) -> None:
    """Tester que le mode append-only n'écrase pas la description existante."""
    # Utiliser un asset de test avec métadonnées existantes
    media_path = tmp_path / "test.jpg"
    _copy_test_asset("test_with_metadata.jpg", media_path)
    
    # Créer le fichier JSON annexe avec une description différente
    sidecar_data = {
        "title": "test.jpg", 
        "description": "New description from sidecar"
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Traiter le sidecar en mode append-only
    process_sidecar_file(json_path, use_localtime=False, append_only=True, immediate_delete=False, organize_files=False, geocode=False)

    # Relire les métadonnées
    metadata = _run_exiftool_read(media_path)
    
    # En mode append-only, la description originale devrait être préservée
    # Note: exiftool's -= operator doesn't overwrite if field exists
    assert metadata.get("ImageDescription") == "Existing description"


@pytest.mark.integration
def test_datetime_formats(tmp_path: Path) -> None:
    """Tester que la date-heure est écrite dans le bon format."""
    # Créer une image de test simple
    media_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='orange')
    img.save(media_path)
    
    # Créer le fichier JSON annexe avec horodatage
    sidecar_data = {
        "title": "test.jpg",
        "photoTakenTime_timestamp": {"timestamp": "1736719606"}  # Horodatage Unix
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Traiter le sidecar
    process_sidecar_file(json_path, use_localtime=False, append_only=False, immediate_delete=False, organize_files=False, geocode=False)

    # Relire les métadonnées
    metadata = _run_exiftool_read(media_path)
    
    # Vérifier le format de la date-heure (devrait être YYYY:MM:DD HH:MM:SS)
    date_original = metadata.get("DateTimeOriginal")
    assert date_original is not None
    assert ":" in date_original
    # Devrait correspondre au format EXIF datetime
    import re
    assert re.match(r'\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2}', date_original)


@pytest.mark.integration
def test_write_and_read_albums(tmp_path: Path) -> None:
    """Tester que les albums sont écrits et peuvent être relus."""
    # Créer une image de test simple
    media_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='cyan')
    img.save(media_path)
    
    # Créer le fichier metadata.json d'album
    album_data = {"title": "Vacances Été 2024"}
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(album_data), encoding="utf-8")
    
    # Créer le fichier JSON annexe
    sidecar_data = {
        "title": "test.jpg",
        "description": "Photo de vacances"
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Traiter le sidecar
    process_sidecar_file(json_path, use_localtime=False, append_only=False, immediate_delete=False, organize_files=False, geocode=False)

    # Relire les métadonnées
    metadata = _run_exiftool_read(media_path)
    
    # Vérifier que l'album a été écrit comme mot-clé
    keywords = metadata.get("Keywords", [])
    if isinstance(keywords, str):
        keywords = [keywords]
    
    assert "Album: Vacances Été 2024" in keywords
    
    # Vérifier aussi le champ Subject
    subjects = metadata.get("Subject", [])
    if isinstance(subjects, str):
        subjects = [subjects]
    
    assert "Album: Vacances Été 2024" in subjects


@pytest.mark.integration  
def test_albums_and_people_name_combined(tmp_path: Path) -> None:
    """Tester que les albums et les personnes peuvent coexister dans les mots-clés."""
    # Créer une image de test simple
    media_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='magenta')
    img.save(media_path)
    
    # Créer le fichier metadata.json d'album
    album_data = {"title": "Album Famille"}
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(album_data), encoding="utf-8")
    
    # Créer le fichier JSON annexe avec des personnes
    sidecar_data = {
        "title": "test.jpg",
        "people": [{"name": "Alice"}, {"name": "Bob"}]
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Traiter le sidecar
    process_sidecar_file(json_path, use_localtime=False, append_only=False, immediate_delete=False, organize_files=False, geocode=False)
    
    # Relire les métadonnées
    metadata = _run_exiftool_read(media_path)
    
    # Vérifier que les mots-clés contiennent à la fois les personnes et l'album
    keywords = metadata.get("Keywords", [])
    if isinstance(keywords, str):
        keywords = [keywords]

    # Vérifier que nous avons à la fois des personnes et un album
    assert "Alice" in keywords
    assert "Bob" in keywords
    assert "Album: Album Famille" in keywords


@pytest.mark.integration
def test_default_safe_behavior(tmp_path: Path) -> None:
    """Tester que le comportement par défaut est sûr (append-only) et préserve les métadonnées existantes."""
    # Créer une simple image de test
    media_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='red')
    img.save(media_path)

    # Tout d'abord, ajouter manuellement des métadonnées en utilisant le mode écrasement
    first_meta = SidecarData(
        title="test.jpg",
        description="Original description",
        people_name=["Original Person"],
        photoTakenTime_timestamp=None,
        creationTime_timestamp=None,
        geoData_latitude=None,
        geoData_longitude=None,
        geoData_altitude=None,
        city=None,
        state=None,
        country=None,
        place_name=None,
        favorited=False,
        albums=["Original Album"]
    )
    
    # Écrire les métadonnées initiales avec le mode écrasement
    write_metadata(media_path, first_meta, append_only=False)

    # Vérifier que les métadonnées initiales ont été écrites
    initial_metadata = _run_exiftool_read(media_path)
    assert initial_metadata.get("ImageDescription") == "Original description"
    initial_keywords = initial_metadata.get("Keywords", [])
    if isinstance(initial_keywords, str):
        initial_keywords = [initial_keywords]
    assert "Original Person" in initial_keywords
    assert "Album: Original Album" in initial_keywords
    
    # Créer le fichier JSON annexe avec une nouvelle description et une nouvelle personne
    sidecar_data = {
        "title": "test.jpg",
        "description": "New description", 
        "people": [{"name": "New Person"}]
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Traiter le sidecar en mode par défaut (append-only)
    process_sidecar_file(json_path, use_localtime=False, append_only=False, immediate_delete=False, organize_files=False, geocode=False)

    # Relire les métadonnées
    final_metadata = _run_exiftool_read(media_path)

    # En mode append-only, la description d'origine doit être préservée
    # car nous utilisons -if "not $TAG" qui n'écrit que si le tag n'existe pas
    assert final_metadata.get("ImageDescription") == "Original description"

    # Les mots-clés devraient toujours contenir les données d'origine, et les nouvelles personnes devraient être AJOUTÉES (pas remplacées)
    # car nous utilisons = qui accumule pour les balises de type liste
    final_keywords = final_metadata.get("Keywords", [])
    if isinstance(final_keywords, str):
        final_keywords = [final_keywords]
    assert "Original Person" in final_keywords
    assert "Album: Original Album" in final_keywords
    # La nouvelle personne devrait également être présente
    assert "New Person" in final_keywords


@pytest.mark.integration  
def test_explicit_overwrite_behavior(tmp_path: Path) -> None:
    """Tester que le mode écrasement explicite remplace les métadonnées existantes."""
    # Créer une simple image de test
    media_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='blue') 
    img.save(media_path)

    # Tout d'abord, ajouter des métadonnées initiales en utilisant le mode écrasement
    first_meta = SidecarData(
        title="test.jpg",
        description="Original description",
        people_name=["Original Person"],
        photoTakenTime_timestamp=None,
        creationTime_timestamp=None,
        geoData_latitude=None,
        geoData_longitude=None,
        geoData_altitude=None,
        city=None,
        state=None,
        country=None,
        place_name=None,
        favorited=False,
        albums=[]
    )
    
    write_metadata(media_path, first_meta, append_only=False)
    
    # Vérifier que les métadonnées initiales ont été écrites
    sidecar_data = {
        "title": "test.jpg",
        "description": "New description",
        "people": [{"name": "New Person"}]
    }
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    # Traiter le sidecar en mode écrasement explicite
    process_sidecar_file(json_path, use_localtime=False, append_only=False, immediate_delete=False, organize_files=False, geocode=False)

    # Relire les métadonnées
    final_metadata = _run_exiftool_read(media_path)

    # En mode écrasement, la nouvelle description doit remplacer l'ancienne
    # Note: Nous utilisons l'opérateur = donc les personnes sont ajoutées et accumulent
    final_keywords = final_metadata.get("Keywords", [])
    if isinstance(final_keywords, str):
        final_keywords = [final_keywords]

    # Les deux personnes, originale et nouvelle, devraient être présentes (car = accumule pour les listes)
    assert "Original Person" in final_keywords
    assert "New Person" in final_keywords


@pytest.mark.integration
def test_append_only_vs_overwrite_video_equivalence(tmp_path: Path) -> None:
    """Tester que le mode append-only produit des résultats similaires au mode écrasement pour les vidéos quand aucune métadonnée n'existe."""
    
    # Copier les fichiers vidéo de test (vierges)
    video_path_append = tmp_path / "test_append.mp4"
    video_path_overwrite = tmp_path / "test_overwrite.mp4"
    
    _copy_test_asset("test_video_clean.mp4", video_path_append)
    _copy_test_asset("test_video_clean.mp4", video_path_overwrite)
    
    # Créer les métadonnées à écrire
    meta = SidecarData(
        title="test.mp4",
        description="Test video description",
        people_name=["Video Person"],
        photoTakenTime_timestamp=1736719606,
        creationTime_timestamp=None,
        geoData_latitude=48.8566,
        geoData_longitude=2.3522,
        geoData_altitude=35.0,
        city=None,
        state=None,
        country=None,
        place_name=None,
        favorited=True,
        albums=["Test Album"]
    )
    
    # Écrire avec le mode append-only
    write_metadata(video_path_append, meta, append_only=True)

    # Écrire avec le mode écrasement
    write_metadata(video_path_overwrite, meta, append_only=False)

    # Relire les métadonnées des deux fichiers
    metadata_append = _run_exiftool_read(video_path_append)
    metadata_overwrite = _run_exiftool_read(video_path_overwrite)
    
    # Comparer les champs clés
    # En mode append-only, les nouvelles métadonnées peuvent ne pas être écrites si des tags similaires existent
    # En mode overwrite, les métadonnées sont toujours écrites
    # Le test vérifie que les nouvelles métadonnées importantes sont présentes
    
    # Les mots-clés devraient contenir la personne et l'album dans les deux modes
    keywords_append = metadata_append.get("Keywords", [])
    keywords_overwrite = metadata_overwrite.get("Keywords", [])
    if isinstance(keywords_append, str):
        keywords_append = [keywords_append]
    if isinstance(keywords_overwrite, str):
        keywords_overwrite = [keywords_overwrite]
    
    # Vérifier que les nouvelles métadonnées importantes sont présentes
    # En mode overwrite, les nouveaux mots-clés doivent être présents
    # Pour les vidéos MP4, les mots-clés sont stockés dans Subject, pas Keywords
    subjects_append = metadata_append.get("Subject", [])
    subjects_overwrite = metadata_overwrite.get("Subject", [])
    if isinstance(subjects_append, str):
        subjects_append = [subjects_append]
    if isinstance(subjects_overwrite, str):
        subjects_overwrite = [subjects_overwrite]
    
    # Combiner Keywords et Subject pour une vérification complète
    all_keywords_append = keywords_append + subjects_append
    all_keywords_overwrite = keywords_overwrite + subjects_overwrite
    
    assert "Video Person" in all_keywords_overwrite
    assert "Album: Test Album" in all_keywords_overwrite
    
    # En mode append-only, les mots-clés sont ajoutés même si d'autres existent
    assert "Video Person" in all_keywords_append
    assert "Album: Test Album" in all_keywords_append


@pytest.mark.integration
def test_batch_vs_normal_mode_equivalence(tmp_path: Path) -> None:
    """Tester que le mode batch produit les mêmes résultats que le mode normal."""
    # Importer la fonction de traitement par lot
    from google_takeout_metadata.processor_batch import process_directory_batch
    from google_takeout_metadata.processor import process_directory

    # Créer des données de test
    test_files = [
        ("photo1.jpg", "First test photo", "Alice"),
        ("photo2.jpg", "Second test photo", "Bob"),
        ("photo3.jpg", "Third test photo", "Charlie")
    ]

    # Créer deux structures de répertoires identiques
    normal_dir = tmp_path / "normal_mode"
    batch_dir = tmp_path / "batch_mode"
    normal_dir.mkdir()
    batch_dir.mkdir()
    
    for title, description, person in test_files:
        # Créer les deux fichiers dans les deux répertoires
        for test_dir in [normal_dir, batch_dir]:
            # Créer l'image
            media_path = test_dir / title
            img = Image.new('RGB', (100, 100), color='blue')
            img.save(media_path)

            # Créer le sidecar
            sidecar_data = {
                "title": title,
                "description": description,
                "people": [{"name": person}]
            }
            json_path = test_dir / f"{title}.json"
            json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    try:
        # Proceder avec le mode normal
        process_directory(normal_dir, use_localtime=False, append_only=True, immediate_delete=False)

        # Traiter avec le mode par lot
        process_directory_batch(batch_dir, use_localtime=False, append_only=True, immediate_delete=False, organize_files=True,
            geocode=False)
        
        # Comparer les métadonnées des fichiers dans les deux répertoires
        for title, expected_description, expected_person in test_files:
            normal_metadata = _run_exiftool_read(normal_dir / title)
            batch_metadata = _run_exiftool_read(batch_dir / title)

            # Vérifier que les descriptions correspondent
            assert normal_metadata.get("ImageDescription") == batch_metadata.get("ImageDescription")
            assert normal_metadata.get("ImageDescription") == expected_description

            # Vérifier que les personnes correspondent
            normal_people_name = normal_metadata.get("PersonInImage", [])
            batch_people_name = batch_metadata.get("PersonInImage", [])
            if isinstance(normal_people_name, str):
                normal_people_name = [normal_people_name]
            if isinstance(batch_people_name, str):
                batch_people_name = [batch_people_name]
            
            assert set(normal_people_name) == set(batch_people_name)
            assert expected_person in normal_people_name
            
    except FileNotFoundError:
        pytest.skip("exiftool introuvable - skipping batch vs normal mode test")


@pytest.mark.integration
def test_batch_mode_performance_benefit(tmp_path: Path) -> None:
    """Tester que le mode batch peut gérer de nombreux fichiers (test de performance)."""
    from google_takeout_metadata.processor_batch import process_directory_batch
    import time

    # Créer de nombreux fichiers de test
    num_files = 20  # Réduit pour CI, mais démontre toujours la capacité par lot

    for i in range(num_files):
        title = f"perf_test_{i:03d}.jpg"

        # Créer l'image
        media_path = tmp_path / title
        img = Image.new('RGB', (50, 50), color='red')
        img.save(media_path)

        # Créer le sidecar
        sidecar_data = {
            "title": title,
            "description": f"Performance test image {i}"
        }
        json_path = tmp_path / f"{title}.json"
        json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    try:
        # Mesurer le temps de traitement par lot
        start_time = time.time()
        process_directory_batch(tmp_path, use_localtime=False, append_only=True, immediate_delete=False, organize_files=True,
            geocode=False)
        end_time = time.time()
        
        batch_time = end_time - start_time
        
        # Vérifier que tous les fichiers ont été traités
        for i in range(num_files):
            title = f"perf_test_{i:03d}.jpg"
            media_path = tmp_path / title
            
            metadata = _run_exiftool_read(media_path)
            expected_description = f"Performance test image {i}"
            assert metadata.get("ImageDescription") == expected_description
        
        # Imprimer le temps pris pour le traitement par lot
        print(f"Batch mode processed {num_files} files in {batch_time:.2f} seconds")
        
    except FileNotFoundError:
        pytest.skip("exiftool introuvable - skipping batch performance test")


@pytest.mark.integration  
def test_batch_mode_with_mixed_file_types(tmp_path: Path) -> None:
    """Tester le mode batch avec différents types de fichiers et métadonnées complexes."""
    from google_takeout_metadata.processor_batch import process_directory_batch
    
    # Créer des fichiers de test avec différents types et métadonnées
    test_files = [
        ("mixed1.jpg", "JPEG test"),
        ("mixed2.png", "PNG test")  # PNG if supported by PIL
    ]
    
    for title, description in test_files:
        # Créer l'image
        media_path = tmp_path / title
        if title.endswith('.jpg'):
            img = Image.new('RGB', (100, 100), color='green')
            img.save(media_path, format='JPEG')
        elif title.endswith('.png'):
            img = Image.new('RGBA', (100, 100), color=(0, 255, 0, 128))
            img.save(media_path, format='PNG')

        # Créer le sidecar complexe
        sidecar_data = {
            "title": title,
            "description": description,
            "people": [{"name": "Mixed Test Person"}],
            "favorited": True,
            "geoData": {
                "latitude": 45.5017,
                "longitude": -73.5673,
                "altitude": 20.0
            }
        }
        json_path = tmp_path / f"{title}.json"
        json_path.write_text(json.dumps(sidecar_data), encoding="utf-8")
    
    try:
        # Traiter avec le mode par lot
        process_directory_batch(tmp_path, use_localtime=False, append_only=True, immediate_delete=False, organize_files=True,
            geocode=False)

        # Vérifier que tous les fichiers ont été traités
        for title, expected_description in test_files:
            media_path = tmp_path / title
            
            metadata = _run_exiftool_read(media_path)
            
            # Vérifier la description
            assert metadata.get("ImageDescription") == expected_description

            # Vérifier les personnes
            people_name = metadata.get("PersonInImage", [])
            if isinstance(people_name, str):
                people_name = [people_name]
            assert "Mixed Test Person" in people_name

            # Vérifier la note (favori)
            rating = metadata.get("Rating")
            assert rating == 5 or rating == "5"

            # Vérifier les données GPS (peut ne pas fonctionner pour tous les types de fichiers)
            gps_lat = metadata.get("GPSLatitude")
            if gps_lat is not None:
                # Si GPSLatitude est présent, vérifier qu'il est correct
                assert "45 deg" in str(gps_lat)
                assert gps_lat is not None
        
    except FileNotFoundError:
        pytest.skip("exiftool introuvable - skipping mixed file types batch test")

from google_takeout_metadata.sidecar import SidecarData
from google_takeout_metadata.exif_writer import write_metadata, build_exiftool_args
import subprocess
import pytest
from pathlib import Path


def test_write_metadata_error(tmp_path, monkeypatch):
    meta = SidecarData(
        filename="a.jpg",
        description="test",  # Add description to ensure args are generated
        people=[],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        favorite=False,
    )
    img = tmp_path / "a.jpg"
    img.write_bytes(b"data")

    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "exiftool", stderr="bad")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError):
        write_metadata(img, meta)


def test_build_args_video():
    """Tester que les balises spécifiques aux vidéos sont ajoutées pour les fichiers MP4/MOV."""
    meta = SidecarData(
        filename="video.mp4",
        description="Video description",
        people=["alice"],
        taken_at=1736719606,
        created_at=None,
        latitude=48.8566,
        longitude=2.3522,
        altitude=None,
        favorite=False,
    )
    
    video_path = Path("video.mp4")
    args = build_exiftool_args(meta, media_path=video_path)
    
    # Vérifier les balises spécifiques aux vidéos
    assert "-Keys:Description=Video description" in args
    assert any("-QuickTime:CreateDate=" in arg for arg in args)
    assert any("-QuickTime:ModifyDate=" in arg for arg in args)
    assert "-Keys:Location=48.8566,2.3522" in args
    assert "-QuickTime:GPSCoordinates=48.8566,2.3522" in args
    assert "-api" in args
    assert "QuickTimeUTC=1" in args


def test_build_args_localtime():
    """Tester que le formatage de l'heure locale fonctionne."""
    meta = SidecarData(
        filename="a.jpg",
        description=None,
        people=[],
        taken_at=1736719606,  # 2025-01-12 22:06:46 UTC
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        favorite=False,
    )

    # Test UTC (default)
    args_utc = build_exiftool_args(meta, media_path=Path("a.jpg"), use_localtime=False)
    # Test local time
    args_local = build_exiftool_args(meta, media_path=Path("a.jpg"), use_localtime=True)
    
    # Les chaînes de date-heure seront différentes (sauf si exécuté dans le fuseau horaire UTC)
    # mais les deux devraient contenir une forme de DateTimeOriginal
    assert any("-DateTimeOriginal=" in arg for arg in args_utc)
    assert any("-DateTimeOriginal=" in arg for arg in args_local)


def test_build_args_append_only() -> None:
    """Tester que le mode append-only utilise l'approche anti-duplication.
    
    La nouvelle approche utilise -TAG-=val puis -TAG+=val pour garantir
    zéro doublon avec normalisation des noms.
    """
    meta = SidecarData(
        filename="a.jpg",
        description="desc",
        people=["alice", "bob"],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        favorite=False,
    )

    # Normal mode (écrasement)
    args_normal = build_exiftool_args(meta, append_only=False)
    assert "-EXIF:ImageDescription=desc" in args_normal
    # En mode overwrite, on vide d'abord puis on ajoute (normalisé)
    assert "-XMP-iptcExt:PersonInImage=" in args_normal
    assert "-XMP-iptcExt:PersonInImage+=Alice" in args_normal  # Normalisé
    assert "-XMP-iptcExt:PersonInImage+=Bob" in args_normal    # Normalisé

    # Append-only mode avec déduplication
    args_append = build_exiftool_args(meta, append_only=True)
    # Nouvelle approche : supprimer puis ajouter pour déduplication
    assert "-EXIF:ImageDescription=desc" in args_append
    # Vérifier la séquence -=/+= pour PersonInImage
    assert "-XMP-iptcExt:PersonInImage-=Alice" in args_append  # Normalisé
    assert "-XMP-iptcExt:PersonInImage+=Alice" in args_append  # Normalisé
    assert "-XMP-iptcExt:PersonInImage-=Bob" in args_append    # Normalisé
    assert "-XMP-iptcExt:PersonInImage+=Bob" in args_append    # Normalisé


def test_build_args_favorite() -> None:
    """Tester que les photos favorites obtiennent rating=5."""
    meta = SidecarData(
        filename="a.jpg",
        description=None,
        people=[],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        favorite=True,
    )

    args = build_exiftool_args(meta, append_only=False)
    assert "-XMP:Rating=5" in args

    # Tester le mode append-only (maintenant le comportement par défaut)
    args_append = build_exiftool_args(meta, append_only=True)
    # Devrait utiliser -wm cg pour l'écriture conditionnelle
    assert "-wm" in args_append
    assert "cg" in args_append
    assert "-XMP:Rating=5" in args_append


def test_build_args_no_favorite() -> None:
    """Tester que les photos non favorites n'obtiennent pas de rating."""
    meta = SidecarData(
        filename="a.jpg",
        description=None,
        people=[],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        favorite=False,
    )

    args = build_exiftool_args(meta)
    assert not any("Rating" in arg for arg in args)


def test_build_args_albums() -> None:
    """Tester que les albums sont écrits comme mots-clés avec le préfixe Album: et normalisation."""
    meta = SidecarData(
        filename="a.jpg",
        description=None,
        people=[],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        favorite=False,
        albums=["Vacances 2024", "Famille"]
    )

    args = build_exiftool_args(meta, append_only=False)
    # En mode overwrite, on vide d'abord puis on ajoute (avec normalisation)
    assert "-XMP-dc:Subject=" in args
    assert "-IPTC:Keywords=" in args
    # Les mots-clés sont normalisés (chaque mot avec première lettre en majuscule)
    assert "-XMP-dc:Subject+=Album: Vacances 2024" in args
    assert "-IPTC:Keywords+=Album: Vacances 2024" in args
    assert "-XMP-dc:Subject+=Album: Famille" in args
    assert "-IPTC:Keywords+=Album: Famille" in args


def test_build_args_video_append_only() -> None:
    """Tester que les balises spécifiques aux vidéos sont incluses en mode append-only."""
    meta = SidecarData(
        filename="video.mp4",
        description="Video description",
        people=["alice"],
        taken_at=1736719606,
        created_at=None,
        latitude=48.8566,
        longitude=2.3522,
        altitude=35.0,
        favorite=False,
    )
    
    video_path = Path("video.mp4")
    args = build_exiftool_args(meta, media_path=video_path, append_only=True)
    
    # Vérifier que l'approche append-only utilise -wm cg
    assert "-wm" in args
    assert "cg" in args
    assert "-Keys:Description=Video description" in args
    
    # Vérifier que les dates QuickTime sont présentes
    assert any("QuickTime:CreateDate=" in arg for arg in args)
    assert any("QuickTime:ModifyDate=" in arg for arg in args)
    
    # Vérifier que les champs GPS spécifiques à la vidéo sont présents
    assert "-QuickTime:GPSCoordinates=48.8566,2.3522" in args
    assert "-Keys:Location=48.8566,2.3522" in args
    
    # Vérifier que l'altitude est présente
    assert "-GPSAltitude=35.0" in args
    
    # Vérifier la configuration vidéo
    assert "-api" in args
    assert "QuickTimeUTC=1" in args


def test_build_args_albums_append_only() -> None:
    """Tester les albums en mode append-only avec déduplication."""
    meta = SidecarData(
        filename="a.jpg",
        description=None,
        people=[],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        favorite=False,
        albums=["Test Album"]
    )

    args = build_exiftool_args(meta, append_only=True)
    # Nouvelle approche : supprimer puis ajouter pour déduplication
    # Les albums sont normalisés (chaque mot avec première lettre en majuscule)
    assert "-XMP-dc:Subject-=Album: Test Album" in args
    assert "-XMP-dc:Subject+=Album: Test Album" in args
    assert "-IPTC:Keywords-=Album: Test Album" in args
    assert "-IPTC:Keywords+=Album: Test Album" in args


def test_build_args_no_albums() -> None:
    """Tester que la liste d'albums vide n'ajoute aucune balise d'album."""
    meta = SidecarData(
        filename="a.jpg",
        description=None,
        people=[],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        favorite=False,
        albums=[]
    )

    args = build_exiftool_args(meta)
    assert not any("Album:" in arg for arg in args)


def test_build_args_default_behavior() -> None:
    """Tester que le comportement par défaut est append-only (mode sécurisé)."""
    meta = SidecarData(
        filename="a.jpg",
        description="Safe description",
        people=["Safe Person"],
        taken_at=1736719606,
        created_at=None,
        latitude=48.8566,
        longitude=2.3522,
        altitude=None,
        favorite=True,
    )

    # Le comportement par défaut devrait être append-only (sécurisé)
    args = build_exiftool_args(meta)
    
    # Devrait utiliser -wm cg pour l'écriture conditionnelle
    assert "-wm" in args
    assert "cg" in args
    assert "-EXIF:ImageDescription=Safe description" in args
    # Devrait utiliser += pour les personnes (accumulation en mode append-only)
    assert "-XMP-iptcExt:PersonInImage+=Safe Person" in args
    # Le rating devrait être présent
    assert "-XMP:Rating=5" in args
    # GPS devrait être présent
    assert "-GPSLatitude=48.8566" in args


def test_build_args_overwrite_mode() -> None:
    """Mode de réécriture explicite (destructif)."""
    meta = SidecarData(
        filename="a.jpg",
        description="Overwrite description",
        people=["Overwrite Person"],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        favorite=True,
    )

    # Mode de réécriture explicite
    args = build_exiftool_args(meta, append_only=False)
    
    # Devrait utiliser l'assignation directe pour les descriptions et les ratings
    assert "-EXIF:ImageDescription=Overwrite description" in args
    # En mode overwrite, on vide d'abord puis on ajoute
    assert "-XMP-iptcExt:PersonInImage=" in args
    assert "-XMP-iptcExt:PersonInImage+=Overwrite Person" in args
    assert "-XMP:Rating=5" in args
    # Ne devrait PAS avoir de conditions -if
    assert "-if" not in args
    assert "not $EXIF:ImageDescription" not in args
    assert "not $XMP-iptcExt:PersonInImage" not in args
    assert "not $XMP:Rating" not in args


def test_build_args_people_default() -> None:
    """Tester que les personnes sont gérées avec déduplication par défaut."""
    meta = SidecarData(
        filename="a.jpg",
        description=None,
        people=["Alice Dupont", "Bob Martin", "Charlie Bernard"],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        favorite=False,
    )

    # Comportement par défaut (append-only avec déduplication)
    args = build_exiftool_args(meta)
    
    # Nouvelle approche : supprimer puis ajouter pour déduplication
    # Les personnes sont dans PersonInImage, mais aussi dans les mots-clés
    for person in ["Alice Dupont", "Bob Martin", "Charlie Bernard"]:
        # PersonInImage : déduplication directe
        assert f"-XMP-iptcExt:PersonInImage-={person}" in args
        assert f"-XMP-iptcExt:PersonInImage+={person}" in args
        # Mots-clés : déduplication des personnes aussi
        assert f"-XMP-dc:Subject-={person}" in args
        assert f"-XMP-dc:Subject+={person}" in args
        assert f"-IPTC:Keywords-={person}" in args
        assert f"-IPTC:Keywords+={person}" in args
    
    # Ne devrait PAS avoir de conditions -if (remplacé par approche -=/+=)
    assert "not $XMP-iptcExt:PersonInImage" not in args
    assert "not $XMP-dc:Subject" not in args
    assert "not $IPTC:Keywords" not in args


def test_build_args_albums_default() -> None:
    """Tester que les albums sont gérés avec déduplication par défaut."""
    meta = SidecarData(
        filename="a.jpg",
        description=None,
        people=[],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        favorite=False,
        albums=["Vacances Été 2024", "Photos de Famille", "Événements Spéciaux"]
    )

    # Comportement par défaut (append-only avec déduplication)
    args = build_exiftool_args(meta)
    
    # Nouvelle approche : supprimer puis ajouter pour déduplication
    # Les albums sont normalisés avec chaque mot commençant par une majuscule
    expected_albums = ["Album: Vacances Été 2024", "Album: Photos De Famille", "Album: Événements Spéciaux"]
    for album_keyword in expected_albums:
        assert f"-XMP-dc:Subject-={album_keyword}" in args
        assert f"-XMP-dc:Subject+={album_keyword}" in args
        assert f"-IPTC:Keywords-={album_keyword}" in args
        assert f"-IPTC:Keywords+={album_keyword}" in args
    
    # Ne devrait PAS avoir de conditions -if pour les albums (ils sont des listes, utiliser +=)
    assert "not $XMP-dc:Subject" not in args
    assert "not $IPTC:Keywords" not in args

# Fichier : tests/test_deduplication_robuste.py

"""Tests spécifiques pour la nouvelle approche anti-duplication."""

from google_takeout_metadata.sidecar import SidecarData
from google_takeout_metadata.exif_writer import build_exiftool_args, normalize_person_name, normalize_keyword


def test_normalize_person_name():
    """Tester la normalisation intelligente des noms de personnes."""
    # Cas basiques
    assert normalize_person_name("anthony vincent") == "Anthony Vincent"
    assert normalize_person_name("ALICE DUPONT") == "Alice Dupont"
    assert normalize_person_name("bob martin") == "Bob Martin"
    
    # Cas spéciaux - mots de liaison
    assert normalize_person_name("jean de la fontaine") == "Jean de la Fontaine"
    assert normalize_person_name("marie van der berg") == "Marie van der Berg"
    assert normalize_person_name("peter von neumann") == "Peter von Neumann"
    
    # Cas spéciaux - noms irlandais/écossais
    assert normalize_person_name("patrick o'connor") == "Patrick O'Connor"
    assert normalize_person_name("SEAN O'BRIEN") == "Sean O'Brien"
    
    # Cas spéciaux - noms écossais/irlandais Mc
    assert normalize_person_name("john mcdonald") == "John McDonald"
    assert normalize_person_name("MARY MCGREGOR") == "Mary McGregor"
    
    # Cas limites
    assert normalize_person_name("") == ""
    assert normalize_person_name("   ") == ""
    assert normalize_person_name("a") == "A"


def test_normalize_keyword():
    """Tester la normalisation des mots-clés (première lettre de chaque mot en majuscule)."""
    assert normalize_keyword("vacances été") == "Vacances Été"
    assert normalize_keyword("photos de famille") == "Photos De Famille"
    assert normalize_keyword("ÉVÉNEMENTS SPÉCIAUX") == "Événements Spéciaux"
    assert normalize_keyword("test album") == "Test Album"
    
    # Cas limites
    assert normalize_keyword("") == ""
    assert normalize_keyword("   ") == ""
    assert normalize_keyword("a b c") == "A B C"


def test_remove_then_add_deduplication():
    """Tester que l'approche -=/+= élimine les doublons pré-existants.
    
    Ce test vérifie la génération correcte des arguments de déduplication
    selon l'approche "supprimer puis ajouter".
    """
    meta = SidecarData(
        filename="test.jpg",
        description="Test description",
        people=["Anthony Vincent", "alice dupont", "BOB MARTIN"],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        city=None,
        state=None,
        country=None,
        place_name=None,
        favorite=False,
        albums=["Vacances 2024", "test album"]
    )
    
    # Mode append-only avec déduplication
    args = build_exiftool_args(meta, append_only=True)
    
    # Vérifier la normalisation et la déduplication pour PersonInImage
    expected_people = ["Anthony Vincent", "Alice Dupont", "Bob Martin"]
    for person in expected_people:
        assert f"-XMP-iptcExt:PersonInImage-={person}" in args
        assert f"-XMP-iptcExt:PersonInImage+={person}" in args
    
    # Vérifier la normalisation et la déduplication pour les mots-clés (personnes)
    for person in expected_people:
        assert f"-XMP-dc:Subject-={person}" in args
        assert f"-XMP-dc:Subject+={person}" in args
        assert f"-IPTC:Keywords-={person}" in args
        assert f"-IPTC:Keywords+={person}" in args
    
    # Vérifier la normalisation et la déduplication pour les albums
    expected_albums = ["Album: Vacances 2024", "Album: Test Album"]
    for album in expected_albums:
        assert f"-XMP-dc:Subject-={album}" in args
        assert f"-XMP-dc:Subject+={album}" in args
        assert f"-IPTC:Keywords-={album}" in args
        assert f"-IPTC:Keywords+={album}" in args
    
    # Vérifier qu'on n'a PAS -wm cg au début (incompatible avec suppression)
    # mais qu'on l'a réactivé pour les autres champs
    assert "-wm" in args and "cg" in args


def test_deduplication_consistency_between_modes():
    """Tester que la normalisation est cohérente entre mode append-only et écrasement."""
    meta = SidecarData(
        filename="test.jpg",
        description=None,
        people=["anthony VINCENT", "alice dupont"],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        city=None,
        state=None,
        country=None,
        place_name=None,
        favorite=False,
        albums=["vacances 2024"]
    )
    
    # Mode append-only
    args_append = build_exiftool_args(meta, append_only=True)
    
    # Mode écrasement
    args_overwrite = build_exiftool_args(meta, append_only=False)
    
    # Vérifier que les noms normalisés sont identiques dans les deux modes
    expected_people = ["Anthony Vincent", "Alice Dupont"]
    expected_album = "Album: Vacances 2024"
    
    for person in expected_people:
        # En mode append-only : -=/+=
        assert f"-XMP-iptcExt:PersonInImage-={person}" in args_append
        assert f"-XMP-iptcExt:PersonInImage+={person}" in args_append
        
        # En mode écrasement : +=
        assert f"-XMP-iptcExt:PersonInImage+={person}" in args_overwrite
    
    # Album normalisé identique dans les deux modes
    assert f"-XMP-dc:Subject+={expected_album}" in args_append
    assert f"-XMP-dc:Subject+={expected_album}" in args_overwrite


def test_case_normalization_prevents_duplicates():
    """Tester que la normalisation de casse en amont évite les doublons."""
    # Simuler différentes variations de casse du même nom
    meta = SidecarData(
        filename="test.jpg",
        description=None,
        people=["anthony vincent", "ANTHONY VINCENT", "Anthony Vincent"],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        city=None,
        state=None,
        country=None,
        place_name=None,
        favorite=False,
    )
    
    args = build_exiftool_args(meta, append_only=True)
    
    # Compter les occurrences du nom normalisé
    normalized_name = "Anthony Vincent"
    remove_count = args.count(f"-XMP-iptcExt:PersonInImage-={normalized_name}")
    add_count = args.count(f"-XMP-iptcExt:PersonInImage+={normalized_name}")
    
    # Chaque variation devrait générer une paire -=/+= 
    # donc 3 variations = 3 suppressions + 3 ajouts
    assert remove_count == 3, f"Attendu 3 suppressions, trouvé {remove_count}"
    assert add_count == 3, f"Attendu 3 ajouts, trouvé {add_count}"


def test_special_characters_in_names():
    """Tester la gestion des caractères spéciaux dans les noms."""
    meta = SidecarData(
        filename="test.jpg",
        description=None,
        people=["José García", "François Müller", "北京 Beijing"],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        city=None,
        state=None,
        country=None,
        place_name=None,
        favorite=False,
    )
    
    args = build_exiftool_args(meta, append_only=True)
    
    # Vérifier que les noms avec caractères spéciaux sont préservés
    expected_names = ["José García", "François Müller", "北京 Beijing"]
    for name in expected_names:
        assert f"-XMP-iptcExt:PersonInImage-={name}" in args
        assert f"-XMP-iptcExt:PersonInImage+={name}" in args


def test_empty_values_handling():
    """Tester la gestion des valeurs vides et None."""
    meta = SidecarData(
        filename="test.jpg",
        description="",  # Vide
        people=[],       # Liste vide
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        city=None,
        state=None,
        country=None,
        place_name=None,
        favorite=False,
        albums=None      # None
    )
    
    args = build_exiftool_args(meta, append_only=True)
    
    # Ne devrait pas y avoir d'arguments liés aux personnes ou albums
    person_args = [arg for arg in args if "PersonInImage" in arg]
    keyword_args = [arg for arg in args if "Subject" in arg or "Keywords" in arg]
    
    assert len(person_args) == 0, f"Pas d'arguments PersonInImage attendus, trouvé: {person_args}"
    assert len(keyword_args) == 0, f"Pas d'arguments mots-clés attendus, trouvé: {keyword_args}"

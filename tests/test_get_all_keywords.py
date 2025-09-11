"""
Tests pour la fonction get_all_keywords et la cohérence du traitement de local_folder_name.
"""

from google_takeout_metadata.sidecar import SidecarData
from google_takeout_metadata.exif_writer import get_all_keywords, build_people_keywords_args


def test_get_all_keywords_basic():
    """Test de base pour get_all_keywords avec personnes et albums."""
    meta = SidecarData(
        filename="test.jpg",
        description=None,
        people=["alice dupont", "jean de la fontaine"],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        city=None,
        state=None,
        country=None,
        place_name=None,
        albums=["vacances été", "photos famille"]
    )
    
    keywords = get_all_keywords(meta)
    
    expected = [
        "Alice Dupont",  # personne normalisée
        "Jean de la Fontaine",  # personne normalisée (particules en minuscules)
        "Album: Vacances Été",  # album préfixé et normalisé
        "Album: Photos Famille"  # album préfixé et normalisé
    ]
    
    assert keywords == expected


def test_get_all_keywords_empty():
    """Test avec métadonnées vides."""
    meta = SidecarData(
        filename="test.jpg",
        description=None,
        people=[],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None
    )
    keywords = get_all_keywords(meta)
    assert keywords == []


def test_get_all_keywords_people_only():
    """Test avec seulement des personnes."""
    meta = SidecarData(
        filename="test.jpg",
        description=None,
        people=["patrick o'connor", "john mcdonald"],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None
    )
    
    keywords = get_all_keywords(meta)
    
    expected = ["Patrick O'Connor", "John McDonald"]
    assert keywords == expected


def test_get_all_keywords_albums_only():
    """Test avec seulement des albums."""
    meta = SidecarData(
        filename="test.jpg",
        description=None,
        people=[],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        city=None,
        state=None,
        country=None,
        place_name=None,
        albums=["ÉVÉNEMENTS SPÉCIAUX", "voyage 2024"]
    )
    
    keywords = get_all_keywords(meta)
    
    expected = ["Album: Événements Spéciaux", "Album: Voyage 2024"]
    assert keywords == expected


def test_get_all_keywords_excludes_local_folder_name():
    """Test que local_folder_name n'est PAS inclus dans les mots-clés."""
    meta = SidecarData(
        filename="test.jpg",
        description=None,
        people=["Alice"],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        city=None,
        state=None,
        country=None,
        place_name=None,
        albums=["Vacances"],
        local_folder_name="Instagram"  # Ne doit PAS apparaître dans les keywords
    )
    
    keywords = get_all_keywords(meta)
    
    expected = ["Alice", "Album: Vacances"]
    assert keywords == expected
    
    # Vérifier explicitement que Instagram n'est pas traité comme album
    assert "Album: Instagram" not in keywords
    assert "Instagram" not in keywords


def test_build_people_keywords_args_uses_get_all_keywords():
    """Test que build_people_keywords_args utilise get_all_keywords correctement."""
    meta = SidecarData(
        filename="test.jpg",
        description=None,
        people=["alice dupont"],
        taken_at=None,
        created_at=None,
        latitude=None,
        longitude=None,
        altitude=None,
        city=None,
        state=None,
        country=None,
        place_name=None,
        albums=["vacances"],
        local_folder_name="WhatsApp"  # Ne doit pas affecter les keywords
    )
    
    args = build_people_keywords_args(meta)
    
    # Vérifier que les arguments contiennent les mots-clés attendus
    args_str = " ".join(args)
    assert "Alice Dupont" in args_str
    assert "Album: Vacances" in args_str
    
    # Vérifier que local_folder_name n'est PAS traité comme album
    assert "Album: WhatsApp" not in args_str
    assert "WhatsApp" not in args_str


if __name__ == "__main__":
    test_get_all_keywords_basic()
    test_get_all_keywords_empty()
    test_get_all_keywords_people_only()
    test_get_all_keywords_albums_only()
    test_get_all_keywords_excludes_local_folder_name()
    test_build_people_keywords_args_uses_get_all_keywords()
    print("✅ Tous les tests get_all_keywords passent !")

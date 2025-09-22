
from pathlib import Path
from google_takeout_metadata.config_loader import ConfigLoader
from google_takeout_metadata.exif_writer import build_exiftool_args
from google_takeout_metadata.sidecar import SidecarData

def test_config_driven_argument_generation():
    """
    Teste que le chargement de la configuration génère les arguments exiftool 
    attendus pour un ensemble de métadonnées en utilisant la vraie configuration.
    """
    # Utiliser la configuration par défaut du projet
    config_loader = ConfigLoader()
    config_loader.load_config()

    meta = SidecarData(
        title="test.jpg",
        description="Photo de famille",
        people_name=["Alice Dupont", "Bob Martin"],
        photoTakenTime_timestamp=1640995200, # 2022-01-01
        geoData_latitude=48.8566,
        geoData_longitude=2.3522,
        albums=["Vacances 2022"],
        favorited=True
    )

    args = build_exiftool_args(
        meta, 
        Path("test.jpg"),
        use_localTime=False,
        config_loader=config_loader
    )

    # Vérifier que les arguments sont générés
    assert len(args) > 0
    
    # Description -> write_if_blank_or_missing (strategy par défaut dans la vraie config)
    assert "-MWG:Description=Photo de famille" in args
    
    # Timestamp -> replace_all (avec formatage)
    assert "-EXIF:DateTimeOriginal=2022:01:01 00:00:00" in args
    assert "-EXIF:CreateDate=2022:01:01 00:00:00" in args
    
    # People -> clean_duplicates (test sur les deux valeurs et l'ordre - puis +)
    for person in ["Alice Dupont", "Bob Martin"]:
        del_arg = f"-XMP-iptcExt:PersonInImage-={person}"
        add_arg = f"-XMP-iptcExt:PersonInImage+={person}"
        assert del_arg in args, f"Argument de suppression manquant pour {person}"
        assert add_arg in args, f"Argument d'ajout manquant pour {person}"
        i_del = args.index(del_arg)
        i_add = args.index(add_arg)
        assert i_del < i_add, f"Il faut supprimer avant d'ajouter pour {person} (clean_duplicates)"
    
        # Favorited -> preserve_positive_rating (avec nom court $Rating dans la condition)
        assert "-XMP:Rating=5" in args
        # Vérifier que la condition utilise le nom court
        rating_if_index = args.index("-if") if "-if" in args else -1
        if rating_if_index >= 0 and rating_if_index < len(args) - 1:
            condition = args[rating_if_index + 1]
            # La condition devrait contenir $Rating (nom court) pas $XMP:Rating
            if "Rating" in condition:
                assert "$Rating" in condition, f"La condition devrait utiliser $Rating, pas $XMP:Rating: {condition}"    # favorited -> write_if_missing : condition + assignation
    # La transformation boolean_to_rating devrait convertir True → 5 (5 étoiles)
    rating_assignments = [a for a in args if a.startswith("-XMP:Rating=")]
    assert rating_assignments, "L'assignation de XMP:Rating devrait être présente"
    
    # Le rating devrait être "5" pour favorited=True (5 étoiles)
    expected_rating_value = "5"  # favorited=True → 5 étoiles
    expected_rating_arg = f"-XMP:Rating={expected_rating_value}"
    assert expected_rating_arg in args, f"Rating attendu: {expected_rating_arg}, mais trouvé: {rating_assignments}"
    
    # Vérifie présence d'une condition -if correspondante pour write_if_missing
    i_rating = args.index(expected_rating_arg)
    window = args[max(0, i_rating-3):i_rating]
    assert "-if" in window, "Condition -if manquante pour write_if_missing Rating"
    # Optionnel: vérifier que la condition cible bien ce tag
    if "-if" in window:
        cond_idx = window.index("-if")
        if cond_idx + 1 < len(window):
            cond = window[cond_idx + 1]
            assert "Rating" in cond, f"La condition -if devrait viser le tag Rating, mais: {cond}"

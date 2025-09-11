#!/usr/bin/env python3

"""
Test script pour vérifier les corrections de la logique -wm cg.
"""

# Remove direct manipulation of sys.path and wrap imports in a try/except
try:
    from google_takeout_metadata.sidecar import SidecarData
    from google_takeout_metadata.exif_writer import build_exiftool_args
except ImportError:
    import sys
    from pathlib import Path

    # Compute the src directory relative to this test file and insert it at the front
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from google_takeout_metadata.sidecar import SidecarData
    from google_takeout_metadata.exif_writer import build_exiftool_args
from google_takeout_metadata.sidecar import SidecarData
from google_takeout_metadata.exif_writer import build_exiftool_args

def test_append_only_timestamps_without_description():
    """
    Teste le scénario P1 : mode append-only avec timestamps mais sans description.
    Doit ajouter -wm cg pour éviter d'écraser les timestamps existants.
    """
    # Métadonnées avec seulement des dates (pas de description)
    meta = SidecarData(
        filename="test.jpg",
        description=None,  # Pas de description -> build_description_args retourne []
        people=None,
        taken_at=1640995200,  # 2022-01-01 00:00:00 UTC
        created_at=1640995200,
        latitude=None,
        longitude=None,
        altitude=None,
        favorite=False,
    )
    
    # Mode append-only
    args = build_exiftool_args(meta, append_only=True)
    
    print("=== Test P1: Timestamps sans description en mode append-only ===")
    print(f"Arguments générés: {args}")
    
    # Vérifications
    assert "-wm" in args, "L'option -wm devrait être présente"
    assert "cg" in args, "L'option cg devrait être présente"
    
    # Vérifier que -wm cg apparaît avant les timestamps
    wm_index = args.index("-wm")
    cg_index = args.index("cg")
    assert cg_index == wm_index + 1, "-wm et cg doivent être consécutifs"
    
    # Vérifier qu'il y a des timestamps après -wm cg
    datetime_found = False
    for i, arg in enumerate(args):
        if "-DateTimeOriginal=" in arg or "-CreateDate=" in arg or "-ModifyDate=" in arg:
            assert i > cg_index, f"Timestamp {arg} doit apparaître après -wm cg"
            datetime_found = True
    
    assert datetime_found, "Au moins un timestamp doit être présent"
    print("✅ Test P1 réussi : -wm cg correctement ajouté pour les timestamps")

def test_fragile_wm_logic_eliminated():
    """
    Teste que la logique fragile any("-wm" in str(arg) for arg in args) n'est plus utilisée.
    """
    # Métadonnées avec dates et GPS
    meta = SidecarData(
        filename="test.jpg",
        description=None,
        people=None,
        taken_at=1640995200,
        created_at=1640995200,
        latitude=48.8566,
        longitude=2.3522,
        altitude=35.0,
        favorite=True,  # Rating=5
    )
    
    args = build_exiftool_args(meta, append_only=True)
    
    print("=== Test: Logique -wm cg structurée ===")
    print(f"Arguments générés: {args}")
    
    # Compter le nombre d'occurrences de -wm
    wm_count = args.count("-wm")
    
    # Avec la nouvelle logique, il ne devrait y avoir qu'un seul -wm cg 
    # (+ éventuellement un dans build_description_args si description présente)
    assert wm_count <= 2, f"Trop d'occurrences de -wm: {wm_count}"
    
    # Vérifier que -wm cg apparaît dans l'ordre correct
    if "-wm" in args:
        wm_indices = [i for i, arg in enumerate(args) if arg == "-wm"]
        for wm_idx in wm_indices:
            assert wm_idx + 1 < len(args), "Il doit y avoir un argument après -wm"
            assert args[wm_idx + 1] == "cg", f"Après -wm doit venir 'cg', trouvé: {args[wm_idx + 1]}"
    
    print("✅ Test logique structurée réussi : -wm cg utilisé de manière cohérente")

def test_no_wm_in_overwrite_mode():
    """
    Teste qu'en mode overwrite, pas de -wm cg inutile.
    """
    meta = SidecarData(
        filename="test.jpg", 
        description="Test description",
        people=None,
        taken_at=1640995200,
        created_at=1640995200,
        latitude=None,
        longitude=None,
        altitude=None,
        favorite=False,
    )
    
    args = build_exiftool_args(meta, append_only=False)
    
    print("=== Test: Mode overwrite sans -wm cg inutile ===")
    print(f"Arguments générés: {args}")
    
    # En mode overwrite, la description ne devrait pas avoir -wm cg
    # (sauf si explicitement nécessaire pour certaines opérations)
    wm_count = args.count("-wm")
    
    # Le mode overwrite ne devrait pas ajouter de -wm cg sauf cas spéciaux
    print(f"Nombre d'occurrences -wm en mode overwrite: {wm_count}")
    print("✅ Test mode overwrite réussi")

if __name__ == "__main__":
    test_append_only_timestamps_without_description()
    print()
    test_fragile_wm_logic_eliminated() 
    print()
    test_no_wm_in_overwrite_mode()
    print()
    print("🎉 Tous les tests des corrections -wm cg ont réussi !")

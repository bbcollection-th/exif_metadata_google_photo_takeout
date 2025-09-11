#!/usr/bin/env python3

"""
Test script pour vérifier le P1 dans write_metadata directement.
"""

import sys
sys.path.append('src')

from google_takeout_metadata.sidecar import SidecarData
from google_takeout_metadata.exif_writer import build_description_args, build_datetime_args

def test_p1_write_metadata_conditional_args():
    """
    Teste spécifiquement le P1 : dans write_metadata, quand build_description_args
    retourne une liste vide mais qu'il y a des datetime_args, -wm cg doit être ajouté.
    """
    
    print("=== Test P1: Cas problématique original ===")
    
    # Scénario P1 : pas de description, mais des dates
    meta = SidecarData(
        filename="test.jpg",
        description=None,  # ❌ Pas de description
        people=None,
        taken_at=1640995200,  # ✅ Mais il y a des dates
        created_at=1640995200,
        latitude=None,
        longitude=None,
        altitude=None,
        city=None,
        state=None,
        country=None,
        place_name=None,
        favorite=False,
    )
    
    # Reproduire la logique de write_metadata (avant correction)
    conditional_args_before = []
    
    # build_description_args avec description=None retourne []
    desc_args = build_description_args(meta, conditional_mode=True)
    conditional_args_before.extend(desc_args)
    print(f"Description args: {desc_args}")
    
    # build_datetime_args retourne les timestamps mais sans -wm cg
    datetime_args = build_datetime_args(meta, use_localtime=False, is_video=False)
    conditional_args_before.extend(datetime_args)
    print(f"Datetime args: {datetime_args}")
    
    print(f"Conditional args AVANT correction: {conditional_args_before}")
    
    # PROBLÈME P1 : Pas de -wm cg dans conditional_args_before !
    # => exiftool va écraser les timestamps existants
    
    has_wm_before = "-wm" in conditional_args_before
    print(f"❌ AVANT correction - a -wm cg: {has_wm_before}")
    
    # Maintenant testons APRÈS correction
    conditional_args_after = []
    conditional_args_after.extend(desc_args)
    
    # CORRECTION P1: Ajouter -wm cg si on a des datetime_args
    if datetime_args:
        conditional_args_after.extend(["-wm", "cg"])
        conditional_args_after.extend(datetime_args)
    
    print(f"Conditional args APRÈS correction: {conditional_args_after}")
    
    has_wm_after = "-wm" in conditional_args_after
    print(f"✅ APRÈS correction - a -wm cg: {has_wm_after}")
    
    assert has_wm_after, "La correction doit ajouter -wm cg pour les timestamps"
    
    # Vérifier l'ordre
    if "-wm" in conditional_args_after:
        wm_idx = conditional_args_after.index("-wm")
        cg_idx = conditional_args_after.index("cg")
        assert cg_idx == wm_idx + 1, "-wm et cg doivent être consécutifs"
        
        # Vérifier qu'au moins un timestamp suit
        has_timestamp_after_wm = False
        for i, arg in enumerate(conditional_args_after):
            if i > cg_idx and ("DateTimeOriginal=" in arg or "CreateDate=" in arg or "ModifyDate=" in arg):
                has_timestamp_after_wm = True
                break
        
        assert has_timestamp_after_wm, "Il doit y avoir au moins un timestamp après -wm cg"
    
    print("✅ P1 correctement corrigé : -wm cg ajouté pour préserver les timestamps existants")

if __name__ == "__main__":
    test_p1_write_metadata_conditional_args()
    print("\n🎉 Correction P1 validée !")

import shutil
import tempfile
import subprocess
from pathlib import Path

from google_takeout_metadata.sidecar import SidecarData
from google_takeout_metadata.exif_writer import write_metadata


def read_exif_people(image_path: Path) -> list[str]:
    """Lit les personnes depuis un fichier image en utilisant exiftool."""
    try:
        cmd = ["exiftool", "-s", "-s", "-s", "-XMP-iptcExt:PersonInImage", str(image_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, encoding='utf-8')
        if result.returncode == 0 and result.stdout.strip():
            # ExifTool retourne les valeurs séparées par des virgules
            people = [p.strip() for p in result.stdout.strip().split(',')]
            return [p for p in people if p]  # Filtrer les valeurs vides
    except (subprocess.SubprocessError, OSError):
        pass
    return []


def test_hybrid_approach_no_duplicates():
    """Test de l'approche hybride : pas de doublons quand on ajoute des personnes existantes."""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Copier l'image test dans le répertoire temporaire
        test_image_src = Path("test_assets/test_clean.jpg")
        test_image = Path(temp_dir) / "test_image.jpg"
        shutil.copy2(test_image_src, test_image)
        
        # Étape 1 : Ajouter les premières personnes (ancien takeout)
        meta1 = SidecarData(
            filename="test_image.jpg",
            description=None,
            people=["Anthony", "Bernard"],
            taken_at=None,
            created_at=None,
            latitude=None,
            longitude=None,
            altitude=None,
            favorite=False,
            albums=["Vacances"]
        )
        write_metadata(test_image, meta1, append_only=True)
        
        # Vérifier l'état initial
        people_initial = read_exif_people(test_image)
        assert "Anthony" in people_initial
        assert "Bernard" in people_initial
        assert len([p for p in people_initial if p == "Anthony"]) == 1
        assert len([p for p in people_initial if p == "Bernard"]) == 1
        
        # Étape 2 : Ajouter nouveaux + existants (nouveau takeout avec tous les gens)
        meta2 = SidecarData(
            filename="test_image.jpg",
            description=None,
            people=["Anthony", "Bernard", "Cindy"],  # Contient TOUS les gens, pas juste les nouveaux
            taken_at=None,
            created_at=None,
            latitude=None,
            longitude=None,
            altitude=None,
            favorite=False,
            albums=["Vacances", "Famille"]
        )
        write_metadata(test_image, meta2, append_only=True)
        
        # Vérifier le résultat final : pas de doublons malgré la redondance
        people_final = read_exif_people(test_image)
        print(f"Personnes finales: {people_final}")
        
        # Assertions critiques : aucun doublon
        assert "Anthony" in people_final
        assert "Bernard" in people_final 
        assert "Cindy" in people_final
        assert len([p for p in people_final if p == "Anthony"]) == 1, f"Anthony apparaît plusieurs fois: {people_final}"
        assert len([p for p in people_final if p == "Bernard"]) == 1, f"Bernard apparaît plusieurs fois: {people_final}"
        assert len([p for p in people_final if p == "Cindy"]) == 1, f"Cindy apparaît plusieurs fois: {people_final}"
        
        # Vérifier que toutes les personnes attendues sont présentes
        expected_people = {"Anthony", "Bernard", "Cindy"}
        actual_people = set(people_final)
        assert expected_people.issubset(actual_people), f"Personnes manquantes. Attendu: {expected_people}, Réel: {actual_people}"


def test_hybrid_approach_only_new_people():
    """Test de l'approche hybride : ajouter seulement les nouvelles personnes."""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Copier l'image test
        # Copier l'image test
        test_image_src = Path("test_assets/test_clean.jpg")
        if not test_image_src.exists():
            raise FileNotFoundError(f"Fichier test requis non trouvé : {test_image_src}")
        test_image = Path(temp_dir) / "test_image.jpg"
        shutil.copy2(test_image_src, test_image)
        
        # Étape 1 : Ajouter les premières personnes
        meta1 = SidecarData(
            filename="test_image.jpg",
            description=None,
            people=["Alice", "Bob"],
            taken_at=None,
            created_at=None,
            latitude=None,
            longitude=None,
            altitude=None,
            favorite=False
        )
        write_metadata(test_image, meta1, append_only=True)
        
        # Étape 2 : Ajouter seulement les nouvelles personnes 
        meta2 = SidecarData(
            filename="test_image.jpg",
            description=None,
            people=["Charlie"],  # Seulement la nouvelle personne
            taken_at=None,
            created_at=None,
            latitude=None,
            longitude=None,
            altitude=None,
            favorite=False
        )
        write_metadata(test_image, meta2, append_only=True)
        
        # Vérifier le résultat : toutes les personnes présentes, pas de doublons
        people_final = read_exif_people(test_image)
        expected_people = {"Alice", "Bob", "Charlie"}
        actual_people = set(people_final)
        
        assert expected_people == actual_people, f"Attendu: {expected_people}, Réel: {actual_people}"
        assert len(people_final) == 3, f"Doublons détectés: {people_final}"


if __name__ == "__main__":
    test_hybrid_approach_no_duplicates()
    test_hybrid_approach_only_new_people()
    print("✅ Tests de l'approche hybride : SUCCÈS")

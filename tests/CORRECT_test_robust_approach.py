import shutil
import tempfile
import subprocess
from pathlib import Path

from google_takeout_metadata.sidecar import SidecarData
from google_takeout_metadata.exif_writer import write_metadata


def read_exif_people_name(image_path: Path) -> list[str]:
    """Lit les personnes depuis un fichier image en utilisant exiftool."""
    try:
        cmd = ["exiftool", "-s", "-s", "-s", "-XMP-iptcExt:PersonInImage", str(image_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, encoding='utf-8')
        if result.returncode == 0 and result.stdout.strip():
            # ExifTool retourne les valeurs séparées par des virgules
            people_name = [p.strip() for p in result.stdout.strip().split(',')]
            return [p for p in people_name if p]  # Filtrer les valeurs vides
    except (subprocess.SubprocessError, OSError):
        pass
    return []


def test_robust_approach_no_duplicates():
    """Test de l'approche robuste (remove-then-add) : pas de doublons quand on ajoute des personnes existantes."""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Copier l'image test dans le répertoire temporaire
        test_image_src = Path("test_assets/test_clean.jpg")
        test_image = Path(temp_dir) / "test_image.jpg"
        shutil.copy2(test_image_src, test_image)
        
        # Étape 1 : Ajouter les premières personnes (ancien takeout)
        meta1 = SidecarData(
            title="test_image.jpg",
            description=None,
            people_name=["Anthony", "Bernard"],
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
            albums=["Vacances"]
        )
        write_metadata(test_image, meta1, append_only=True)
        
        # Vérifier l'état initial
        people_name_initial = read_exif_people_name(test_image)
        assert "Anthony" in people_name_initial
        assert "Bernard" in people_name_initial
        assert len([p for p in people_name_initial if p == "Anthony"]) == 1
        assert len([p for p in people_name_initial if p == "Bernard"]) == 1
        
        # Étape 2 : Ajouter nouveaux + existants (nouveau takeout avec tous les gens)
        meta2 = SidecarData(
            title="test_image.jpg",
            description=None,
            people_name=["Anthony", "Bernard", "Cindy"],  # Contient TOUS les gens, pas juste les nouveaux
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
            albums=["Vacances", "Famille"]
        )
        write_metadata(test_image, meta2, append_only=True)
        
        # Vérifier le résultat final : pas de doublons malgré la redondance
        people_name_final = read_exif_people_name(test_image)
        print(f"Personnes finales: {people_name_final}")
        
        # Assertions critiques : aucun doublon
        assert "Anthony" in people_name_final
        assert "Bernard" in people_name_final 
        assert "Cindy" in people_name_final
        assert len([p for p in people_name_final if p == "Anthony"]) == 1, f"Anthony apparaît plusieurs fois: {people_name_final}"
        assert len([p for p in people_name_final if p == "Bernard"]) == 1, f"Bernard apparaît plusieurs fois: {people_name_final}"
        assert len([p for p in people_name_final if p == "Cindy"]) == 1, f"Cindy apparaît plusieurs fois: {people_name_final}"
        
        # Vérifier que toutes les personnes attendues sont présentes
        expected_people_name = {"Anthony", "Bernard", "Cindy"}
        actual_people_name = set(people_name_final)
        assert expected_people_name.issubset(actual_people_name), f"Personnes manquantes. Attendu: {expected_people_name}, Réel: {actual_people_name}"


def test_robust_approach_only_new_people_name():
    """Test de l'approche robuste (remove-then-add) : ajouter seulement les nouvelles personnes."""
    
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
            title="test_image.jpg",
            description=None,
            people_name=["Alice", "Bob"],
            photoTakenTime_timestamp=None,
            creationTime_timestamp=None,
            geoData_latitude=None,
            geoData_longitude=None,
            geoData_altitude=None,
            city=None,
            state=None,
            country=None,
            place_name=None,
            favorited=False
        )
        write_metadata(test_image, meta1, append_only=True)
        
        # Étape 2 : Ajouter seulement les nouvelles personnes 
        meta2 = SidecarData(
            title="test_image.jpg",
            description=None,
            people_name=["Charlie"],  # Seulement la nouvelle personne
            photoTakenTime_timestamp=None,
            creationTime_timestamp=None,
            geoData_latitude=None,
            geoData_longitude=None,
            geoData_altitude=None,
            city=None,
            state=None,
            country=None,
            place_name=None,
            favorited=False
        )
        write_metadata(test_image, meta2, append_only=True)
        
        # Vérifier le résultat : toutes les personnes présentes, pas de doublons
        people_name_final = read_exif_people_name(test_image)
        expected_people_name = {"Alice", "Bob", "Charlie"}
        actual_people_name = set(people_name_final)
        
        assert expected_people_name == actual_people_name, f"Attendu: {expected_people_name}, Réel: {actual_people_name}"
        assert len(people_name_final) == 3, f"Doublons détectés: {people_name_final}"


if __name__ == "__main__":
    test_robust_approach_no_duplicates()
    test_robust_approach_only_new_people_name()
    print("✅ Tests de l'approche robuste (remove-then-add) : SUCCÈS")

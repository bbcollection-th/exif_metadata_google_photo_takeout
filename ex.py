import subprocess
import json
from pathlib import Path
import tempfile
from PIL import Image

def run_exiftool(args: list[str]) -> subprocess.CompletedProcess:
    """Exécute une commande exiftool et gère les erreurs."""
    try:
        # Ajout de l'argument pour écraser le fichier original pour la simplicité du test
        full_cmd = ["exiftool", "-overwrite_original"] + args
        print(f"\n▶️ Exécution de la commande :\n  {' '.join(full_cmd)}")
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8'
        )
        print("✅ Commande exécutée avec succès.")
        if result.stdout.strip():
            print(f"   Sortie: {result.stdout.strip()}")
        return result
    except FileNotFoundError:
        print("ERREUR: La commande 'exiftool' est introuvable. Assurez-vous qu'elle est installée et dans le PATH.")
        raise
    except subprocess.CalledProcessError as e:
        print(f"❌ ERREUR lors de l'exécution d'ExifTool (code {e.returncode})")
        print(f"   STDOUT: {e.stdout}")
        print(f"   STDERR: {e.stderr}")
        raise

def read_metadata(image_path: Path) -> dict:
    """Lit les métadonnées d'une image et les retourne en format JSON."""
    result = run_exiftool(["-j", "-g1", str(image_path)])
    # ExifTool retourne une liste contenant un dictionnaire
    return json.loads(result.stdout)[0]

# --- DÉBUT DU TEST ---
# Utiliser un répertoire temporaire pour ne pas laisser de fichiers derrière
with tempfile.TemporaryDirectory() as temp_dir:
    temp_dir_path = Path(temp_dir)
    test_image_path = temp_dir_path / "test_image.jpg"

    print(f"Création de l'image de test : {test_image_path}")
    Image.new('RGB', (10, 10), color='blue').save(test_image_path)

    # --- ÉTAPE 1 : Écrire les métadonnées initiales ---
    print("\n--- ÉTAPE 1 : Écriture des métadonnées initiales ---")
    initial_people = ["Alice", "Bob L'éponge"] # Personnes initiales, dont une avec un espace
    initial_write_args = []
    for person in initial_people:
        initial_write_args.extend(["-XMP-iptcExt:PersonInImage+=", person])
    initial_write_args.append(str(test_image_path))
    
    run_exiftool(initial_write_args)

    # --- ÉTAPE 2 : Vérifier les métadonnées initiales ---
    print("\n--- ÉTAPE 2 : Vérification des métadonnées initiales ---")
    metadata_after_initial_write = read_metadata(test_image_path)
    written_people = metadata_after_initial_write.get("XMP-iptcExt", {}).get("PersonInImage")
    
    print(f"Personnes lues dans le fichier : {written_people}")
    assert written_people == initial_people, f"Échec de l'écriture initiale! Attendu: {initial_people}, Obtenu: {written_people}"
    print("✅ Vérification initiale réussie.")


    # --- ÉTAPE 3 : Construire et exécuter la commande d'ÉCRASEMENT ---
    # C'est la partie cruciale qui utilise la logique "vider puis remplir"
    print("\n--- ÉTAPE 3 : Exécution de la commande d'écrasement (vider puis remplir) ---")
    new_people = ["Charlie", "David"]
    
    overwrite_args = []
    # 1. Vider la liste
    overwrite_args.append("-XMP-iptcExt:PersonInImage=")
    # 2. Remplir la liste avec les nouvelles valeurs
    for person in new_people:
        overwrite_args.extend(["-XMP-iptcExt:PersonInImage+=", person])
    
    overwrite_args.append(str(test_image_path))
    
    run_exiftool(overwrite_args)

    # --- ÉTAPE 4 : Vérifier les métadonnées finales ---
    print("\n--- ÉTAPE 4 : Vérification des métadonnées finales ---")
    final_metadata = read_metadata(test_image_path)
    final_people = final_metadata.get("XMP-iptcExt", {}).get("PersonInImage")
    
    print(f"Personnes finales lues dans le fichier : {final_people}")
    
    # Assertions finales
    assert final_people == new_people, f"La liste finale devrait être {new_people}, mais est {final_people}"
    assert "Alice" not in final_people, "L'ancienne personne 'Alice' est toujours présente !"
    assert "Bob L'éponge" not in final_people, "L'ancienne personne 'Bob L'éponge' est toujours présente !"
    
    print("\n========================================================")
    print("✅ SUCCÈS : Le test prouve que la méthode 'vider puis remplir' fonctionne parfaitement.")
    print("La séquence '-TAG=' suivie de '-TAG+=' a correctement écrasé les anciennes valeurs.")
    print("========================================================")
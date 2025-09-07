"""Module de gestion des statistiques et rapport de synthèse."""

from __future__ import annotations

import logging
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional
import json

logger = logging.getLogger(__name__)


@dataclass
class ProcessingStats:
    """Statistiques de traitement des fichiers."""
    
    # Totaux
    total_sidecars_found: int = 0
    total_processed: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    
    # Par type de fichier
    images_processed: int = 0
    videos_processed: int = 0
    
    # Détails des opérations
    files_fixed_extension: int = 0
    sidecars_cleaned: int = 0
    
    # Listes de détails pour le rapport détaillé
    failed_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    fixed_extensions: List[str] = field(default_factory=list)
    
    # Erreurs par catégorie
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    
    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def start_processing(self) -> None:
        """Marquer le début du traitement."""
        self.start_time = datetime.now()
    
    def end_processing(self) -> None:
        """Marquer la fin du traitement."""
        self.end_time = datetime.now()
    
    @property
    def duration(self) -> Optional[float]:
        """Durée du traitement en secondes."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    @property
    def success_rate(self) -> float:
        """Taux de réussite en pourcentage."""
        if self.total_sidecars_found == 0:
            return 0.0
        return (self.total_processed / self.total_sidecars_found) * 100
    
    def add_processed_file(self, file_path: Path, is_image: bool = True) -> None:
        """Ajouter un fichier traité avec succès."""
        self.total_processed += 1
        if is_image:
            self.images_processed += 1
        else:
            self.videos_processed += 1
    
    def add_failed_file(self, file_path: Path, error_type: str, error_msg: str) -> None:
        """Ajouter un fichier en échec."""
        self.total_failed += 1
        self.failed_files.append(f"{file_path.name}: {error_msg}")
        
        # Compter les erreurs par type
        if error_type in self.errors_by_type:
            self.errors_by_type[error_type] += 1
        else:
            self.errors_by_type[error_type] = 1
    
    def add_skipped_file(self, file_path: Path, reason: str) -> None:
        """Ajouter un fichier ignoré."""
        self.total_skipped += 1
        self.skipped_files.append(f"{file_path.name}: {reason}")
    
    def add_fixed_extension(self, old_name: str, new_name: str) -> None:
        """Ajouter une correction d'extension."""
        self.files_fixed_extension += 1
        self.fixed_extensions.append(f"{old_name} → {new_name}")
    
    def print_console_summary(self) -> None:
        """Afficher un résumé concis dans la console."""
        print("\n" + "="*60)
        print("📊 RÉSUMÉ DU TRAITEMENT")
        print("="*60)
        
        print(f"📁 Fichiers de métadonnées trouvés : {self.total_sidecars_found}")
        print(f"✅ Fichiers traités avec succès : {self.total_processed}")
        
        if self.images_processed > 0 or self.videos_processed > 0:
            print(f"   📸 Images : {self.images_processed}")
            print(f"   🎥 Vidéos : {self.videos_processed}")
        
        if self.total_failed > 0:
            print(f"❌ Fichiers en échec : {self.total_failed}")
            
        if self.total_skipped > 0:
            print(f"⏭️  Fichiers ignorés : {self.total_skipped}")
            
        if self.files_fixed_extension > 0:
            print(f"🔧 Extensions corrigées : {self.files_fixed_extension}")
            
        if self.sidecars_cleaned > 0:
            print(f"🗑️  Fichiers de métadonnées supprimés : {self.sidecars_cleaned}")
        
        # Taux de réussite
        if self.total_sidecars_found > 0:
            print(f"📈 Taux de réussite : {self.success_rate:.1f}%")
        
        # Durée
        if self.duration:
            print(f"⏱️  Durée : {self.duration:.1f}s")
        
        # Erreurs principales
        if self.errors_by_type:
            print(f"\n🔍 Types d'erreurs principales :")
            for error_type, count in sorted(self.errors_by_type.items(), key=lambda x: x[1], reverse=True)[:3]:
                print(f"   • {error_type}: {count} fichier(s)")
                
        print("="*60)
        
        if self.total_failed > 0 or self.total_skipped > 0:
            print("💡 Consultez le fichier de log détaillé pour plus d'informations.")
    
    def save_detailed_report(self, log_file: Path) -> None:
        """Sauvegarder un rapport détaillé dans un fichier spécifique à cette exécution."""
        report = {
            "execution_timestamp": datetime.now().isoformat(),
            "summary": {
                "total_sidecars_found": self.total_sidecars_found,
                "total_processed": self.total_processed,
                "total_failed": self.total_failed,
                "total_skipped": self.total_skipped,
                "images_processed": self.images_processed,
                "videos_processed": self.videos_processed,
                "files_fixed_extension": self.files_fixed_extension,
                "sidecars_cleaned": self.sidecars_cleaned,
                "success_rate": self.success_rate,
                "duration_seconds": self.duration
            },
            "details": {
                "failed_files": self.failed_files,
                "skipped_files": self.skipped_files,
                "fixed_extensions": self.fixed_extensions,
                "errors_by_type": self.errors_by_type
            }
        }
        
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"📄 Rapport détaillé sauvegardé : {log_file}")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du rapport : {e}")


# Instance globale pour les statistiques
stats = ProcessingStats()

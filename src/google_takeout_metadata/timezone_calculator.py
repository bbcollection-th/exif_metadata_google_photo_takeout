#!/usr/bin/env python3
"""
Calculateur de fuseaux horaires et générateur d'arguments ExifTool pour correction temporelle.

Ce module utilise les coordonnées GPS pour déduire le fuseau horaire exact (DST inclus)
et génère les arguments ExifTool appropriés pour corriger les timestamps.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Union
from dataclasses import dataclass

try:
    from timezonefinder import TimezoneFinder
    from zoneinfo import ZoneInfo
    TIMEZONE_SUPPORT = True
except ImportError:
    TIMEZONE_SUPPORT = False
    TimezoneFinder = None
    ZoneInfo = None

logger = logging.getLogger(__name__)

@dataclass
class TimezoneInfo:
    """Information de fuseau horaire calculée"""
    timezone_name: str
    utc_offset_seconds: int
    offset_string: str  # Format "+02:00" ou "-05:00"
    local_datetime: datetime
    is_dst: bool

class TimezoneCalculator:
    """Calculateur de fuseaux horaires à partir de coordonnées GPS"""
    
    def __init__(self):
        if not TIMEZONE_SUPPORT:
            raise ImportError(
                "Les dépendances timezone ne sont pas installées. "
                "Installez avec: pip install timezonefinder"
            )
        self.tf = TimezoneFinder()
    
    def get_timezone_info(self, latitude: float, longitude: float, utc_timestamp: Union[int, datetime]) -> Optional[TimezoneInfo]:
        """
        Calcule l'information de fuseau horaire pour des coordonnées et un timestamp donnés.
        
        Args:
            latitude: Latitude en degrés décimaux
            longitude: Longitude en degrés décimaux  
            utc_timestamp: Timestamp UTC (secondes depuis epoch ou objet datetime)
            
        Returns:
            TimezoneInfo ou None si le calcul échoue
        """
        try:
            # Trouver le nom du fuseau horaire
            timezone_name = self.tf.timezone_at(lng=longitude, lat=latitude)
            if not timezone_name:
                logger.warning(f"Aucun fuseau trouvé pour {latitude}, {longitude}")
                return None
            
            # Créer l'objet datetime UTC selon le type d'entrée
            if isinstance(utc_timestamp, datetime):
                # Si c'est déjà un datetime, l'utiliser (en assumant qu'il est en UTC)
                utc_dt = utc_timestamp.replace(tzinfo=timezone.utc)
            else:
                # Si c'est un timestamp, le convertir
                utc_dt = datetime.fromtimestamp(utc_timestamp, tz=timezone.utc)
            
            # Créer les objets de fuseau horaire
            try:
                tz = ZoneInfo(timezone_name)
                local_dt = utc_dt.astimezone(tz)
            except Exception as e:
                logger.error(f"Erreur ZoneInfo pour {timezone_name}: {e}")
                return None
            
            # Calculer l'offset
            offset_seconds = int(local_dt.utcoffset().total_seconds())
            
            # Formater l'offset pour EXIF (+HH:MM)
            sign = '+' if offset_seconds >= 0 else '-'
            abs_offset = abs(offset_seconds)
            hours = abs_offset // 3600
            minutes = (abs_offset % 3600) // 60
            offset_string = f"{sign}{hours:02d}:{minutes:02d}"
            
            # Détecter DST
            is_dst = local_dt.dst() is not None and local_dt.dst().total_seconds() > 0
            
            return TimezoneInfo(
                timezone_name=timezone_name,
                utc_offset_seconds=offset_seconds,
                offset_string=offset_string,
                local_datetime=local_dt,
                is_dst=is_dst
            )
            
        except Exception as e:
            logger.error(f"Erreur calcul timezone pour {latitude}, {longitude}: {e}")
            return None

class TimezoneExifArgsGenerator:
    """Générateur d'arguments ExifTool pour correction des fuseaux horaires"""
    
    def __init__(self, calculator: TimezoneCalculator):
        self.calculator = calculator
    
    def generate_image_args(self, file_path: Path, timezone_info: TimezoneInfo, 
                          use_absolute_values: bool = True) -> list[str]:
        """
        Génère les arguments ExifTool pour corriger les timestamps d'une image.
        
        Args:
            file_path: Chemin du fichier image
            timezone_info: Information de fuseau horaire  
            use_absolute_values: Si True, écrit des valeurs absolues, sinon utilise globalTimeShift
            
        Returns:
            Liste d'arguments ExifTool
        """
        args = []
        
        if use_absolute_values:
            # Option A: Valeurs absolues (local time + offset)
            local_exif = timezone_info.local_datetime.strftime('%Y:%m:%d %H:%M:%S')
            
            args.extend([
                f'-DateTimeOriginal={local_exif}',
                f'-OffsetTimeOriginal={timezone_info.offset_string}',
                f'-CreateDate={local_exif}',
                f'-OffsetTimeDigitized={timezone_info.offset_string}',
                f'-OffsetTime={timezone_info.offset_string}'
            ])
        else:
            # Option B: Shift global relatif (si les tags sont déjà en UTC)
            # Convertit "+02:00" en "+2:00" format ExifTool
            offset_hours = timezone_info.utc_offset_seconds // 3600
            offset_minutes = (abs(timezone_info.utc_offset_seconds) % 3600) // 60
            sign = '+' if offset_hours >= 0 else '-'
            shift_format = f"{sign}{abs(offset_hours)}:{offset_minutes:02d}"
            
            args.extend([
                '-globalTimeShift', shift_format
            ])
        
        args.extend([
            '-overwrite_original' if not self._backup_enabled() else '',
            str(file_path)
        ])
        
        # Filtrer les arguments vides
        return [arg for arg in args if arg]
    
    def generate_video_args(self, file_path: Path, utc_timestamp: int) -> list[str]:
        """
        Génère les arguments ExifTool pour corriger les timestamps d'une vidéo.
        Les vidéos QuickTime gardent l'UTC avec l'API appropriée.
        
        Args:
            file_path: Chemin du fichier vidéo
            utc_timestamp: Timestamp UTC original
            
        Returns:
            Liste d'arguments ExifTool
        """
        utc_dt = datetime.fromtimestamp(utc_timestamp, tz=timezone.utc)
        utc_exif = utc_dt.strftime('%Y:%m:%d %H:%M:%S')
        
        args = [
            '-api', 'QuickTimeUTC=1',
            f'-QuickTime:CreateDate={utc_exif}',
            f'-QuickTime:ModifyDate={utc_exif}',
            '-TrackCreateDate<QuickTime:CreateDate',
            '-TrackModifyDate<QuickTime:ModifyDate', 
            '-MediaCreateDate<QuickTime:CreateDate',
            '-MediaModifyDate<QuickTime:ModifyDate',
            '-overwrite_original' if not self._backup_enabled() else '',
            str(file_path)
        ]
        
        return [arg for arg in args if arg]
    
    def generate_args_file(self, file_timezone_map: Dict[Path, TimezoneInfo], 
                          output_file: Path) -> None:
        """
        Génère un fichier d'arguments ExifTool pour traitement en lot.
        
        Args:
            file_timezone_map: Mapping fichier -> timezone info
            output_file: Chemin du fichier d'arguments à créer
        """
        lines = []
        
        for file_path, tz_info in file_timezone_map.items():
            if self._is_video_file(file_path):
                # Pour les vidéos, on a besoin du timestamp UTC original
                # Note: Ceci nécessiterait d'être passé séparément 
                logger.warning(f"Traitement vidéo pas encore implémenté dans args_file pour {file_path}")
                continue
            else:
                # Images: valeurs absolues
                file_args = self.generate_image_args(file_path, tz_info, use_absolute_values=True)
                lines.extend(file_args)
                lines.append('-execute')
        
        # Écrire le fichier
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        logger.info(f"Fichier d'arguments généré: {output_file}")
    
    def _is_video_file(self, file_path: Path) -> bool:
        """Vérifie si le fichier est une vidéo"""
        video_extensions = {'.mp4', '.mov', '.m4v', '.3gp', '.avi', '.mkv'}
        return file_path.suffix.lower() in video_extensions
    
    def _backup_enabled(self) -> bool:
        """Vérifie si les backups sont activés dans la config"""
        # Ici on pourrait checker la config globale
        return True

def create_timezone_calculator() -> Optional[TimezoneCalculator]:
    """Factory pour créer un calculateur de timezone avec gestion d'erreur"""
    try:
        return TimezoneCalculator()
    except ImportError as e:
        logger.error(f"Impossible de créer TimezoneCalculator: {e}")
        logger.info("Pour activer le support timezone: pip install timezonefinder")
        return None

# Exemple d'utilisation
if __name__ == "__main__":
    # Test basique
    calc = create_timezone_calculator()
    if calc:
        # Paris en été (DST)
        tz_info = calc.get_timezone_info(48.8566, 2.3522, 1627296896)  # Timestamp d'exemple
        if tz_info:
            print(f"Timezone: {tz_info.timezone_name}")
            print(f"Offset: {tz_info.offset_string}")
            print(f"Local time: {tz_info.local_datetime}")
            print(f"Is DST: {tz_info.is_dst}")
            
            # Générer args pour une image
            generator = TimezoneExifArgsGenerator(calc)
            args = generator.generate_image_args(Path("test.jpg"), tz_info)
            print(f"ExifTool args: {args}")
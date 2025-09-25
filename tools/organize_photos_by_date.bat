@echo off
setlocal EnableDelayedExpansion

echo ========================================
echo  ORGANISATEUR DE PHOTOS PAR DATE
echo ========================================
echo.

REM Vérifier si un dossier a été fourni
if "%~1"=="" (
    echo Usage: %0 "C:\chemin\vers\dossier\photos"
    echo.
    echo Ou glissez-déposez un dossier sur ce fichier batch
    pause
    exit /b 1
)

set "SOURCE_DIR=%~1"

REM Vérifier si le dossier existe
if not exist "%SOURCE_DIR%" (
    echo ERREUR: Le dossier "%SOURCE_DIR%" n'existe pas
    pause
    exit /b 1
)

echo Dossier source: %SOURCE_DIR%
echo.

REM Menu d'options
REM Vérifier que Python est disponible
python --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR: Python non trouvé. Installez Python 3.10+ puis relancez.
    pause
    exit /b 1
)

echo Choisissez une option:
echo 1. Mode simulation (voir ce qui serait fait)
echo 2. Organiser réellement les photos
echo 3. Organiser dans un autre dossier
echo.
set /p choice="Votre choix (1-3): "

if "%choice%"=="1" (
    echo.
    echo === MODE SIMULATION ===
    echo Aucun fichier ne sera déplacé, vous verrez juste un aperçu...
    echo.
    python organize_by_date.py "%SOURCE_DIR%" --dry-run --verbose
    goto :end
) else if "%choice%"=="2" (
    echo.
    echo === ORGANISATION REELLE ===
    echo Les fichiers vont être organisés dans des sous-dossiers AAAA-MM...
    echo AVEC toutes les gestions d'erreurs avancées (permissions, espace disque, etc.)
    echo.
    set /p confirm="Êtes-vous sûr ? (O/N): "
    if /i "!confirm!"=="O" (
        python organize_by_date.py "%SOURCE_DIR%" --verbose
    ) else (
        echo Opération annulée.
    )
    goto :end
) else if "%choice%"=="3" (
    echo.
    set /p target="Dossier de destination: "
    if not "!target!"=="" (
        echo.
        echo === ORGANISATION VERS AUTRE DOSSIER ===
        echo Source: %SOURCE_DIR%
        echo Destination: !target!
        echo.
        set /p confirm="Êtes-vous sûr ? (O/N): "
        if /i "!confirm!"=="O" (
            python organize_by_date.py "%SOURCE_DIR%" --target-dir "!target!" --verbose
        ) else (
            echo Opération annulée.
        )
    )
    goto :end
) else (
    echo Choix invalide
)

:end
echo.
echo Terminé! Appuyez sur une touche pour fermer...
pause >nul
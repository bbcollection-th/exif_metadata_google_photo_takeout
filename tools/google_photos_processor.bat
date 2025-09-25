@echo off
setlocal EnableDelayedExpansion

REM ================================================================
REM Script Batch pour Google Photos Takeout Metadata Processor
REM Point 11 de la checklist : Script glisser-déposer automatique
REM ================================================================

echo.
echo ============================================================
echo   Google Photos Takeout Metadata Processor
echo   Script de traitement automatique
echo ============================================================
echo.

REM Vérification des arguments
if "%~1"=="" (
    echo ❌ Erreur: Glissez-deposez un dossier sur ce script ^(.bat^)
    echo.
    echo 📁 Usage: Faites glisser votre dossier "Google Photos" 
    echo    directement sur ce fichier .bat
    echo.
    echo 🔍 Le dossier doit contenir des fichiers .json Google Photos
    echo.
    pause
    exit /b 1
)

set "INPUT_DIR=%~1"

REM Vérification que c'est bien un dossier
if not exist "%INPUT_DIR%" (
    echo ❌ Erreur: Le chemin n'existe pas: %INPUT_DIR%
    pause
    exit /b 1
)

if not exist "%INPUT_DIR%\*" (
    echo ❌ Erreur: Ce n'est pas un dossier valide: %INPUT_DIR%
    pause
    exit /b 1
)

echo 📁 Dossier source: %INPUT_DIR%
echo.

REM Détection de l'environnement Python
set "PYTHON_CMD="
set "SCRIPT_DIR=%~dp0"

REM 1. Essayer l'environnement virtuel local
if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    set "PYTHON_CMD=%SCRIPT_DIR%.venv\Scripts\python.exe"
    echo ✅ Python trouvé dans l'environnement virtuel local
) else (
    REM 2. Essayer python dans le PATH
    python --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=python"
        echo ✅ Python trouvé dans le PATH système
    ) else (
        echo ❌ Erreur: Python non trouvé
        echo.
        echo 🔧 Solutions possibles:
        echo    • Installez Python depuis python.org
        echo    • Ou créez un environnement virtuel dans .venv/
        echo    • Ou ajoutez Python au PATH système
        pause
        exit /b 1
    )
)

REM Vérification d'ExifTool
exiftool -ver >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Erreur: ExifTool non trouvé
    echo.
    echo 🔧 Solution: Installez ExifTool depuis exiftool.org
    echo    et ajoutez-le au PATH système
    pause
    exit /b 1
) else (
    for /f %%i in ('exiftool -ver') do set "EXIFTOOL_VERSION=%%i"
    echo ✅ ExifTool trouvé, version: !EXIFTOOL_VERSION!
)

echo.

REM Vérification des fichiers JSON
echo 🔍 Vérification du contenu du dossier...
set "JSON_COUNT=0"
for /r "%INPUT_DIR%" %%f in (*.json) do (
    set /a JSON_COUNT+=1
)

if !JSON_COUNT! equ 0 (
    echo ❌ Erreur: Aucun fichier .json trouvé dans le dossier
    echo.
    echo 📋 Le dossier doit contenir des fichiers JSON de Google Photos Takeout
    echo    Exemple: IMG_20231225_120000.jpg.json
    pause
    exit /b 1
) else (
    echo ✅ !JSON_COUNT! fichier^(s^) JSON trouvé^(s^)
)

REM Menu d'options
echo.
echo 🔧 Options de traitement:
echo    [1] Traitement standard (recommandé)
echo    [2] Traitement avec organisation des fichiers
echo    [3] Traitement avec géocodage (plus lent)
echo    [4] Traitement complet (organisation + géocodage)
echo    [5] Mode test/aperçu (dry-run)
echo.
set /p "CHOICE=Votre choix (1-5): "

REM Construction de la commande
set "MODULE_CMD=%PYTHON_CMD% -m google_takeout_metadata"
set "EXTRA_ARGS="

if "%CHOICE%"=="1" (
    echo 📋 Mode: Traitement standard
) else if "%CHOICE%"=="2" (
    echo 📋 Mode: Traitement avec organisation
    set "EXTRA_ARGS=--batch"
) else if "%CHOICE%"=="3" (
    echo 📋 Mode: Traitement avec géocodage
    set "EXTRA_ARGS=--geocode"
) else if "%CHOICE%"=="4" (
    echo 📋 Mode: Traitement complet
    set "EXTRA_ARGS=--batch --geocode"
) else if "%CHOICE%"=="5" (
    echo 📋 Mode: Test/Aperçu (dry-run)
    set "EXTRA_ARGS=--dry-run"
) else (
    echo ❌ Choix invalide, utilisation du mode standard
)

echo.
echo 🚀 Démarrage du traitement...
echo 📂 Commande: %MODULE_CMD% "%INPUT_DIR%" %EXTRA_ARGS%
echo.

REM Changement vers le répertoire du script
cd /d "%SCRIPT_DIR%"

REM Exécution du traitement
%MODULE_CMD% "%INPUT_DIR%" %EXTRA_ARGS%
set "EXIT_CODE=%errorlevel%"

echo.
if %EXIT_CODE% equ 0 (
    echo ✅ Traitement terminé avec succès !
    echo.
    echo 📊 Résultats:
    echo    • Métadonnées appliquées aux fichiers images/vidéos
    echo    • Fichiers JSON traités
    if not "%EXTRA_ARGS%"=="" (
        if "%EXTRA_ARGS%"=="--batch" echo    • Fichiers organisés dans des dossiers par date
        if "%EXTRA_ARGS%"=="--geocode" echo    • Géolocalisation appliquée
        if "%EXTRA_ARGS%"=="--batch --geocode" echo    • Fichiers organisés et géolocalisés
    )
    echo.
    echo 🎯 Vos fichiers sont maintenant enrichis avec leurs métadonnées !
) else (
    echo ❌ Traitement terminé avec des erreurs (code: %EXIT_CODE%)
    echo.
    echo 🔧 Solutions possibles:
    echo    • Vérifiez que le dossier contient bien des fichiers Google Photos
    echo    • Assurez-vous d'avoir les droits d'écriture sur les fichiers
    echo    • Consultez les logs pour plus de détails
)

echo.
echo 📋 Pour plus d'informations, consultez la documentation du projet
echo.
pause
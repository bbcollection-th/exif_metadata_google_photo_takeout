# ================================================================
# Script PowerShell pour Google Photos Takeout Metadata Processor
# Point 11 de la checklist : Script glisser-déposer automatique
# ================================================================

param(
    [Parameter(Position=0)]
    [string]$InputPath,
    
    [switch]$Batch,
    [switch]$Geocode,
    [switch]$DryRun,
    [switch]$LocalTime,
    [switch]$Help
)

function Write-Header {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "   Google Photos Takeout Metadata Processor" -ForegroundColor White
    Write-Host "   Script PowerShell de traitement automatique" -ForegroundColor Gray
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Success {
    param($Message)
    Write-Host "✅ $Message" -ForegroundColor Green
}

function Write-Error {
    param($Message)
    Write-Host "❌ $Message" -ForegroundColor Red
}

function Write-Warning {
    param($Message)
    Write-Host "⚠️ $Message" -ForegroundColor Yellow
}

function Write-Info {
    param($Message)
    Write-Host "ℹ️ $Message" -ForegroundColor Blue
}

function Show-Help {
    Write-Header
    Write-Host "📖 AIDE - Google Photos Processor" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "🎯 Usage:" -ForegroundColor White
    Write-Host "   .\google_photos_processor.ps1 <dossier> [options]"
    Write-Host ""
    Write-Host "📁 Glisser-Déposer:" -ForegroundColor White
    Write-Host "   Faites glisser votre dossier 'Google Photos' directement"
    Write-Host "   sur ce fichier .ps1 dans l'Explorateur Windows"
    Write-Host ""
    Write-Host "🔧 Options:" -ForegroundColor White
    Write-Host "   -Batch      Organiser les fichiers par date"
    Write-Host "   -Geocode    Ajouter la géolocalisation"
    Write-Host "   -DryRun     Mode test (aucune modification)"
    Write-Host "   -LocalTime  Utiliser l'heure locale"
    Write-Host "   -Help       Afficher cette aide"
    Write-Host ""
    Write-Host "📋 Exemples:" -ForegroundColor White
    Write-Host "   .\google_photos_processor.ps1 'C:\Takeout\Google Photos'"
    Write-Host "   .\google_photos_processor.ps1 'C:\Takeout\Google Photos' -Batch -Geocode"
    Write-Host ""
}

function Test-PythonEnvironment {
    $scriptDir = Split-Path -Parent $MyInvocation.ScriptName
    $venvPython = Join-Path $scriptDir ".venv\Scripts\python.exe"
    
    # 1. Essayer environnement virtuel local
    if (Test-Path $venvPython) {
        Write-Success "Python trouvé dans l'environnement virtuel local"
        return $venvPython
    }
    
    # 2. Essayer Python dans le PATH
    try {
        $null = & python --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Python trouvé dans le PATH système"
            $version = & python --version 2>&1
            Write-Host "   Version: $version" -ForegroundColor Gray
            return "python"
        }
    } catch {
        # Python non trouvé
    }
    
    Write-Error "Python non trouvé"
    Write-Host ""
    Write-Host "🔧 Solutions possibles:" -ForegroundColor Yellow
    Write-Host "   • Installez Python depuis python.org"
    Write-Host "   • Ou créez un environnement virtuel dans .venv\"
    Write-Host "   • Ou ajoutez Python au PATH système"
    return $null
}

function Test-ExifTool {
    try {
        $version = & exiftool -ver 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "ExifTool trouvé, version: $version"
            return $true
        }
    } catch {
        # ExifTool non trouvé
    }
    
    Write-Error "ExifTool non trouvé"
    Write-Host ""
    Write-Host "🔧 Solution:" -ForegroundColor Yellow
    Write-Host "   Installez ExifTool depuis exiftool.org"
    Write-Host "   et ajoutez-le au PATH système"
    return $false
}

function Test-InputDirectory {
    param($Path)
    
    if (-not $Path) {
        Write-Error "Aucun dossier spécifié"
        Write-Host ""
        Write-Host "📁 Usage: Glissez-déposez un dossier sur ce script (.ps1)" -ForegroundColor Yellow
        Write-Host "   ou utilisez: .\google_photos_processor.ps1 'chemin\vers\dossier'"
        return $false
    }
    
    if (-not (Test-Path $Path)) {
        Write-Error "Le chemin n'existe pas: $Path"
        return $false
    }
    
    if (-not (Test-Path $Path -PathType Container)) {
        Write-Error "Ce n'est pas un dossier valide: $Path"
        return $false
    }
    
    Write-Success "Dossier source: $Path"
    
    # Compter les fichiers JSON
    $jsonFiles = Get-ChildItem -Path $Path -Recurse -Filter "*.json" | Measure-Object
    $jsonCount = $jsonFiles.Count
    
    if ($jsonCount -eq 0) {
        Write-Error "Aucun fichier .json trouvé dans le dossier"
        Write-Host ""
        Write-Host "📋 Le dossier doit contenir des fichiers JSON de Google Photos Takeout" -ForegroundColor Yellow
        Write-Host "   Exemple: IMG_20231225_120000.jpg.json"
        return $false
    } else {
        Write-Success "$jsonCount fichier(s) JSON trouvé(s)"
        return $true
    }
}

function Get-UserChoice {
    if ($Batch -or $Geocode -or $DryRun -or $LocalTime) {
        # Options déjà spécifiées via paramètres
        return $true
    }
    
    Write-Host ""
    Write-Host "🔧 Options de traitement:" -ForegroundColor Cyan
    Write-Host "   [1] Traitement standard (recommandé)"
    Write-Host "   [2] Traitement avec organisation des fichiers"
    Write-Host "   [3] Traitement avec géolocalisation (plus lent)"
    Write-Host "   [4] Traitement complet (organisation + géolocalisation)"
    Write-Host "   [5] Mode test/aperçu (dry-run)"
    Write-Host "   [6] Traitement avec heure locale"
    Write-Host ""
    
    do {
        $choice = Read-Host "Votre choix (1-6)"
        
        switch ($choice) {
            "1" { 
                Write-Host "📋 Mode: Traitement standard" -ForegroundColor Green
                break
            }
            "2" { 
                Write-Host "📋 Mode: Traitement avec organisation" -ForegroundColor Green
                $script:Batch = $true
                break
            }
            "3" { 
                Write-Host "📋 Mode: Traitement avec géolocalisation" -ForegroundColor Green
                $script:Geocode = $true
                break
            }
            "4" { 
                Write-Host "📋 Mode: Traitement complet" -ForegroundColor Green
                $script:Batch = $true
                $script:Geocode = $true
                break
            }
            "5" { 
                Write-Host "📋 Mode: Test/Aperçu (dry-run)" -ForegroundColor Green
                $script:DryRun = $true
                break
            }
            "6" { 
                Write-Host "📋 Mode: Traitement avec heure locale" -ForegroundColor Green
                $script:LocalTime = $true
                break
            }
            default { 
                Write-Warning "Choix invalide, veuillez choisir entre 1 et 6"
                continue
            }
        }
        break
    } while ($true)
    
    return $true
}

function Start-Processing {
    param($PythonCmd, $InputPath)
    
    $args = @("-m", "google_takeout_metadata", "`"$InputPath`"")
    
    if ($Batch) { $args += "--batch" }
    if ($Geocode) { $args += "--geocode" }
    if ($DryRun) { $args += "--dry-run" }
    if ($LocalTime) { $args += "--local-time" }
    
    Write-Host ""
    Write-Host "🚀 Démarrage du traitement..." -ForegroundColor Green
    Write-Host "📂 Commande: $PythonCmd $($args -join ' ')" -ForegroundColor Gray
    Write-Host ""
    
    # Changer vers le répertoire du script
    $scriptDir = Split-Path -Parent $MyInvocation.ScriptName
    Push-Location $scriptDir
    
    try {
        $startTime = Get-Date
        & $PythonCmd @args
        $exitCode = $LASTEXITCODE
        $endTime = Get-Date
        $duration = $endTime - $startTime
        
        Write-Host ""
        Write-Host "⏱️ Durée du traitement: $($duration.ToString('hh\:mm\:ss'))" -ForegroundColor Gray
        
        if ($exitCode -eq 0) {
            Write-Success "Traitement terminé avec succès !"
            Write-Host ""
            Write-Host "📊 Résultats:" -ForegroundColor Cyan
            Write-Host "   • Métadonnées appliquées aux fichiers images/vidéos"
            Write-Host "   • Fichiers JSON traités"
            
            if ($Batch) { 
                Write-Host "   • Fichiers organisés dans des dossiers par date" -ForegroundColor Green
            }
            if ($Geocode) { 
                Write-Host "   • Géolocalisation appliquée" -ForegroundColor Green
            }
            if ($DryRun) { 
                Write-Host "   • Mode test - aucune modification effectuée" -ForegroundColor Yellow
            }
            
            Write-Host ""
            Write-Host "🎯 Vos fichiers sont maintenant enrichis avec leurs métadonnées !" -ForegroundColor Green
        } else {
            Write-Error "Traitement terminé avec des erreurs (code: $exitCode)"
            Write-Host ""
            Write-Host "🔧 Solutions possibles:" -ForegroundColor Yellow
            Write-Host "   • Vérifiez que le dossier contient bien des fichiers Google Photos"
            Write-Host "   • Assurez-vous d'avoir les droits d'écriture sur les fichiers"
            Write-Host "   • Consultez les logs pour plus de détails"
        }
        
        return $exitCode
    } finally {
        Pop-Location
    }
}

# ================================================================
# SCRIPT PRINCIPAL
# ================================================================

if ($Help) {
    Show-Help
    exit 0
}

Write-Header

# Si exécuté via glisser-déposer, $args[0] contient le chemin
if (-not $InputPath -and $args.Count -gt 0) {
    $InputPath = $args[0]
}

# Vérifications préliminaires
Write-Host "🔍 Vérification de l'environnement..." -ForegroundColor Cyan

if (-not (Test-InputDirectory $InputPath)) {
    Write-Host ""
    Write-Host "Pour obtenir de l'aide: .\google_photos_processor.ps1 -Help" -ForegroundColor Gray
    Read-Host "Appuyez sur Entrée pour quitter"
    exit 1
}

$pythonCmd = Test-PythonEnvironment
if (-not $pythonCmd) {
    Read-Host "Appuyez sur Entrée pour quitter"
    exit 1
}

if (-not (Test-ExifTool)) {
    Read-Host "Appuyez sur Entrée pour quitter"
    exit 1
}

# Choix des options de traitement
if (-not (Get-UserChoice)) {
    exit 1
}

# Lancement du traitement
$exitCode = Start-Processing $pythonCmd $InputPath

Write-Host ""
Write-Host "📋 Pour plus d'informations, consultez la documentation du projet" -ForegroundColor Gray
Write-Host ""

if ($exitCode -eq 0) {
    Write-Host "Appuyez sur Entrée pour continuer..." -ForegroundColor Green
} else {
    Write-Host "Appuyez sur Entrée pour quitter..." -ForegroundColor Red
}
Read-Host

exit $exitCode
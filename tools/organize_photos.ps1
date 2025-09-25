# Script PowerShell pour organiser les photos par date avec ExifTool
# Usage: .\organize_photos.ps1 "C:\chemin\vers\photos" [-TargetDir "C:\destination"] [-DryRun]

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$SourceDir,
    
    [Parameter(Position=1)]
    [string]$TargetDir = "",
    
    [switch]$DryRun = $false,
    
    [switch]$Verbose = $false
)

# Configuration
if ($TargetDir -eq "") {
    $TargetDir = $SourceDir
}

# Extensions supportées
$SupportedExtensions = @(
    '*.jpg', '*.jpeg', '*.jpe',
    '*.png', '*.gif', '*.bmp', '*.tiff', '*.tif',
    '*.heic', '*.heif', '*.webp',
    '*.mp4', '*.mov', '*.avi', '*.mkv', '*.wmv', '*.m4v',
    '*.raw', '*.cr2', '*.nef', '*.arw', '*.dng'
)

# Tags de date par ordre de priorité
$DateTags = @(
    'DateTimeOriginal',
    'CreateDate', 
    'CreationDate',
    'DateCreated',
    'FileModifyDate'
)

function Test-ExifTool {
    try {
        $version = & exiftool -ver 2>$null
        Write-Host "ExifTool version $version détecté" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Error "ExifTool non trouvé. Installez-le avec: scoop install exiftool"
        return $false
    }
}

function Get-FileDate {
    param([string]$FilePath)
    
    foreach ($tag in $DateTags) {
        try {
            $dateStr = & exiftool -s -s -s -d "%Y-%m" "-$tag" $FilePath 2>$null
            if ($dateStr -and $dateStr -ne "-" -and $dateStr -ne "0000-00") {
                if ($Verbose) {
                    Write-Host "  Trouvé date '$dateStr' via tag $tag" -ForegroundColor DarkGray
                }
                return $dateStr
            }
        }
        catch {
            # Continuer avec le tag suivant
        }
    }
    
    if ($Verbose) {
        Write-Host "  Aucune date trouvée, utilisation de 'unknown_date'" -ForegroundColor Yellow
    }
    return "unknown_date"
}

function Move-FileToDateFolder {
    param(
        [string]$FilePath,
        [string]$DateFolder
    )
    
    $fileName = Split-Path $FilePath -Leaf
    $targetDir = Join-Path $TargetDir $DateFolder
    $targetPath = Join-Path $targetDir $fileName
    
    # Créer le dossier de destination
    if (-not $DryRun) {
        if (-not (Test-Path $targetDir)) {
            New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
        }
    }
    
    # Gérer les conflits de noms
    $counter = 1
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($fileName)
    $extension = [System.IO.Path]::GetExtension($fileName)
    
    while (Test-Path $targetPath) {
        $newName = "{0}_{1:D3}{2}" -f $baseName, $counter, $extension
        $targetPath = Join-Path $targetDir $newName
        $counter++
    }
    
    # Déplacer le fichier
    try {
        if ($DryRun) {
            Write-Host "[DRY-RUN] Déplacerait: $FilePath -> $targetPath" -ForegroundColor Cyan
        }
        else {
            Move-Item -Path $FilePath -Destination $targetPath -Force
            Write-Host "Déplacé: $fileName -> $DateFolder/" -ForegroundColor Green
        }
        return $true
    }
    catch {
        Write-Error "Erreur déplacement $FilePath : $_"
        return $false
    }
}

# Vérifications initiales
Write-Host "==========================================" -ForegroundColor Blue
Write-Host " ORGANISATEUR DE PHOTOS PAR DATE" -ForegroundColor Blue  
Write-Host "==========================================" -ForegroundColor Blue
Write-Host ""

if (-not (Test-Path $SourceDir)) {
    Write-Error "Dossier source '$SourceDir' non trouvé"
    exit 1
}

if (-not (Test-ExifTool)) {
    exit 1
}

Write-Host "Source: $SourceDir" -ForegroundColor White
Write-Host "Destination: $TargetDir" -ForegroundColor White
if ($DryRun) {
    Write-Host "Mode: SIMULATION (aucun fichier ne sera déplacé)" -ForegroundColor Yellow
}
else {
    Write-Host "Mode: RÉEL (les fichiers seront déplacés)" -ForegroundColor Green
}
Write-Host "==========================================" -ForegroundColor Blue
Write-Host ""

# Rechercher tous les fichiers supportés
Write-Host "Recherche des fichiers..." -ForegroundColor White

$allFiles = @()
foreach ($ext in $SupportedExtensions) {
    $files = Get-ChildItem -Path $SourceDir -Filter $ext -Recurse -File
    $allFiles += $files
}

if ($allFiles.Count -eq 0) {
    Write-Warning "Aucun fichier supporté trouvé dans $SourceDir"
    exit 0
}

Write-Host "$($allFiles.Count) fichiers supportés trouvés" -ForegroundColor White
Write-Host ""

# Variables de statistiques
$stats = @{}
$totalFiles = $allFiles.Count
$processedFiles = 0
$successfulMoves = 0

# Traiter chaque fichier
Write-Host "Traitement des fichiers..." -ForegroundColor White
Write-Host ""

foreach ($file in $allFiles) {
    $processedFiles++
    
    if ($Verbose) {
        Write-Host "[$processedFiles/$totalFiles] Traitement: $($file.Name)" -ForegroundColor DarkGray
    }
    
    # Obtenir la date
    $dateFolder = Get-FileDate -FilePath $file.FullName
    
    # Incrémenter les statistiques
    if (-not $stats.ContainsKey($dateFolder)) {
        $stats[$dateFolder] = 0
    }
    $stats[$dateFolder]++
    
    # Déplacer le fichier
    if (Move-FileToDateFolder -FilePath $file.FullName -DateFolder $dateFolder) {
        $successfulMoves++
    }
    
    # Afficher la progression
    if ($processedFiles % 10 -eq 0) {
        Write-Host "Progression: $processedFiles/$totalFiles fichiers traités" -ForegroundColor Yellow
    }
}

# Afficher les statistiques finales
Write-Host ""
Write-Host "==================================================" -ForegroundColor Blue
Write-Host "                STATISTIQUES FINALES" -ForegroundColor Blue
Write-Host "==================================================" -ForegroundColor Blue

$sortedStats = $stats.GetEnumerator() | Sort-Object Name
foreach ($entry in $sortedStats) {
    Write-Host ("{0,-20} : {1,4} fichiers" -f $entry.Key, $entry.Value) -ForegroundColor White
}

Write-Host ""
Write-Host "Total traité: $successfulMoves/$totalFiles fichiers" -ForegroundColor White

if ($DryRun) {
    Write-Host ""
    Write-Warning "MODE DRY-RUN: Aucun fichier n'a été réellement déplacé"
    Write-Host "Pour exécuter réellement, relancez sans le paramètre -DryRun" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Terminé!" -ForegroundColor Green
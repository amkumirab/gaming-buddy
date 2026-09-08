[CmdletBinding()]
param(
    [string]$PythonExecutable = "python",
    [switch]$SkipApplicationBuild
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

Push-Location $projectRoot
try {
    $validationOutput = & $PythonExecutable "scripts/validate_release.py"
    if ($LASTEXITCODE -ne 0) {
        throw "Release metadata validation failed with exit code $LASTEXITCODE."
    }
    $versionMatch = [regex]::Match(($validationOutput -join "`n"), "version (\d+\.\d+\.\d+)")
    if (-not $versionMatch.Success) {
        throw "Could not determine the validated release version."
    }
    $version = $versionMatch.Groups[1].Value

    if (-not $SkipApplicationBuild) {
        & $PythonExecutable -m PyInstaller --clean --noconfirm "packaging/gaming-buddy.spec"
        if ($LASTEXITCODE -ne 0) {
            throw "Application build failed with exit code $LASTEXITCODE."
        }
    }

    $bundle = Join-Path $projectRoot "dist/GamingBuddy/GamingBuddy.exe"
    if (-not (Test-Path -LiteralPath $bundle -PathType Leaf)) {
        throw "The application bundle is missing. Build it before creating the installer."
    }

    $compilerCommand = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    $compilerCandidates = @(
        $(if ($compilerCommand) { $compilerCommand.Source }),
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $compilerPath = $compilerCandidates |
        Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } |
        Select-Object -First 1
    if (-not $compilerPath) {
        throw "Inno Setup 6 compiler was not found."
    }

    & $compilerPath "packaging/gaming-buddy.iss"
    if ($LASTEXITCODE -ne 0) {
        throw "Installer build failed with exit code $LASTEXITCODE."
    }

    $installer = Join-Path $projectRoot "release/Gaming-Buddy-Setup-$version-x64.exe"
    if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
        throw "The expected installer was not created: $installer"
    }
    $checksumPath = "$installer.sha256"
    $checksum = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
    "$checksum  $([IO.Path]::GetFileName($installer))" |
        Set-Content -LiteralPath $checksumPath -Encoding ascii

    Write-Host "Installer: $installer"
    Write-Host "SHA-256:  $checksum"
}
finally {
    Pop-Location
}

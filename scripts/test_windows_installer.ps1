[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$InstallerPath,
    [Parameter(Mandatory)]
    [string]$Version,
    [string]$ReportDirectory = "installer-test"
)

$ErrorActionPreference = "Stop"
# Installation and removal change HKCU and shortcuts. Never use a real user profile.
if ($env:GITHUB_ACTIONS -ne "true" -or $env:RUNNER_ENVIRONMENT -ne "github-hosted") {
    throw "This lifecycle test requires a disposable GitHub-hosted Windows runner."
}

$installer = (Resolve-Path -LiteralPath $InstallerPath).Path
$expectedName = "Gaming-Buddy-Setup-$Version-x64.exe"
if ([IO.Path]::GetFileName($installer) -cne $expectedName) {
    throw "Installer name does not match version $Version."
}
$checksumLine = (Get-Content -LiteralPath "$installer.sha256" -Raw).Trim()
$digest = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
if ($checksumLine -cne "$digest  $expectedName") {
    throw "Installer checksum or filename does not match."
}

$installDirectory = Join-Path $env:LOCALAPPDATA "Programs\Gaming Buddy"
$dataDirectory = Join-Path $env:LOCALAPPDATA "GamingBuddy"
$settingsKey = "HKCU:\Software\GamingBuddy"
$uninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{57C1EB82-EEAD-4E5F-8F24-49C61A578D08}_is1"
foreach ($path in @($installDirectory, $dataDirectory, $settingsKey, $uninstallKey)) {
    if (Test-Path -LiteralPath $path) {
        throw "Refusing to overwrite existing application state: $path"
    }
}
$reportRoot = (New-Item -ItemType Directory -Path $ReportDirectory -Force).FullName
$checks = [ordered]@{}
$appProcess = $null
$originalPath = $env:PATH
$pythonEnvironment = @{}

function Invoke-Setup([string]$Executable, [string[]]$Arguments) {
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments -WindowStyle Hidden -PassThru
    if (-not $process.WaitForExit(120000)) {
        Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
        throw "Installer did not finish within two minutes."
    }
    if ($process.ExitCode -ne 0) {
        throw "Installer exited with code $($process.ExitCode)."
    }
}

try {
    Invoke-Setup $installer @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/TASKS=desktopicon", "/LOG=`"$reportRoot\install.log`"")
    $executable = Join-Path $installDirectory "GamingBuddy.exe"
    if (-not (Test-Path -LiteralPath $executable)) { throw "Installed executable is missing." }
    if ((Get-Item -LiteralPath $executable).VersionInfo.ProductVersion -ne $Version) {
        throw "Installed executable version differs from the release."
    }
    if ((Get-ItemProperty -LiteralPath $uninstallKey).DisplayVersion -ne $Version) {
        throw "Windows uninstall registration has the wrong version."
    }
    $shortcuts = @(
        (Join-Path ([Environment]::GetFolderPath("Programs")) "Gaming Buddy.lnk"),
        (Join-Path ([Environment]::GetFolderPath("Desktop")) "Gaming Buddy.lnk")
    )
    $shell = New-Object -ComObject WScript.Shell
    foreach ($shortcut in $shortcuts) {
        if (-not (Test-Path -LiteralPath $shortcut)) { throw "Shortcut is missing: $shortcut" }
        if ($shell.CreateShortcut($shortcut).TargetPath -ne $executable) {
            throw "Shortcut points to a different executable: $shortcut"
        }
    }
    $checks.install_and_shortcuts = "passed"

    # Restrict the launched application's environment; the runner itself still has Python.
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    foreach ($name in @("PYTHONHOME", "PYTHONPATH", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH")) {
        $pythonEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
        [Environment]::SetEnvironmentVariable($name, $null, "Process")
    }
    $appProcess = Start-Process -FilePath $executable -WorkingDirectory $installDirectory -WindowStyle Hidden -PassThru
    Start-Sleep -Seconds 8
    $appProcess.Refresh()
    if ($appProcess.HasExited) { throw "Installed application exited during startup." }
    $runtime = @($appProcess.Modules | Where-Object { $_.ModuleName -match '^python3\d+\.dll$' })
    if ($runtime.Count -ne 1 -or -not $runtime[0].FileName.StartsWith("$installDirectory\", [StringComparison]::OrdinalIgnoreCase)) {
        throw "Application did not load its bundled Python runtime."
    }
    Stop-Process -Id $appProcess.Id
    $appProcess.WaitForExit(10000) | Out-Null
    $appProcess = $null
    $checks.bundled_runtime_startup = "passed"
    $database = Join-Path $dataDirectory "gaming-buddy.sqlite3"
    if (-not (Test-Path -LiteralPath $database)) { throw "Application did not create its database." }

    # These are retention sentinels, not a claim of UI note/screenshot testing.
    $note = Join-Path $dataDirectory "release-test-note.txt"
    "First line`nSecond line" | Set-Content -LiteralPath $note -Encoding utf8
    $image = Join-Path $dataDirectory "captures\release-test.png"
    [IO.File]::WriteAllBytes($image, [Convert]::FromBase64String("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aV1cAAAAASUVORK5CYII="))
    New-Item -Path "$settingsKey\ReleaseTest" -Force | Out-Null
    New-ItemProperty -Path "$settingsKey\ReleaseTest" -Name "Retention" -Value "keep" -Force | Out-Null
    $savedHashes = @{}
    foreach ($file in @($database, $note, $image)) {
        $savedHashes[$file] = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash
    }
    $obsolete = Join-Path $installDirectory "_internal\release-test-obsolete.txt"
    "obsolete" | Set-Content -LiteralPath $obsolete
    Invoke-Setup $installer @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/LOG=`"$reportRoot\reinstall.log`"")
    if (Test-Path -LiteralPath $obsolete) { throw "Reinstall did not remove stale runtime files." }
    foreach ($file in $savedHashes.Keys) {
        if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $savedHashes[$file]) {
            throw "Reinstall changed user data: $file"
        }
    }
    $checks.same_version_reinstall_retention = "passed"
    Invoke-Setup (Join-Path $installDirectory "unins000.exe") @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/LOG=`"$reportRoot\uninstall.log`"")
    foreach ($path in @($executable, $uninstallKey) + $shortcuts) {
        if (Test-Path -LiteralPath $path) { throw "Uninstall left a program entry behind: $path" }
    }
    foreach ($file in $savedHashes.Keys) {
        if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $savedHashes[$file]) {
            throw "Uninstall changed user data: $file"
        }
    }
    if ((Get-ItemProperty -LiteralPath "$settingsKey\ReleaseTest").Retention -ne "keep") {
        throw "Uninstall removed retained settings."
    }
    $checks.silent_uninstall_retention = "passed"
}
finally {
    if ($appProcess -and -not $appProcess.HasExited) { Stop-Process -Id $appProcess.Id }
    $env:PATH = $originalPath
    foreach ($name in $pythonEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $pythonEnvironment[$name], "Process")
    }
    [ordered]@{
        commit = $env:GITHUB_SHA
        version = $Version
        installer = $expectedName
        sha256 = $digest
        checks = $checks
        limitations = @(
            "The hosted runner has Python installed; only application PATH was restricted.",
            "Tray, global hotkeys, interactive capture and note editing require a desktop test.",
            "Reinstall uses the same version; an older-to-newer upgrade is not exercised."
        )
    } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath "$reportRoot\result.json" -Encoding utf8
}

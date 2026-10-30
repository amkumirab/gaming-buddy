#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$InstallerPath,
    [Parameter(Mandatory)]
    [ValidatePattern('\A[0-9a-fA-F]{40}\z')]
    [string]$BuildCommit,
    [Parameter(Mandatory)]
    [ValidatePattern('\Ahttps://github\.com/amkumirab/gaming-buddy/actions/runs/[1-9][0-9]*\z')]
    [string]$BuildRunUrl,
    [Parameter(Mandatory)]
    [string]$ReportDirectory
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$installer = Get-Item -LiteralPath $InstallerPath
if ($installer.PSIsContainer -or $installer.Name -cnotmatch '\AGaming-Buddy-Setup-(\d+\.\d+\.\d+)-x64\.exe\z') {
    throw 'Expected Gaming-Buddy-Setup-MAJOR.MINOR.PATCH-x64.exe.'
}
$version = $Matches[1]
$checksumFile = Get-Item -LiteralPath "$($installer.FullName).sha256"
if ($checksumFile.PSIsContainer -or $checksumFile.Length -gt 4096) {
    throw 'Expected a small SHA-256 checksum file beside the installer.'
}
$digest = (Get-FileHash -LiteralPath $installer.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
$checksum = (Get-Content -LiteralPath $checksumFile.FullName -Raw -Encoding utf8).Trim()
if ($checksum -cne "$digest  $($installer.Name)") {
    throw 'Installer checksum or filename does not match. No report was created.'
}
if (Test-Path -LiteralPath $ReportDirectory) {
    throw 'Report directory already exists. Choose a new directory to preserve earlier evidence.'
}
$docs = Join-Path $PSScriptRoot '../docs'
$report = Get-Content -LiteralPath (Join-Path $docs 'windows-acceptance-report.md') -Raw -Encoding utf8
$compatibility = Get-Content -LiteralPath (Join-Path $docs 'game-compatibility-report.md') -Raw -Encoding utf8
$commit = $BuildCommit.ToLowerInvariant()
$environment = [ordered]@{
    os_reported = [Environment]::OSVersion.VersionString
    os_64_bit = [Environment]::Is64BitOperatingSystem
    process_architecture = $env:PROCESSOR_ARCHITECTURE
    powershell_version = $PSVersionTable.PSVersion.ToString()
}
$identity = [ordered]@{
    schema_version = 1
    prepared_at_utc = [DateTime]::UtcNow.ToString('o')
    commit = $commit
    build_run_url = $BuildRunUrl
    identity_source = 'Caller supplied; cross-check against Actions before acceptance.'
    version = $version
    installer = $installer.Name
    installer_bytes = $installer.Length
    sha256 = $digest
    checksum = 'passed'
    environment = $environment
    clean_machine_acceptance = 'not_tested'
    publication = 'pending'
}
$report = $report.Replace(
    '# Windows installer acceptance report template', '# Windows installer acceptance report'
).Replace(
    'This blank template is not test evidence.',
    'Only the local installer checksum has been verified; desktop acceptance remains pending.'
).Replace(
    '- Build run URL and full commit SHA: Not recorded',
    "- Build run URL and full commit SHA: $BuildRunUrl ; $commit"
).Replace(
    '- Version and installer filename: Not recorded',
    "- Version and installer filename: $version ; $($installer.Name)"
).Replace(
    '- Installer SHA-256 and matching checksum file: Not recorded',
    "- Installer SHA-256 and matching checksum file: $digest ; local checksum matched"
).Replace(
    '(windows-release.md#clean-machine-desktop-acceptance)',
    "(https://github.com/amkumirab/gaming-buddy/blob/$commit/docs/windows-release.md#clean-machine-desktop-acceptance)"
)
$header = "Candidate: $($installer.Name)`n`nCommit: $commit`n`nBuild: $BuildRunUrl`n`nSHA-256: $digest`n`n"
# Create a new directory only after all inputs and templates have been read successfully.
$output = (New-Item -ItemType Directory -Path $ReportDirectory).FullName
$utf8 = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText((Join-Path $output 'candidate.json'), ($identity | ConvertTo-Json -Depth 4), $utf8)
[IO.File]::WriteAllText((Join-Path $output 'acceptance.md'), $report, $utf8)
[IO.File]::WriteAllText((Join-Path $output 'game-compatibility.md'), ($header + $compatibility), $utf8)
Write-Output "Checksum verified. Reports prepared in $output"
Write-Output 'Clean-machine, game compatibility, and publication checks remain pending.'

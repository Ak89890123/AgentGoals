param(
    [string]$OutputDir = "",
    [string]$SmokeStatePath = "",
    [switch]$SkipClean
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$launcher = Join-Path $repoRoot "apps\goal_dashboard.pyw"
$schemas = Join-Path $repoRoot "schemas"
$assets = Join-Path $repoRoot "assets"
$icon = Join-Path $assets "agentgoals-target.ico"
$source = Join-Path $repoRoot "src"
$work = Join-Path $repoRoot ".tmp\pyinstaller-dashboard"
if (-not $OutputDir) {
    $OutputDir = Join-Path $repoRoot "dist\agentgoals-dashboard"
}
$output = [System.IO.Path]::GetFullPath($OutputDir)

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Repository virtual environment is missing: $python"
}
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
    throw "Dashboard launcher is missing: $launcher"
}
if (-not (Test-Path -LiteralPath $icon -PathType Leaf)) {
    throw "Dashboard icon is missing: $icon"
}

& $python -m PyInstaller --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is unavailable. Install the desktop extra first: .\.venv\Scripts\python -m pip install -e .[desktop]"
}

New-Item -ItemType Directory -Path $output -Force | Out-Null
$arguments = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--onedir",
    "--windowed",
    "--name", "AgentGoals",
    "--distpath", $output,
    "--workpath", $work,
    "--specpath", $work,
    "--paths", $source,
    "--add-data", "$schemas;schemas",
    "--add-data", "$assets;assets",
    "--icon", $icon
)
if (-not $SkipClean) {
    $arguments += "--clean"
}
$arguments += $launcher

& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Dashboard packaging failed with exit code $LASTEXITCODE"
}

$packageDir = Join-Path $output "AgentGoals"
$executable = Join-Path $packageDir "AgentGoals.exe"
if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "Packaged executable was not created: $executable"
}
$size = (Get-ChildItem -LiteralPath $packageDir -File -Recurse | Measure-Object -Property Length -Sum).Sum
$sizeMb = [Math]::Round($size / 1MB, 2)
Write-Output "Executable: $executable"
Write-Output "InstalledSizeMB: $sizeMb"
if ($size -gt 60MB) {
    throw "Installed package exceeds the 60 MB Contract budget: $sizeMb MB"
}

$sourceSchema = Join-Path $schemas "goal-state.schema.json"
$bundledSchema = Join-Path $packageDir "_internal\schemas\goal-state.schema.json"
if (-not (Test-Path -LiteralPath $bundledSchema -PathType Leaf)) {
    throw "Packaged Goal STATE schema is missing: $bundledSchema"
}
$sourceSchemaHash = (Get-FileHash -LiteralPath $sourceSchema -Algorithm SHA256).Hash
$bundledSchemaHash = (Get-FileHash -LiteralPath $bundledSchema -Algorithm SHA256).Hash
if ($sourceSchemaHash -ne $bundledSchemaHash) {
    throw "Packaged Goal STATE schema does not match the source schema"
}
Write-Output "BundledSchemaSHA256: $bundledSchemaHash"

$liveStatePath = Join-Path $repoRoot "outputs\global\STATE.json"
$fixtureStatePath = Join-Path $repoRoot "fixtures\dashboard\clean-state.json"
if ($SmokeStatePath) {
    $statePath = [System.IO.Path]::GetFullPath($SmokeStatePath)
} elseif (Test-Path -LiteralPath $liveStatePath -PathType Leaf) {
    $statePath = $liveStatePath
} else {
    $statePath = $fixtureStatePath
}
if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
    throw "Dashboard smoke STATE is missing: $statePath"
}
$probe = Join-Path $repoRoot ".tmp\dashboard-package-smoke.json"
if (Test-Path -LiteralPath $probe) {
    Remove-Item -LiteralPath $probe -Force
}
$quotedState = '"' + $statePath + '"'
$quotedProbe = '"' + $probe + '"'
$process = Start-Process -FilePath $executable -ArgumentList @(
    "--state", $quotedState,
    "--smoke",
    "--probe-output", $quotedProbe
) -WindowStyle Hidden -PassThru -Wait
$probePayload = $null
if (Test-Path -LiteralPath $probe -PathType Leaf) {
    $probePayload = Get-Content -LiteralPath $probe -Raw -Encoding UTF8 | ConvertFrom-Json
}
if ($process.ExitCode -ne 0 -or $null -eq $probePayload -or $probePayload.status -ne "passed") {
    $detail = if ($null -ne $probePayload) { $probePayload | ConvertTo-Json -Compress } else { "probe missing" }
    throw "Packaged dashboard smoke failed: exit=$($process.ExitCode) $detail"
}
Write-Output "PackageSmokeState: $statePath"
Write-Output "PackageSmokeEntries: $($probePayload.entries)"

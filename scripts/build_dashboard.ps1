param(
    [string]$OutputDir = "",
    [switch]$SkipClean
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$launcher = Join-Path $repoRoot "apps\goal_dashboard.pyw"
$schemas = Join-Path $repoRoot "schemas"
$source = Join-Path $repoRoot "src"
$work = Join-Path $repoRoot ".tmp\pyinstaller-dashboard"
if (-not $OutputDir) {
    $OutputDir = Join-Path $repoRoot "dist\goal-dashboard"
}
$output = [System.IO.Path]::GetFullPath($OutputDir)

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Repository virtual environment is missing: $python"
}
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
    throw "Dashboard launcher is missing: $launcher"
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
    "--name", "GoalControl",
    "--distpath", $output,
    "--workpath", $work,
    "--specpath", $work,
    "--paths", $source,
    "--add-data", "$schemas;schemas"
)
if (-not $SkipClean) {
    $arguments += "--clean"
}
$arguments += $launcher

& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Dashboard packaging failed with exit code $LASTEXITCODE"
}

$packageDir = Join-Path $output "GoalControl"
$executable = Join-Path $packageDir "GoalControl.exe"
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

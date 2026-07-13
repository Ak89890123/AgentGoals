param(
    [string]$Executable = "",
    [string]$StatePath = "",
    [int]$Iterations = 5
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
if (-not $Executable) {
    $Executable = Join-Path $repoRoot "dist\agentgoals-dashboard\AgentGoals\AgentGoals.exe"
}
if (-not $StatePath) {
    $StatePath = Join-Path $repoRoot "outputs\global\STATE.json"
}
$exe = (Resolve-Path -LiteralPath $Executable).Path
$state = (Resolve-Path -LiteralPath $StatePath).Path
$quotedState = '"' + $state + '"'

$coldStarts = @()
1..$Iterations | ForEach-Object {
    $measurement = Measure-Command {
        $smoke = Start-Process -FilePath $exe -ArgumentList @("--state", $quotedState, "--smoke") -WindowStyle Hidden -PassThru -Wait
        if ($smoke.ExitCode -ne 0) {
            throw "Packaged dashboard smoke failed with exit code $($smoke.ExitCode)"
        }
    }
    $coldStarts += $measurement.TotalMilliseconds
}

$before = @(Get-Process -Name AgentGoals -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$process = Start-Process -FilePath $exe -ArgumentList @("--state", $quotedState) -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 3
$running = @(Get-Process -Name AgentGoals -ErrorAction SilentlyContinue | Where-Object { $before -notcontains $_.Id })
$workingSet = ($running | Measure-Object -Property WorkingSet64 -Sum).Sum
$privateMemory = ($running | Measure-Object -Property PrivateMemorySize64 -Sum).Sum
$running | Stop-Process -Force

$packageDir = Split-Path -Parent $exe
$installedSize = (Get-ChildItem -LiteralPath $packageDir -File -Recurse | Measure-Object -Property Length -Sum).Sum
$meanColdStart = ($coldStarts | Measure-Object -Average).Average
$maxColdStart = ($coldStarts | Measure-Object -Maximum).Maximum
$workingSetMb = [Math]::Round($workingSet / 1MB, 2)
$privateMemoryMb = [Math]::Round($privateMemory / 1MB, 2)
$installedSizeMb = [Math]::Round($installedSize / 1MB, 2)

Write-Output ("ColdStartMeanMs=" + [Math]::Round($meanColdStart, 2))
Write-Output ("ColdStartMaxMs=" + [Math]::Round($maxColdStart, 2))
Write-Output ("WorkingSetMB=" + $workingSetMb)
Write-Output ("PrivateMemoryMB=" + $privateMemoryMb)
Write-Output ("InstalledSizeMB=" + $installedSizeMb)

if ($meanColdStart -gt 2000) { throw "Mean cold start exceeds 2,000 ms" }
if ($workingSet -gt 150MB) { throw "Working set exceeds 150 MB" }
if ($installedSize -gt 60MB) { throw "Installed size exceeds 60 MB" }

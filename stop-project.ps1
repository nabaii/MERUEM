param(
    [switch]$RemoveVolumes
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Fail {
    param([string]$Message)
    Write-Host ""
    Write-Host $Message -ForegroundColor Red
    exit 1
}

$repoRoot = $PSScriptRoot
Set-Location $repoRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fail "Docker is required to stop the project stack."
}

$composeArgs = @("--profile", "dev", "down", "--remove-orphans")
if ($RemoveVolumes) {
    $composeArgs += "--volumes"
}

& docker compose @composeArgs
if ($LASTEXITCODE -ne 0) {
    Fail "Failed to stop the project stack."
}

Write-Host ""
Write-Host "Project stack stopped." -ForegroundColor Green
if ($RemoveVolumes) {
    Write-Host "Docker volumes were removed too."
}

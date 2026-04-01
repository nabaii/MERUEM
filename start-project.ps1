param(
    [switch]$UseBuiltFrontend,
    [switch]$SkipWorkers
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Note {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Yellow
}

function Fail {
    param([string]$Message)
    Write-Host ""
    Write-Host $Message -ForegroundColor Red
    exit 1
}

function Ensure-Command {
    param(
        [string]$Name,
        [string]$Hint
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Fail $Hint
    }
}

function Invoke-Compose {
    param([string[]]$ComposeArgs)

    & docker compose @ComposeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose $($ComposeArgs -join ' ') failed."
    }
}

function Wait-ForHttp {
    param(
        [string]$Url,
        [string]$Name,
        [int]$TimeoutSeconds = 240
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return
            }
        } catch {
            Start-Sleep -Seconds 2
        }
    }

    throw "Timed out waiting for $Name at $Url."
}

$repoRoot = $PSScriptRoot
Set-Location $repoRoot

Ensure-Command -Name "docker" -Hint "Docker is required. Install Docker Desktop, then rerun this command."

try {
    & docker info | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "docker info failed"
    }
} catch {
    Fail "Docker Desktop does not appear to be running. Start Docker Desktop, then rerun this command."
}

if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Note "Created .env from .env.example."
    } else {
        Fail "No .env file was found, and .env.example is missing too."
    }
}

$apiServices = @("up", "-d", "postgres", "redis", "api")

Write-Step "Starting database, cache, and API"
Invoke-Compose -ComposeArgs $apiServices

Write-Step "Waiting for API to come online"
Wait-ForHttp -Url "http://localhost:8000/" -Name "API"

Write-Step "Running database migrations"
try {
    Invoke-Compose -ComposeArgs @("exec", "-T", "api", "alembic", "upgrade", "head")
} catch {
    Write-Note "Migration failed. If the error mentions role_enum already exists, stop the stack and run .\stop-project.cmd -RemoveVolumes before trying again."
    throw
}

$profileArgs = @()
$frontendService = "frontend-dev"
$frontendUrl = "http://localhost:3000"

if ($UseBuiltFrontend) {
    $frontendService = "frontend"
    $frontendUrl = "http://localhost"
} else {
    $profileArgs = @("--profile", "dev")
}

$remainingServices = @()
if (-not $SkipWorkers) {
    $remainingServices += @("worker", "beat")
}
$remainingServices += $frontendService

Write-Step "Starting the remaining services"
Invoke-Compose -ComposeArgs ($profileArgs + @("up", "-d") + $remainingServices)

Write-Step "Waiting for frontend to come online"
Wait-ForHttp -Url $frontendUrl -Name "frontend" -TimeoutSeconds 300

Write-Host ""
Write-Host "Project is running." -ForegroundColor Green
Write-Host "Frontend: $frontendUrl"
Write-Host "API docs: http://localhost:8000/docs"
Write-Host "Login: use 'Skip login (dev)' on the sign-in page"
Write-Host ""
Write-Host "Useful commands:"
Write-Host "  .\stop-project.cmd"
if ($UseBuiltFrontend) {
    Write-Host "  docker compose logs -f"
} else {
    Write-Host "  docker compose --profile dev logs -f"
}

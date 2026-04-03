param(
    [switch]$SkipFrontend,
    [switch]$SkipBackend
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $repoRoot "frontend"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not $SkipFrontend) {
    Write-Host "==> Verifying frontend"
    Push-Location $frontendRoot
    try {
        npm run verify
        if ($LASTEXITCODE -ne 0) {
            throw "frontend verification failed"
        }
    } finally {
        Pop-Location
    }
}

if (-not $SkipBackend) {
    if (-not (Test-Path $venvPython)) {
        throw "Expected Python virtual environment at .venv\Scripts\python.exe"
    }

    Write-Host "==> Running backend tests"
    Push-Location $repoRoot
    try {
        & $venvPython -m pytest tests/test_detection/test_detection_service_dedup.py tests/test_services/test_detection_presenter.py tests/test_services/test_detection_pipeline.py tests/test_services/test_detection_records_service.py
        if ($LASTEXITCODE -ne 0) {
            throw "backend verification failed"
        }
    } finally {
        Pop-Location
    }
}

Write-Host "==> Verification complete"

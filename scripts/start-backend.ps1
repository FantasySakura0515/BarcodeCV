$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    throw "Expected Python virtual environment at .venv\Scripts\python.exe"
}

Push-Location $repoRoot
try {
    & $venvPython -m backend.api
} finally {
    Pop-Location
}

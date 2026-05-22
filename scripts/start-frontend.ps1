param()

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $repoRoot "frontend"

if (-not (Test-Path $frontendRoot)) {
    throw "Frontend workspace not found at $frontendRoot"
}

Push-Location $frontendRoot
try {
    npm run dev
} finally {
    Pop-Location
}

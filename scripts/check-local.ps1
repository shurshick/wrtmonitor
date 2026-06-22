$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    throw "Run .\scripts\setup-dev.ps1 first"
}

function Invoke-Step {
    param(
        [string]$Command,
        [string]$WorkingDirectory = $repoRoot
    )

    Push-Location $WorkingDirectory
    try {
        & powershell -NoProfile -Command $Command
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed: $Command"
        }
    }
    finally {
        Pop-Location
    }
}

$env:PYTHONPATH = $repoRoot
$env:WRTMONITOR_DATABASE_URL = "postgresql+psycopg://wrtmonitor:local-dev-password@localhost:5432/wrtmonitor_test"
$env:WRTMONITOR_ALLOW_INSECURE_LOCAL = "true"
$env:WRTMONITOR_ALLOW_INSECURE_DEV_DEFAULTS = "true"
$env:WRTMONITOR_JWT_SECRET = "local-dev-secret-value-with-more-than-32-characters"
$env:WRTMONITOR_SKIP_E2E = "1"

Invoke-Step "$venvPython -m compileall backend"
Invoke-Step "$venvPython -m ruff check backend --select E9,F63,F7,F82"
Invoke-Step "$venvPython -m ruff format --check backend"
Invoke-Step "$venvPython -m pytest backend/tests openwrt-agent/tests -q"
Invoke-Step "& 'C:\Program Files\Git\usr\bin\sh.exe' -n openwrt-agent/wrtmonitor-agent"

if (Get-Command shellcheck -ErrorAction SilentlyContinue) {
    Invoke-Step "shellcheck openwrt-agent/wrtmonitor-agent"
}
else {
    Write-Host "shellcheck not found locally, skipping"
}

Invoke-Step ".\gradlew.bat :android:app:testDebugUnitTest"
Invoke-Step ".\gradlew.bat :android:app:assembleDebug"

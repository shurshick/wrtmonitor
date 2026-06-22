param(
    [string]$PythonPath = "",
    [switch]$RecreateVenv
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $repoRoot ".venv"

function Resolve-CompatiblePython {
    param([string]$RequestedPath)

    if ($RequestedPath -and (Test-Path $RequestedPath)) {
        return (Resolve-Path $RequestedPath).Path
    }

    $candidates = @()

    try {
        $py312 = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $py312) { $candidates += $py312.Trim() }
    } catch {}

    try {
        $py313 = & py -3.13 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $py313) { $candidates += $py313.Trim() }
    } catch {}

    $bundled = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path $bundled) {
        $candidates += $bundled
    }

    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "Compatible Python 3.12/3.13 not found. Install Python 3.12 or pass -PythonPath."
}

$python = Resolve-CompatiblePython -RequestedPath $PythonPath
Write-Host "Using Python: $python"

if ($RecreateVenv -and (Test-Path $venvPath)) {
    Remove-Item -Recurse -Force $venvPath
}

if (-not (Test-Path $venvPath)) {
    & $python -m venv $venvPath
}

$venvPython = Join-Path $venvPath "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Failed to create .venv"
}

& $venvPython -m pip install --upgrade pip wheel setuptools
& $venvPython -m pip install -r (Join-Path $repoRoot "backend\requirements.txt")

Write-Host ""
Write-Host "Local environment is ready."
Write-Host "Python: $venvPython"
Write-Host "Run checks with: powershell -ExecutionPolicy Bypass -File .\scripts\check-local.ps1"

param(
    [string]$PythonExe = "",
    [switch]$NoStart,
    [switch]$SkipModels
)
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    if (-not $PythonExe) {
        $PythonExe = Join-Path $repoRoot '.venv\Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $PythonExe)) {
            $kitPath = if ($env:KIT_DIR) { $env:KIT_DIR } else { Join-Path $repoRoot 'rtx-ai-session-kit' }
            $PythonExe = Join-Path $kitPath '.venv\Scripts\python.exe'
        }
    }
    if (-not (Test-Path -LiteralPath $PythonExe)) {
        throw 'Python environment missing. Follow README setup or pass -PythonExe.'
    }
    if (-not $NoStart) {
        & docker compose -f compose.yaml up -d --build --wait --wait-timeout 120
        if ($LASTEXITCODE -ne 0) { throw 'Docker Compose failed. Inspect services before continuing.' }
    }
    $preflightArgs = @('-B', 'scripts/preflight.py')
    if ($SkipModels) { $preflightArgs += '--skip-models' }
    else { $preflightArgs += '--kit-smoke' }
    & $PythonExe @preflightArgs
    $checkExit = $LASTEXITCODE
    if ($checkExit -ne 0) { throw 'Readiness checks failed.' }
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
} finally {
    Pop-Location
}
exit 0

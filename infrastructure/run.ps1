# Uses the bundled Python when present; no permanent PATH changes.
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$suiteRoot = if ($env:OSS_CAD_SUITE) { $env:OSS_CAD_SUITE } else { Join-Path $repoRoot '.tools/oss-cad-suite' }
$bundledPython = Join-Path $suiteRoot 'lib/python3.exe'
if (Test-Path -LiteralPath $bundledPython) {
    & $bundledPython (Join-Path $PSScriptRoot 'run.py') @args
} else {
    & python (Join-Path $PSScriptRoot 'run.py') @args
}
exit $LASTEXITCODE

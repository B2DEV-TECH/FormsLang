param(
    [Parameter(Mandatory=$true)][string]$Engine,
    [Parameter(Mandatory=$true)][string]$Version,
    [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$enginePath = (Resolve-Path -LiteralPath $Engine).Path
$run = [System.IO.Path]::GetFullPath($Output)
if (Test-Path -LiteralPath $run) { throw "Beta journey output already exists: $run" }
$forms = Join-Path $run 'sources/forms'
$database = Join-Path $run 'sources/database'
New-Item -ItemType Directory -Force -Path $forms,$database | Out-Null

# One project: navigation evidence in CUSTOMERS/SHIPMENTS, eligible NOTICE scope.
Copy-Item -LiteralPath (Join-Path $repo 'formslang/demo/modernization/forms/customers.xml') -Destination $forms
Copy-Item -LiteralPath (Join-Path $repo 'formslang/demo/modernization/forms/shipments.xml') -Destination $forms
Copy-Item -LiteralPath (Join-Path $repo 'tests/fixtures/project-generation/notice.xml') -Destination $forms
Get-ChildItem -LiteralPath (Join-Path $repo 'formslang/demo/modernization/database') -File |
    Copy-Item -Destination $database

$env:FORMSLANG_CONFIG_DIR = Join-Path $run 'config'
$env:FORMSLANG_DATA_DIR = Join-Path $run 'data'
$env:FORMSLANG_AUTH = '0'
$env:FORMSLANG_SECRET_BACKEND = 'memory'
$reported = & $enginePath --version
if ($LASTEXITCODE -ne 0 -or $reported -ne "FormsLang $Version") {
    throw "Installed engine reported $reported instead of FormsLang $Version"
}
$project = Join-Path $run 'project'
$created = & $enginePath project create $project --name 'Synthetic beta A to B journey' --forms $forms --database $database --json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $created.project.source_roots.Count -ne 2) { throw 'Installed project creation failed' }
$analyzed = & $enginePath project analyze $project --json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $analyzed.status -ne 'COMPLETED') { throw 'Installed project analysis failed' }
$saved = & $enginePath project status $project --json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $saved.assessment.inventory.forms.analyzed -ne 3 -or
    $saved.assessment.inventory.database.package_bodies -ne 1) {
    throw 'Installed composite assessment did not retain three Forms and the package body'
}

# Required browser contract: open this saved project, inspect the resolved and
# unresolved CUSTOMERS edges, follow SHIPMENTS, and exercise NOTICE review,
# generation, validation, reports, and reopen through this installed engine.
python (Join-Path $repo 'examples/verify/installed_beta_browser_check.py') --engine $enginePath --project $project --output (Join-Path $run 'browser')
if ($LASTEXITCODE -ne 0) { throw 'Installed A to B browser journey failed' }
Write-Output "PASS: installed beta A to B journey on FormsLang $Version"

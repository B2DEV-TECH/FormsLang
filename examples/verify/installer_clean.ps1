param(
    [Parameter(Mandatory=$true)][ValidateSet('nsis','msi')][string]$Kind,
    [Parameter(Mandatory=$true)][string]$CandidateVersion
)
$ErrorActionPreference = 'Stop'
# This performs real installation; run only on a disposable hosted Windows runner.
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted') {
    throw 'Installer acceptance requires a disposable GitHub-hosted runner.'
}

$qaRoot = Join-Path $env:RUNNER_TEMP "formslang-installer-clean-$Kind"
$installDir = Join-Path $qaRoot 'install café'
$fileName = if ($Kind -eq 'msi') { "FormsLang_${CandidateVersion}_x64_en-US.msi" } else { "FormsLang_${CandidateVersion}_x64-setup.exe" }
$asset = (Resolve-Path "installer-assets/candidate/$fileName").Path
if (Test-Path -LiteralPath $installDir) { throw "Clean install directory already exists: $installDir" }
New-Item -ItemType Directory -Force -Path $qaRoot | Out-Null

if ($Kind -eq 'msi') {
    $log = Join-Path $qaRoot 'install.log'
    $installed = Start-Process msiexec.exe -WindowStyle Hidden -PassThru -Wait -ArgumentList @('/i', "`"$asset`"", '/qn', '/norestart', "INSTALLDIR=`"$installDir`"", '/l*v', "`"$log`"")
} else {
    $installed = Start-Process $asset -WindowStyle Hidden -PassThru -Wait -ArgumentList @('/S', "/D=$installDir")
}
if ($installed.ExitCode -notin @(0,3010)) { throw "Clean $Kind install exited $($installed.ExitCode)" }

$engine = Join-Path $installDir 'formslang-engine.exe'
$desktop = Join-Path $installDir 'formslang-desktop.exe'
if (-not (Test-Path -LiteralPath $engine)) { throw "Missing installed engine: $engine" }
if (-not (Test-Path -LiteralPath $desktop)) { throw "Missing installed desktop: $desktop" }

python examples/verify/installed_engine_check.py $engine (Join-Path $qaRoot 'acceptance') --version $CandidateVersion --phase seed
if ($LASTEXITCODE -ne 0) { throw 'Clean installed-engine acceptance failed' }
python examples/verify/project_engine_check.py --engine $engine --output (Join-Path $qaRoot 'project-acceptance')
if ($LASTEXITCODE -ne 0) { throw 'Clean installed project/review/generation/report acceptance failed' }
python examples/verify/installed_visual_check.py --engine $engine --version $CandidateVersion --output (Join-Path $qaRoot 'visual-acceptance')
if ($LASTEXITCODE -ne 0) { throw 'Clean installed browser journey failed' }

$app = Start-Process $desktop -WindowStyle Hidden -PassThru
try {
    $deadline = (Get-Date).AddSeconds(60)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        $app.Refresh()
        if ($app.HasExited) { throw 'Clean installed desktop exited during startup' }
        $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$($app.Id)"
        foreach ($child in $children) {
            if ($child.Name -eq 'formslang-engine.exe' -and $child.CommandLine -match '--port\s+"?(\d+)') {
                try {
                    $state = Invoke-RestMethod "http://127.0.0.1:$($Matches[1])/api/state" -TimeoutSec 2
                    if ($null -ne $state.stats -and $app.MainWindowHandle -ne 0) { $ready = $true }
                } catch { }
            }
        }
        if ($ready) { break }
        Start-Sleep -Milliseconds 250
    }
    if (-not $ready) { throw 'Clean installed desktop window and engine did not become ready' }
    Write-Output 'PASS: clean installed desktop creates its native window and starts its engine'
} finally {
    if (-not $app.HasExited) {
        $null = $app.CloseMainWindow()
        if (-not $app.WaitForExit(10000)) { taskkill /PID $app.Id /T /F | Out-Null }
    }
}

# Leave the runner's ephemeral installation for evidence collection; the runner
# is discarded after the job. Upgrade acceptance separately tests uninstall.
Write-Output "PASS: clean $Kind candidate installation at a non-ASCII user-space path"

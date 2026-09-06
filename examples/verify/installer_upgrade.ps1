param(
    [Parameter(Mandatory=$true)][ValidateSet('nsis','msi')][string]$Kind,
    [Parameter(Mandatory=$true)][string]$BaselineVersion,
    [Parameter(Mandatory=$true)][string]$CandidateVersion
)
$ErrorActionPreference = 'Stop'
# This performs real installation; run only on a disposable hosted Windows runner.
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted') {
    throw 'Installer acceptance requires a disposable GitHub-hosted runner.'
}
$qaRoot = Join-Path $env:RUNNER_TEMP "formslang-installer-$Kind"
$installDir = Join-Path $qaRoot 'installed'
New-Item -ItemType Directory -Force -Path $qaRoot | Out-Null
function Install-Version([string]$Version, [string]$Phase) {
    $fileName = if ($Kind -eq 'msi') { "FormsLang_${Version}_x64_en-US.msi" } else { "FormsLang_${Version}_x64-setup.exe" }
    $asset = (Resolve-Path "installer-assets/$Phase/$fileName").Path
    if ($Kind -eq 'msi') {
        $log = Join-Path $qaRoot "$Phase-install.log"
        $process = Start-Process msiexec.exe -WindowStyle Hidden -PassThru -Wait -ArgumentList @('/i', "`"$asset`"", '/qn', '/norestart', "INSTALLDIR=`"$installDir`"", '/l*v', "`"$log`"")
    } else {
        $process = Start-Process $asset -WindowStyle Hidden -PassThru -Wait -ArgumentList @('/S', "/D=$installDir")
    }
    if ($process.ExitCode -notin @(0,3010)) { throw "$Phase installer exited $($process.ExitCode)" }
    $engine = Join-Path $installDir 'formslang-engine.exe'
    if (-not (Test-Path -LiteralPath $engine)) { throw "Missing installed engine: $engine" }
    python examples/verify/installed_engine_check.py $engine (Join-Path $qaRoot 'acceptance') --version $Version --phase $(if ($Phase -eq 'baseline') { 'seed' } else { 'verify' })
    if ($LASTEXITCODE -ne 0) { throw "$Phase installed-engine acceptance failed" }
}
Install-Version $BaselineVersion 'baseline'
Install-Version $CandidateVersion 'candidate'
$desktop = Join-Path $installDir 'formslang-desktop.exe'
$app = Start-Process $desktop -WindowStyle Hidden -PassThru
try {
    $deadline = (Get-Date).AddSeconds(60)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        $app.Refresh()
        if ($app.HasExited) { throw 'Installed desktop exited during startup' }
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
    if (-not $ready) { throw 'Installed desktop window and engine did not become ready' }
    Write-Output 'PASS: installed desktop creates its native window and starts its engine'
} finally {
    if (-not $app.HasExited) {
        $null = $app.CloseMainWindow()
        if (-not $app.WaitForExit(10000)) {
            taskkill /PID $app.Id /T /F | Out-Null
        }
    }
}
Write-Output "PASS: $Kind clean installation and upgrade $BaselineVersion -> $CandidateVersion"

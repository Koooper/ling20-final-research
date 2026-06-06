#requires -version 5.1
<#
  setup.ps1 - one-shot environment bootstrap for the Lakota Obstruents analysis pipeline.

  Gets a working Python, builds an isolated virtual environment (venv), and installs the
  pinned packages from requirements.txt. Built to run on a stock Windows laptop with no
  prior Python knowledge and NO administrator rights.

  Easiest way to run: double-click setup.cmd (it calls this with the right settings).
  Or from PowerShell:  powershell -ExecutionPolicy Bypass -File .\setup.ps1

  Re-running is safe (idempotent). Use -Recreate to rebuild the environment from scratch.

  Targets Windows PowerShell 5.1 (the version on a stock Windows machine), so it avoids
  PowerShell 7-only syntax on purpose.
#>
[CmdletBinding()]
param(
    [switch]$Recreate
)

$ErrorActionPreference = 'Stop'

# --- friendly output ---------------------------------------------------------
function Say    ($m) { Write-Host $m }
function Step   ($m) { Write-Host ""; Write-Host ">> $m" -ForegroundColor Cyan }
function Good   ($m) { Write-Host "   [ok] $m" -ForegroundColor Green }
function Note   ($m) { Write-Host "   $m"      -ForegroundColor DarkGray }
function Warned ($m) { Write-Host "   [!] $m"  -ForegroundColor Yellow }
function Failed ($m) { Write-Host ""; Write-Host "XX $m" -ForegroundColor Red }

# --- settings ----------------------------------------------------------------
$PyTarget   = '3.12'      # version to install when none is found
$PyFull     = '3.12.8'    # exact installer to download as a last resort (bump as needed)
$MinMinor   = 10          # accept an existing Python 3.10 .. 3.13
$MaxMinorEx = 14
$RepoRoot   = $PSScriptRoot
$ReqFile    = Join-Path $RepoRoot 'requirements.txt'

# Force modern TLS so HTTPS downloads don't silently fail on older Windows PowerShell.
try {
    [Net.ServicePointManager]::SecurityProtocol = `
        [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
} catch {
    try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
}

Write-Host ""
Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host "  Lakota Obstruents pipeline - environment setup"             -ForegroundColor Cyan
Write-Host "=============================================================" -ForegroundColor Cyan
Note "Repo: $RepoRoot"

if (-not (Test-Path $ReqFile)) {
    Failed "Can't find requirements.txt next to this script."
    Note "Make sure setup.ps1 sits in the repository's top folder (next to requirements.txt)."
    exit 1
}

# --- find an existing, usable Python -----------------------------------------
# Returns an object {Exe, Pre, Version, Path} or $null. Screens out the Microsoft
# Store stub and anything outside the accepted 3.10..3.13 range.
function Test-Interpreter {
    param([string]$Exe, [string[]]$Pre = @())
    try {
        $code = 'import sys; print("%d.%d.%d" % sys.version_info[:3]); print(sys.executable)'
        $out = & $Exe @Pre -c $code 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $out) { return $null }
        $lines = @($out)
        $ver  = $lines[0].Trim()
        $path = $lines[-1].Trim()
        if ($path -like '*\WindowsApps\*') { return $null }   # Microsoft Store stub - avoid
        $p = $ver.Split('.')
        $maj = [int]$p[0]; $min = [int]$p[1]
        if ($maj -ne 3 -or $min -lt $MinMinor -or $min -ge $MaxMinorEx) { return $null }
        return [pscustomobject]@{ Exe = $Exe; Pre = $Pre; Version = $ver; Path = $path }
    } catch {
        return $null
    }
}

function Update-PathFromRegistry {
    $machine = [Environment]::GetEnvironmentVariable('Path','Machine')
    $user    = [Environment]::GetEnvironmentVariable('Path','User')
    $env:Path = @($machine, $user | Where-Object { $_ }) -join ';'
}

# Most reliable detection: the registry keys the 'py' launcher itself reads. This works
# even if Python isn't on PATH (e.g. installed without "Add to PATH") and regardless of
# the current process environment.
function Find-PythonFromRegistry {
    $hives = @(
        'HKCU:\SOFTWARE\Python\PythonCore',
        'HKLM:\SOFTWARE\Python\PythonCore',
        'HKLM:\SOFTWARE\WOW6432Node\Python\PythonCore'
    )
    $cands = @()
    foreach ($hive in $hives) {
        if (-not (Test-Path $hive)) { continue }
        foreach ($k in (Get-ChildItem $hive -ErrorAction SilentlyContinue)) {
            $ipKey = Join-Path $k.PSPath 'InstallPath'
            if (-not (Test-Path $ipKey)) { continue }
            $props = Get-ItemProperty -Path $ipKey -ErrorAction SilentlyContinue
            $exe = $null
            if ($props.ExecutablePath) { $exe = $props.ExecutablePath }
            elseif ($props.'(default)') { $exe = Join-Path $props.'(default)' 'python.exe' }
            if ($exe -and (Test-Path $exe)) {
                $cands += [pscustomobject]@{ Key = $k.PSChildName; Exe = $exe }
            }
        }
    }
    if (-not $cands) { return $null }
    # prefer 3.12, then 3.13/3.11/3.10; ignore 32-bit/out-of-range via Test-Interpreter
    $order = @{ '3.12' = 0; '3.13' = 1; '3.11' = 2; '3.10' = 3 }
    $ranked = $cands | Sort-Object @{ Expression = {
        $base = ($_.Key -replace '-.*$',''); if ($order.ContainsKey($base)) { $order[$base] } else { 99 } } }
    foreach ($c in $ranked) {
        $r = Test-Interpreter -Exe $c.Exe
        if ($r) { return $r }
    }
    return $null
}



function Find-Python {
    $r = "C:\Users\djjr6\AppData\Local\Programs\Python\Python312\python.exe"
    return $r
}

# --- install Python when none is found (no admin) ----------------------------
function Install-Python {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Step "No suitable Python found - installing Python $PyTarget with winget (no admin needed)."
        try {
            & winget install -e --id "Python.Python.$PyTarget" --scope user --silent `
                --accept-package-agreements --accept-source-agreements | Out-Null
        } catch {
            Warned "winget reported: $($_.Exception.Message)"
        }
        Update-PathFromRegistry
        $r = Find-Python
        if ($r) { return $r }
        Warned "winget didn't produce a usable Python; falling back to the official installer."
    } else {
        Step "winget isn't available - downloading the official Python $PyFull installer."
    }

    # official python.org installer, per-user, fully silent
    $arch = 'amd64'
    if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { $arch = 'arm64' }
    $url = "https://www.python.org/ftp/python/$PyFull/python-$PyFull-$arch.exe"
    $dst = Join-Path $env:TEMP "python-$PyFull-$arch.exe"
    Note "Downloading $url"
    try {
        Invoke-WebRequest -Uri $url -OutFile $dst -UseBasicParsing
    } catch {
        Failed "Couldn't download the Python installer."
        Note "Check your internet connection, or install Python $PyTarget by hand from"
        Note "  https://www.python.org/downloads/  (tick 'Add python.exe to PATH'), then re-run."
        exit 1
    }
    Note "Running the installer quietly (this can take a minute)..."
    $args = @('/quiet','InstallAllUsers=0','PrependPath=1','Include_launcher=1',
              'Include_pip=1','Include_test=0')
    $proc = Start-Process -FilePath $dst -ArgumentList $args -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        Warned "Installer exit code $($proc.ExitCode) (it may still have worked - checking)."
    }
    Update-PathFromRegistry
    $r = Find-Python
    if ($r) { return $r }
    Failed "Python still isn't detected after the install attempt."
    Note "Please install Python $PyTarget from https://www.python.org/downloads/"
    Note "(tick 'Add python.exe to PATH' on the first screen), then run this again."
    exit 1
}

Step "Looking for a usable Python (3.$MinMinor or newer)..."
$py = Find-Python
if ($py) {
    Good "Found Python $($py.Version)"
    Note $py.Path
} else {
    $py = Install-Python
    Good "Python ready: $($py.Version)"
    Note $py.Path
}

# --- pick the venv location --------------------------------------------------
# Normally the env lives in the repo as .venv. But if the repo is inside OneDrive,
# a venv (thousands of files) would get sync-churned and locked, so put it under
# LocalAppData instead. The user never has to care where it is.
$venvHome = Join-Path $RepoRoot '.venv'
if ($RepoRoot -match 'OneDrive') {
    $venvHome = Join-Path $env:LOCALAPPDATA 'LakotaObstruents\venv'
    Note "Repo is inside OneDrive - putting the environment outside it to avoid sync trouble:"
    Note "  $venvHome"
}

Step "Setting up the isolated Python environment (venv)..."
if ((Test-Path $venvHome) -and $Recreate) {
    Note "Removing the existing environment (-Recreate)."
    Remove-Item -Path $venvHome -Recurse -Force
}
$venvPy = Join-Path $venvHome 'Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
    $parent = Split-Path -Parent $venvHome
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    & $py.Exe @($py.Pre) -m venv $venvHome
    if (-not (Test-Path $venvPy)) {
        Failed "Could not create the virtual environment."
        Note "If this keeps happening, re-run with:  powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Recreate"
        exit 1
    }
    Good "Environment created."
} else {
    Good "Reusing the existing environment (use -Recreate to rebuild)."
}

# --- install dependencies ----------------------------------------------------
Step "Installing the Python packages (this is the slow part - a few minutes)..."
& $venvPy -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { Warned "Could not upgrade pip; continuing anyway." }
& $venvPy -m pip install -r $ReqFile
if ($LASTEXITCODE -ne 0) {
    Failed "Installing the packages failed."
    Note "This is usually a flaky internet connection. Re-run setup to try again."
    exit 1
}
Good "Packages installed."

# --- verify ------------------------------------------------------------------
Step "Checking that everything imports..."
$probe = 'import pandas, numpy, scipy, matplotlib, seaborn, sklearn, yaml, openpyxl; print("IMPORTS_OK")'
$res = & $venvPy -c $probe 2>&1
if ($LASTEXITCODE -ne 0 -or ("$res" -notmatch 'IMPORTS_OK')) {
    Failed "The packages installed, but at least one failed to import:"
    $res | ForEach-Object { Note $_ }
    Note "Re-run with -Recreate to rebuild the environment cleanly."
    exit 1
}
Good "All required packages import cleanly."

# --- pre-create the derived-data folder tree ---------------------------------
# Praat's createFolder is NOT recursive: 02/02b write to data\derived\extraction and choke if
# data\derived doesn't already exist. PowerShell's New-Item -Force makes parents, so we touch
# the whole tree here once. Idempotent; these dirs are .gitignored (only their contents matter).
Step "Pre-creating the data\derived output folders (Praat can't make nested dirs)..."
$derivedDirs = @(
    'data\derived',
    'data\derived\extraction',
    'data\derived\merged',
    'data\derived\validation',
    'output',
    'figures',
    'figures\formant_winners'
)
foreach ($d in $derivedDirs) {
    $full = Join-Path $RepoRoot $d
    if (-not (Test-Path $full)) { New-Item -ItemType Directory -Path $full -Force | Out-Null }
}
Good "Output folders ready."

# --- record the env location for the run scripts -----------------------------
$ptr = Join-Path $RepoRoot '.venv-path'
Set-Content -Path $ptr -Value $venvPy -Encoding ASCII

# --- done --------------------------------------------------------------------
Write-Host ""
Write-Host "=============================================================" -ForegroundColor Green
Write-Host "  All set. The analysis environment is ready."                 -ForegroundColor Green
Write-Host "=============================================================" -ForegroundColor Green
Note "Python:      $($py.Version)"
Note "Environment: $venvHome"
Note "Pointer:     $ptr  (the run scripts read this - leave it alone)"
Write-Host ""
Say "You do NOT need to 'activate' anything. When the analysis tools exist, they'll"
Say "use this environment automatically. To run a Python file by hand:"
Write-Host "    & `"$venvPy`" path\to\script.py" -ForegroundColor White
Write-Host ""
exit 0

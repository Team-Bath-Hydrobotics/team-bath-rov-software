$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "winget was not found. Downloading Microsoft's signed App Installer package..."

    $wingetBundle = Join-Path $env:TEMP "Microsoft.DesktopAppInstaller.msixbundle"
    $wingetUrl = "https://github.com/microsoft/winget-cli/releases/latest/download/Microsoft.DesktopAppInstaller_8wekyb3d8bbwe.msixbundle"

    try {
        Invoke-WebRequest -Uri $wingetUrl -OutFile $wingetBundle
        Add-AppxPackage -Path $wingetBundle
    } catch {
        throw "winget could not be installed automatically. Install App Installer from the Microsoft Store, then rerun this script. Details: $($_.Exception.Message)"
    } finally {
        if (Test-Path $wingetBundle) {
            Remove-Item $wingetBundle -Force
        }
    }

    $windowsApps = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps"
    $env:Path = "$windowsApps;$env:Path"
}

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw "winget was installed but is not available in this PowerShell session. Open a new PowerShell window and rerun this script."
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

function Install-WingetPackage {
    param([Parameter(Mandatory = $true)][string]$Id)
    winget install --id $Id --exact --accept-package-agreements --accept-source-agreements
}

Write-Host "Installing prerequisites..."
Install-WingetPackage "Git.Git"
Install-WingetPackage "Docker.DockerDesktop"
Install-WingetPackage "Python.Python.3.11"
Install-WingetPackage "OpenJS.NodeJS.LTS"
Install-WingetPackage "Gyan.FFmpeg"
Install-WingetPackage "FiloSottile.mkcert"

# Refresh PATH for tools installed by winget during this process.
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
    [Environment]::GetEnvironmentVariable("Path", "User")

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' was not found. Open a new PowerShell window and rerun this script."
}

$pythonPath = (& py -3.11 -c "import sys; print(sys.executable)").Trim()
if (-not (Test-Path $pythonPath)) {
    throw "Python 3.11 was not found. Open a new PowerShell window and rerun this script."
}

$uiRoot = Join-Path (Split-Path -Parent $repoRoot) "team-bath-rov-secondary-ui"
if (-not (Test-Path $uiRoot)) {
    throw "Secondary UI repository was not found at $uiRoot. Clone it beside team-bath-rov-software first."
}

Push-Location $uiRoot
try {
    npm install
} finally {
    Pop-Location
}

& py -3.11 -m pip install --user pipx
& py -3.11 -m pipx ensurepath

$userScripts = Join-Path $env:USERPROFILE "AppData\Roaming\Python\Python311\Scripts"
$env:Path = "$userScripts;$env:Path"

if (Get-Command poetry -ErrorAction SilentlyContinue) {
    Write-Host "Poetry is already installed; skipping."
} else {
    & py -3.11 -m pipx install poetry
}

foreach ($service in @("telemetry-processor", "video-processor", "packet-simulator")) {
    Push-Location (Join-Path $repoRoot $service)
    try {
        poetry env use $pythonPath
        poetry install --no-interaction
    } finally {
        Pop-Location
    }
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    $dockerDesktop = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerDesktop) {
        Write-Host "Starting Docker Desktop..."
        Start-Process $dockerDesktop
    }

    $dockerReady = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Seconds 2
        docker info *> $null
        if ($LASTEXITCODE -eq 0) {
            $dockerReady = $true
            break
        }
    }
    if (-not $dockerReady) {
        throw "Docker Desktop did not become ready. A Windows restart, WSL 2 setup, or virtualization may be required. Start Docker Desktop and rerun the script."
    }
}

$mqttRoot = Join-Path $repoRoot "mqtt"
$passwordFile = Join-Path $mqttRoot "PASSWORD"
if (-not (Test-Path $passwordFile)) {
    $password = Read-Host "Enter the HiveMQ keystore password" -AsSecureString
    $confirmation = Read-Host "Confirm the HiveMQ keystore password" -AsSecureString

    $passwordPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
    $confirmationPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($confirmation)
    try {
        $passwordText = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPtr)
        $confirmationText = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($confirmationPtr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPtr)
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($confirmationPtr)
    }

    if ([string]::IsNullOrWhiteSpace($passwordText) -or $passwordText -cne $confirmationText) {
        throw "Passwords did not match or were empty."
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($passwordFile, "HIVEMQ_KEYSTORE_PASSWORD=$passwordText`n", $utf8NoBom)
} else {
    Write-Host "mqtt/PASSWORD already exists; leaving it unchanged."
    $existingPassword = Select-String -Path $passwordFile -Pattern '^HIVEMQ_KEYSTORE_PASSWORD=(.+)$'
    if (-not $existingPassword) {
        throw "mqtt/PASSWORD exists but contains an empty or invalid keystore password."
    }
}

$bashCandidates = @(
    (Join-Path $env:ProgramFiles "Git\bin\bash.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Git\bin\bash.exe")
)
$bashPath = $bashCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $bashPath) {
    throw "Git Bash was not found. Open a new PowerShell window and rerun this script."
}

& $bashPath -lc "cd -- '$mqttRoot' && ./create_keystore.sh"
if ($LASTEXITCODE -ne 0) {
    throw "MQTT keystore creation failed."
}

Write-Host "Windows setup complete. Starting all services..."
& $pythonPath (Join-Path $repoRoot "scripts\run-all.py")
if ($LASTEXITCODE -ne 0) {
    throw "run-all.py exited with code $LASTEXITCODE."
}

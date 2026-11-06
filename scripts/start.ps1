. (Join-Path $PSScriptRoot "env.ps1")

$dockerReady = $false
try {
    docker info --format "{{.ServerVersion}}" | Out-Null
    $dockerReady = ($LASTEXITCODE -eq 0)
}
catch {
    $dockerReady = $false
}

if (-not $dockerReady) {
    $dockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path -LiteralPath $dockerDesktop)) {
        throw "Docker Desktop is not installed at $dockerDesktop."
    }

    Write-Host "Starting Docker Desktop..."
    Start-Process -FilePath $dockerDesktop -WindowStyle Hidden

    $deadline = (Get-Date).AddMinutes(4)
    do {
        Start-Sleep -Seconds 5
        docker info --format "{{.ServerVersion}}" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $dockerReady = $true
            break
        }
    } while ((Get-Date) -lt $deadline)
}

if (-not $dockerReady) {
    throw "Docker engine did not become ready."
}

$jar = Join-Path $LabRoot "litemall\litemall-all.jar"
if (-not (Test-Path -LiteralPath $jar)) {
    throw "Application jar is missing. Run scripts\build.ps1 first."
}

docker compose up -d
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose startup failed."
}

docker compose ps

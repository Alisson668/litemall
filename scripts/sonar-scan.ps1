. (Join-Path $PSScriptRoot "env.ps1")

$sonarUrl = "http://localhost:9000"
$ready = $false
$deadline = (Get-Date).AddMinutes(3)

while ((Get-Date) -lt $deadline) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "$sonarUrl/api/system/status" -TimeoutSec 5
        if ($response.Content -match '"status"\s*:\s*"UP"') {
            $ready = $true
            break
        }
    }
    catch {
    }
    Start-Sleep -Seconds 5
}

if (-not $ready) {
    throw "SonarQube is not ready at $sonarUrl."
}

sonar-scanner
if ($LASTEXITCODE -ne 0) {
    throw "SonarScanner failed."
}

Write-Host "Scan complete: $sonarUrl/dashboard?id=litemall"

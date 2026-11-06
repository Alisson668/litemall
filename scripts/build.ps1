. (Join-Path $PSScriptRoot "env.ps1")

Write-Host "Building litemall with Java 8..."
mvn clean package -DskipTests
if ($LASTEXITCODE -ne 0) {
    throw "Maven build failed."
}

$sourceJar = Join-Path $LabRoot "litemall-all\target\litemall-all-0.1.0-exec.jar"
$targetDir = Join-Path $LabRoot "litemall"
$targetJar = Join-Path $targetDir "litemall-all.jar"

if (-not (Test-Path -LiteralPath $sourceJar)) {
    throw "Built jar not found: $sourceJar"
}

New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
Copy-Item -LiteralPath $sourceJar -Destination $targetJar -Force
Write-Host "Application jar ready: $targetJar"

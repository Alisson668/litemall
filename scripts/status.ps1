. (Join-Path $PSScriptRoot "env.ps1")

docker compose ps
Write-Host ""
Write-Host "Litemall : http://localhost:8080"
Write-Host "SonarQube: http://localhost:9000  (admin / admin)"
Write-Host "Grafana  : http://localhost:3000  (admin / admin)"
Write-Host "Prometheus: http://localhost:9090"
Write-Host "MySQL    : localhost:3307  (litemall / litemall123456)"

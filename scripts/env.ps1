$ErrorActionPreference = "Stop"

$script:LabRoot = Split-Path -Parent $PSScriptRoot
$script:DevToolsRoot = "D:\DevTools"
$script:JavaHome = Join-Path $DevToolsRoot "jdk8"
$script:MavenRepository = Join-Path $DevToolsRoot "maven-repository"
$script:SonarScannerHome = Join-Path $DevToolsRoot "sonar-scanner"
$script:SonarCache = Join-Path $DevToolsRoot "sonar-cache"
$script:PythonVenv = Join-Path $DevToolsRoot "venvs\litemall-lab"

New-Item -ItemType Directory -Path $MavenRepository,$SonarCache -Force | Out-Null

$requiredPaths = @(
    (Join-Path $JavaHome "bin\java.exe"),
    (Join-Path $SonarScannerHome "bin\sonar-scanner.bat"),
    (Join-Path $PythonVenv "Scripts\python.exe")
)

foreach ($path in $requiredPaths) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required tool is missing: $path"
    }
}

$env:JAVA_HOME = $JavaHome
$env:MAVEN_OPTS = "-Dmaven.repo.local=$($MavenRepository.Replace('\', '/')) -Dfile.encoding=UTF-8"
$env:SONAR_SCANNER_HOME = $SonarScannerHome
$env:SONAR_USER_HOME = $SonarCache
$env:PATH = @(
    (Join-Path $JavaHome "bin"),
    (Join-Path $SonarScannerHome "bin"),
    (Join-Path $PythonVenv "Scripts"),
    $env:PATH
) -join ";"

Set-Location -LiteralPath $LabRoot

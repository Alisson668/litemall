param(
    [switch]$SkipTests,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "env.ps1")

$experimentRoot = Join-Path $LabRoot "experiment-3"
$evidenceDir = Join-Path $experimentRoot "evidence"
$openApiDir = Join-Path $experimentRoot "openapi"
New-Item -ItemType Directory -Path $evidenceDir,$openApiDir -Force | Out-Null

function Remove-GeneratedFile([string]$path) {
    if (-not (Test-Path -LiteralPath $path)) {
        return
    }
    $resolved = (Resolve-Path -LiteralPath $path).Path
    if (-not $resolved.StartsWith($LabRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a file outside the lab workspace: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Force
}

if (-not $SkipTests) {
    Remove-GeneratedFile (Join-Path $LabRoot "litemall-wx-api\target\jacoco.exec")
    Write-Host "Running Experiment 3 contract and fuzz tests..."
    $mavenArgs = @(
        "-pl", "litemall-wx-api",
        "-am",
        "-Dmaven.test.skip=false",
        "-Dtest=WxOrderSubmitContractTest,WxOrderSubmitFuzzTest",
        "-Dsurefire.failIfNoSpecifiedTests=false",
        "test"
    )
    & mvn.cmd @mavenArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Experiment 3 tests failed."
    }
}

if (-not $SkipBuild) {
    Write-Host "Packaging the fixed application..."
    & mvn.cmd package "-DskipTests"
    if ($LASTEXITCODE -ne 0) {
        throw "Maven package failed."
    }

    $sourceJar = Join-Path $LabRoot "litemall-all\target\litemall-all-0.1.0-exec.jar"
    $targetDir = Join-Path $LabRoot "litemall"
    $targetJar = Join-Path $targetDir "litemall-all.jar"
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    Copy-Item -LiteralPath $sourceJar -Destination $targetJar -Force

    docker compose restart litemall
    if ($LASTEXITCODE -ne 0) {
        throw "Could not restart litemall."
    }

    $deadline = (Get-Date).AddMinutes(2)
    $ready = $false
    do {
        Start-Sleep -Seconds 3
        try {
            $health = Invoke-WebRequest -UseBasicParsing `
                -Uri "http://localhost:8080/wx/home/index" -TimeoutSec 5
            $ready = $health.StatusCode -eq 200
        }
        catch {
            $ready = $false
        }
    } while (-not $ready -and (Get-Date) -lt $deadline)
    if (-not $ready) {
        throw "litemall did not become ready."
    }
}

$testReports = Get-ChildItem `
    -Path (Join-Path $LabRoot "litemall-wx-api\target\surefire-reports") `
    -Filter "*WxOrderSubmit*" -File -ErrorAction SilentlyContinue
foreach ($report in $testReports) {
    Copy-Item -LiteralPath $report.FullName -Destination $evidenceDir -Force
}

$swaggerPath = Join-Path $openApiDir "wx-api-swagger.json"
$swagger = Invoke-WebRequest -UseBasicParsing `
    -Uri "http://localhost:8080/v2/api-docs?group=wx" `
    -OutFile $swaggerPath -PassThru -TimeoutSec 30
if ($swagger.StatusCode -ne 200) {
    throw "Could not export Swagger document."
}

function ConvertTo-Base64Url([byte[]]$bytes) {
    [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

function New-TestToken([int]$userId = 7) {
    $header = '{"alg":"HS256","typ":"JWT"}'
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $payload = "{`"userId`":$userId,`"iss`":`"LITEMALL`",`"sub`":`"this is litemall token`",`"aud`":[`"MINIAPP`"],`"iat`":$now,`"exp`":$($now + 7200)}"
    $unsigned = (ConvertTo-Base64Url ([Text.Encoding]::UTF8.GetBytes($header))) +
        "." + (ConvertTo-Base64Url ([Text.Encoding]::UTF8.GetBytes($payload)))
    $hmac = New-Object System.Security.Cryptography.HMACSHA256
    $hmac.Key = [Text.Encoding]::UTF8.GetBytes("X-Litemall-Token")
    $signature = ConvertTo-Base64Url ($hmac.ComputeHash(
        [Text.Encoding]::UTF8.GetBytes($unsigned)))
    return $unsigned + "." + $signature
}

function Invoke-FuzzCase(
    [string]$name,
    [string]$category,
    [string]$method,
    [string]$token,
    [string]$accept,
    [string]$contentType,
    [string]$body,
    [int]$expectedStatus,
    [int]$expectedErrno
) {
    $headers = @{ Accept = $accept }
    if ($token -ne "") {
        $headers["X-Litemall-Token"] = $token
    }
    $parameters = @{
        UseBasicParsing = $true
        Uri = "http://localhost:8080/wx/order/submit"
        Method = $method
        Headers = $headers
        TimeoutSec = 20
    }
    if ($contentType -ne "") {
        $parameters.ContentType = $contentType
    }
    if ($body -ne "") {
        $parameters.Body = $body
    }

    try {
        $response = Invoke-WebRequest @parameters
        $status = [int]$response.StatusCode
        $responseBody = $response.Content
    }
    catch {
        $webResponse = $_.Exception.Response
        if ($null -eq $webResponse) {
            throw
        }
        $reader = New-Object System.IO.StreamReader($webResponse.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        $reader.Dispose()
        $status = [int]$webResponse.StatusCode
    }

    $errno = $null
    if ($responseBody -ne "") {
        try {
            $errno = ($responseBody | ConvertFrom-Json).errno
        }
        catch {
            $errno = $null
        }
    }
    $passed = $status -eq $expectedStatus
    if ($expectedErrno -ne 0) {
        $passed = $passed -and $errno -eq $expectedErrno
    }
    return [pscustomobject]@{
        name = $name
        category = $category
        httpStatus = $status
        errno = $errno
        expectedHttpStatus = $expectedStatus
        expectedErrno = $expectedErrno
        passed = $passed
        responseBody = $responseBody
    }
}

$token = New-TestToken
$largeMessage = "x" * 65536
$largeBody = "{`"cartId`":1,`"addressId`":2,`"couponId`":0,`"message`":`"$largeMessage`"}"
$results = @(
    (Invoke-FuzzCase "valid-shape-missing-address" "normal" "Post" $token `
        "application/json" "application/json" `
        '{"cartId":1,"addressId":2,"couponId":0}' 200 401),
    (Invoke-FuzzCase "text-integer" "type-confusion" "Post" $token `
        "application/json" "application/json" `
        '{"cartId":"1","addressId":"2","couponId":0}' 200 402),
    (Invoke-FuzzCase "boolean-integer" "type-confusion" "Post" $token `
        "application/json" "application/json" `
        '{"cartId":true,"addressId":2,"couponId":0}' 200 402),
    (Invoke-FuzzCase "sql-injection" "security" "Post" $token `
        "application/json" "application/json" `
        '{"cartId":1,"addressId":"2 UNION SELECT 1","couponId":0}' 200 402),
    (Invoke-FuzzCase "integer-overflow" "extreme-value" "Post" $token `
        "application/json" "application/json" `
        '{"cartId":1,"addressId":2147483648,"couponId":0}' 200 402),
    (Invoke-FuzzCase "negative-address" "extreme-value" "Post" $token `
        "application/json" "application/json" `
        '{"cartId":1,"addressId":-2,"couponId":0}' 200 402),
    (Invoke-FuzzCase "malformed-json" "encoding" "Post" $token `
        "application/json" "application/json" "{" 200 402),
    (Invoke-FuzzCase "array-root" "type-confusion" "Post" $token `
        "application/json" "application/json" "[]" 200 402),
    (Invoke-FuzzCase "plain-text" "encoding" "Post" $token `
        "application/json" "text/plain" `
        '{"cartId":1,"addressId":2,"couponId":0}' 415 415),
    (Invoke-FuzzCase "missing-token" "authentication" "Post" "" `
        "application/json" "application/json" `
        '{"cartId":1,"addressId":2,"couponId":0}' 200 501),
    (Invoke-FuzzCase "invalid-token" "authentication" "Post" "not-a-jwt" `
        "application/json" "application/json" `
        '{"cartId":1,"addressId":2,"couponId":0}' 200 501),
    (Invoke-FuzzCase "wrong-method" "contract" "Get" $token `
        "application/json" "" "" 405 405),
    (Invoke-FuzzCase "unsupported-accept" "contract" "Post" $token `
        "text/plain" "application/json" `
        '{"cartId":1,"addressId":2,"couponId":0}' 406 0),
    (Invoke-FuzzCase "body-user-id" "idor" "Post" $token `
        "application/json" "application/json" `
        '{"userId":999,"cartId":1,"addressId":2,"couponId":0}' 200 401),
    (Invoke-FuzzCase "oversized-message" "extreme-value" "Post" $token `
        "application/json" "application/json" $largeBody 200 401)
)

$idorAddressId = 900001
$idorCartId = 900001
$fixtureSql = @"
USE litemall;
DELETE FROM litemall_address WHERE id = $idorAddressId;
DELETE FROM litemall_cart WHERE id = $idorCartId;
INSERT INTO litemall_address
    (id, name, user_id, province, city, county, address_detail, tel,
     is_default, add_time, update_time, deleted)
VALUES
    ($idorAddressId, 'IDOR Fixture', 7, 'Test Province', 'Test City',
     'Test County', 'Experiment 3 temporary address', '13800000000',
     0, NOW(), NOW(), 0);
INSERT INTO litemall_cart
    (id, user_id, goods_id, goods_sn, goods_name, product_id, price,
     number, specifications, checked, add_time, update_time, deleted)
VALUES
    ($idorCartId, 999, 1, 'IDOR-GOODS', 'Cross-user cart fixture', 1,
     1.00, 1, '[]', 1, NOW(), NOW(), 0);
"@
try {
    $fixtureOutput = & docker exec -e MYSQL_PWD=litemall123456 litemall-mysql `
        mysql -uroot -N -e $fixtureSql
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create the live IDOR fixture: $fixtureOutput"
    }
    $idorResult = Invoke-FuzzCase "cross-user-cart" "idor" "Post" $token `
        "application/json" "application/json" `
        "{`"cartId`":$idorCartId,`"addressId`":$idorAddressId,`"couponId`":0}" `
        200 402
}
finally {
    $cleanupSql = @"
USE litemall;
DELETE FROM litemall_address WHERE id = $idorAddressId;
DELETE FROM litemall_cart WHERE id = $idorCartId;
"@
    $cleanupOutput = & docker exec -e MYSQL_PWD=litemall123456 litemall-mysql `
        mysql -uroot -N -e $cleanupSql
    if ($LASTEXITCODE -ne 0) {
        throw "Could not clean the live IDOR fixture: $cleanupOutput"
    }
}
$results += $idorResult

$results | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath (Join-Path $evidenceDir "live-final-results.json") `
        -Encoding UTF8

$summary = [pscustomobject]@{
    collectedAt = (Get-Date).ToString("yyyy-MM-dd HH:mm:ssK")
    endpoint = "http://localhost:8080/wx/order/submit"
    cases = $results.Count
    passed = @($results | Where-Object { $_.passed }).Count
    failed = @($results | Where-Object { -not $_.passed }).Count
    statusCodesObserved = @($results | ForEach-Object { $_.httpStatus } | Sort-Object -Unique)
    serverErrorsObserved = @($results | Where-Object { $_.httpStatus -ge 500 }).Count
    swaggerFile = "experiment-3/openapi/wx-api-swagger.json"
}
$summary | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath (Join-Path $evidenceDir "live-summary.json") `
        -Encoding UTF8

$results | Select-Object name,category,httpStatus,errno,passed |
    Format-Table -AutoSize
$summary | Format-List

if ($summary.failed -ne 0 -or $summary.serverErrorsObserved -ne 0) {
    throw "Live Experiment 3 fuzzing did not satisfy the contract."
}

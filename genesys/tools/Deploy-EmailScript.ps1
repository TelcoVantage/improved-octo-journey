<#
.SYNOPSIS
  Deploys the "Email Assistant" Genesys Cloud script and its search data action.

.DESCRIPTION
  1. Gets an OAuth token (client credentials).
  2. Finds the "Genesys Cloud Data Actions" integration.
  3. Creates the data action from genesys/data-actions/*.json (or reuses it if the name exists).
  4. Writes the data action id (and your region's app host) into the .script file.
  5. Uploads the .script through the same endpoint the Scripts UI uses (uploads/v2/scripter),
     waits for the import to finish, then publishes the script.

  Written for Windows PowerShell 5.1 running in Constrained Language Mode:
  no .NET static method calls, no ::new(), no [pscustomobject] casts, cmdlets only.

.EXAMPLE
  .\Deploy-EmailScript.ps1 -Region mypurecloud.ie -ClientId xxxx -ClientSecret yyyy

.NOTES
  OAuth client needs (at least): integrations:integration:view, integrations:action:add,
  integrations:action:view, scripter:script:add, scripter:script:view,
  scripter:publishedScript:add, scripter:publishedScript:view, analytics:conversationDetail:view.
  Script uploads require a user-level (not group-inherited) grant of those scripter permissions.
#>
param(
    [Parameter(Mandatory = $true)]  [string] $ClientId,
    [Parameter(Mandatory = $true)]  [string] $ClientSecret,
    [string] $Region          = "mypurecloud.com",
    [string] $ScriptFile      = (Join-Path (Split-Path -Parent $PSScriptRoot) "scripts\Email-Assistant.script"),
    [string] $DataActionFile  = (Join-Path (Split-Path -Parent $PSScriptRoot) "data-actions\Email-Assistant-Search-Inbound-Emails.json"),
    [string] $IntegrationName = "Genesys Cloud Data Actions",
    [string] $ScriptName      = "Email Assistant",
    [string] $DivisionId      = "",
    [string] $AppHost         = "",
    [switch] $SkipPublish
)

$ErrorActionPreference = "Stop"
$Placeholder     = "11111111-1111-1111-1111-111111111111"
$DefaultAppHost  = "apps.mypurecloud.com"
if ($AppHost -eq "") { $AppHost = "apps." + $Region }

# ---------------------------------------------------------------------------
# Helpers (Constrained Language Mode safe)
# ---------------------------------------------------------------------------
function ConvertTo-Base64Text {
    # Pure PowerShell Base64 for ASCII/Latin-1 text (used for the Basic auth header).
    param([string] $Text)
    $alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    $bytes = @()
    foreach ($ch in $Text.ToCharArray()) { $bytes += ([int][char]$ch -band 255) }
    $out = ""
    $i = 0
    while ($i -lt $bytes.Count) {
        $b0 = $bytes[$i]
        $b1 = 0; $b2 = 0
        $have = 1
        if (($i + 1) -lt $bytes.Count) { $b1 = $bytes[$i + 1]; $have = 2 }
        if (($i + 2) -lt $bytes.Count) { $b2 = $bytes[$i + 2]; $have = 3 }
        $n = ($b0 -shl 16) -bor ($b1 -shl 8) -bor $b2
        $out += $alphabet[($n -shr 18) -band 63]
        $out += $alphabet[($n -shr 12) -band 63]
        if ($have -ge 2) { $out += $alphabet[($n -shr 6) -band 63] } else { $out += "=" }
        if ($have -ge 3) { $out += $alphabet[$n -band 63] } else { $out += "=" }
        $i += 3
    }
    return $out
}

function Get-HttpStatus {
    param($ErrorRecord)
    $status = 0
    try { $status = [int]$ErrorRecord.Exception.Response.StatusCode } catch { $status = 0 }
    if ($status -eq 0) {
        $m = "" + $ErrorRecord.Exception.Message
        if ($m -like "*401*") { $status = 401 }
        elseif ($m -like "*403*") { $status = 403 }
        elseif ($m -like "*404*") { $status = 404 }
        elseif ($m -like "*400*") { $status = 400 }
    }
    return $status
}

function Invoke-GcApi {
    param(
        [string] $Method,
        [string] $Path,          # e.g. /api/v2/scripts
        $Body = $null,
        [string] $BaseUrl = ""
    )
    if ($BaseUrl -eq "") { $BaseUrl = $script:ApiBase }
    $uri = $BaseUrl + $Path
    $headers = @{ Authorization = "Bearer " + $script:Token }
    try {
        if ($null -ne $Body) {
            $json = $Body | ConvertTo-Json -Depth 30 -Compress
            return Invoke-RestMethod -Uri $uri -Method $Method -Headers $headers -ContentType "application/json" -Body $json
        }
        return Invoke-RestMethod -Uri $uri -Method $Method -Headers $headers
    }
    catch {
        $status = Get-HttpStatus $_
        $detail = ""
        try { $detail = "" + $_.ErrorDetails.Message } catch { $detail = "" }
        throw ("HTTP " + $status + " calling " + $Method + " " + $Path + ". " + $_.Exception.Message + " " + $detail)
    }
}

# ---------------------------------------------------------------------------
# 1. Token
# ---------------------------------------------------------------------------
$script:ApiBase = "https://api." + $Region
$LoginUrl       = "https://login." + $Region + "/oauth/token"
$AppsBase       = "https://" + $AppHost

Write-Host "[1/5] Requesting OAuth token from $LoginUrl ..."
$basic = ConvertTo-Base64Text ($ClientId + ":" + $ClientSecret)
try {
    $tokenResp = Invoke-RestMethod -Uri $LoginUrl -Method Post -Headers @{ Authorization = "Basic " + $basic } `
        -ContentType "application/x-www-form-urlencoded" -Body "grant_type=client_credentials"
}
catch {
    $status = Get-HttpStatus $_
    throw ("Token request failed (HTTP " + $status + "): " + $_.Exception.Message)
}
if (-not $tokenResp -or -not $tokenResp.access_token) { throw "Token response did not contain access_token. Check client id / secret / region." }
$script:Token = $tokenResp.access_token
Write-Host "      token OK"

# ---------------------------------------------------------------------------
# 2. Data Actions integration
# ---------------------------------------------------------------------------
Write-Host "[2/5] Looking for integration '$IntegrationName' ..."
$integration = $null
$page = 1
while ($null -eq $integration -and $page -le 10) {
    $resp = Invoke-GcApi -Method Get -Path ("/api/v2/integrations?pageSize=100&pageNumber=" + $page)
    if (-not $resp -or -not $resp.entities) { break }
    foreach ($e in $resp.entities) {
        if ($e.name -eq $IntegrationName -and $e.integrationType.id -eq "purecloud-data-actions") { $integration = $e; break }
    }
    if ($resp.entities.Count -lt 100) { break }
    $page++
}
if ($null -eq $integration) {
    throw ("Integration '" + $IntegrationName + "' (type purecloud-data-actions) not found. Create it under Admin > Integrations first, then re-run.")
}
$integrationId = $integration.id
Write-Host ("      integration id " + $integrationId)

# ---------------------------------------------------------------------------
# 3. Data action (create or reuse)
# ---------------------------------------------------------------------------
Write-Host "[3/5] Creating data action from $DataActionFile ..."
if (-not (Test-Path $DataActionFile)) { throw "Data action file not found: $DataActionFile" }
$actionDef = Get-Content -Path $DataActionFile -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $actionDef -or -not $actionDef.name) { throw "Data action file is not valid JSON or has no name." }

$existing = $null
$list = Invoke-GcApi -Method Get -Path ("/api/v2/integrations/actions?pageSize=100&integrationId=" + $integrationId)
if ($list -and $list.entities) {
    foreach ($a in $list.entities) { if ($a.name -eq $actionDef.name) { $existing = $a; break } }
}
if ($null -ne $existing) {
    $dataActionId = $existing.id
    Write-Host ("      reusing existing data action " + $dataActionId)
}
else {
    $createBody = @{
        name          = $actionDef.name
        category      = "Email Assistant"
        integrationId = $integrationId
        secure        = $false
        contract      = $actionDef.contract
        config        = $actionDef.config
    }
    $created = Invoke-GcApi -Method Post -Path "/api/v2/integrations/actions" -Body $createBody
    if (-not $created -or -not $created.id) { throw "Data action creation returned no id." }
    $dataActionId = $created.id
    Write-Host ("      created data action " + $dataActionId)
}

# ---------------------------------------------------------------------------
# 4. Patch and upload the script
# ---------------------------------------------------------------------------
Write-Host "[4/5] Uploading script $ScriptFile ..."
if (-not (Test-Path $ScriptFile)) { throw "Script file not found: $ScriptFile" }
$scriptText = Get-Content -Path $ScriptFile -Raw -Encoding UTF8
if ($scriptText.IndexOf($Placeholder) -lt 0) { Write-Warning "Placeholder data action id not found in script; it may already be patched." }
$scriptText = $scriptText.Replace($Placeholder, $dataActionId)
$scriptText = $scriptText.Replace('"value": "' + $DefaultAppHost + '"', '"value": "' + $AppHost + '"')

$boundary = "----GenesysScriptUpload" + (Get-Random -Minimum 100000 -Maximum 999999)
$crlf = "`r`n"
$body = ""
$body += "--" + $boundary + $crlf
$body += 'Content-Disposition: form-data; name="scriptName"' + $crlf + $crlf
$body += $ScriptName + $crlf
if ($DivisionId -ne "") {
    $body += "--" + $boundary + $crlf
    $body += 'Content-Disposition: form-data; name="divisionId"' + $crlf + $crlf
    $body += $DivisionId + $crlf
}
$body += "--" + $boundary + $crlf
$body += 'Content-Disposition: form-data; name="file"; filename="Email-Assistant.script"' + $crlf
$body += "Content-Type: application/json" + $crlf + $crlf
$body += $scriptText + $crlf
$body += "--" + $boundary + "--" + $crlf

$uploadUrl = $AppsBase + "/uploads/v2/scripter"
try {
    $upload = Invoke-RestMethod -Uri $uploadUrl -Method Post -Headers @{ Authorization = "Bearer " + $script:Token } `
        -ContentType ("multipart/form-data; boundary=" + $boundary) -Body $body
}
catch {
    $status = Get-HttpStatus $_
    throw ("Script upload failed (HTTP " + $status + ") at " + $uploadUrl + ": " + $_.Exception.Message + ". If this is a permissions error, the OAuth client (or your user, for a user token) needs user-level scripter permissions.")
}
$uploadId = ""
if ($upload.uploadId) { $uploadId = "" + $upload.uploadId }
elseif ($upload.id) { $uploadId = "" + $upload.id }
if ($uploadId -eq "") { throw ("Upload response did not contain an upload id: " + ($upload | ConvertTo-Json -Compress -Depth 5)) }
Write-Host ("      upload id " + $uploadId + " - waiting for import ...")

$scriptId = ""
$attempt = 0
while ($attempt -lt 30) {
    Start-Sleep -Seconds 2
    $attempt++
    $st = Invoke-GcApi -Method Get -Path ("/api/v2/scripts/uploads/" + $uploadId + "/status")
    if ($st.succeeded -eq $true) {
        if ($st.scriptId) { $scriptId = "" + $st.scriptId }
        break
    }
    if ($st.succeeded -eq $false -and $st.message) { throw ("Script import failed: " + $st.message) }
}
if ($attempt -ge 30 -and $scriptId -eq "") { Write-Warning "Import status did not report success within 60 s; checking the script list anyway." }

if ($scriptId -eq "") {
    $found = Invoke-GcApi -Method Get -Path ("/api/v2/scripts?pageSize=50&sortBy=modifiedDate&sortOrder=descending&name=" + $ScriptName.Replace(" ", "%20"))
    if ($found -and $found.entities) {
        foreach ($s in $found.entities) { if ($s.name -eq $ScriptName) { $scriptId = "" + $s.id; break } }
    }
}
if ($scriptId -eq "") { throw "Imported script could not be located by name '$ScriptName'. Open Admin > Scripts to check." }
Write-Host ("      script id " + $scriptId)

# ---------------------------------------------------------------------------
# 5. Publish
# ---------------------------------------------------------------------------
if ($SkipPublish) {
    Write-Host "[5/5] Publish skipped (-SkipPublish)."
}
else {
    Write-Host "[5/5] Publishing script ..."
    try {
        $scriptInfo = Invoke-GcApi -Method Get -Path ("/api/v2/scripts/" + $scriptId)
        $pub = @{ scriptId = $scriptId }
        if ($scriptInfo.versionId) { $pub["versionId"] = "" + $scriptInfo.versionId }
        $published = Invoke-GcApi -Method Post -Path "/api/v2/scripts/published" -Body $pub
        Write-Host ("      published (published id " + $published.id + ")")
    }
    catch {
        Write-Warning ("Publish via API failed: " + $_.Exception.Message + " - open the script in Admin > Scripts and click Publish.")
    }
}

Write-Host ""
Write-Host "Done."
Write-Host ("  Data action : " + $dataActionId + "  (" + $actionDef.name + ")")
Write-Host ("  Script      : " + $scriptId + "  (" + $ScriptName + ")")
Write-Host ("  Open editor : " + $AppsBase + "/scripter/#/scripts/" + $scriptId)
Write-Host "  Next: open the script, click Preview, run 'All emails from this sender', then assign the script to your email queue/flow."

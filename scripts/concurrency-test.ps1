<#
Concurrency demonstration for the reservation endpoint.

Fires two POST requests to reserve the same seat at the same time.
Expected result: exactly one 201 Created, exactly one 409 Conflict.

Usage:
    .\scripts\concurrency-test.ps1 -EventId 1 -SeatId <SEAT_ID>
#>
param(
    [Parameter(Mandatory = $true)][int]$EventId,
    [Parameter(Mandatory = $true)][int]$SeatId,
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$url = "$BaseUrl/events/$EventId/seats/$SeatId/reserve"

Write-Host "Firing two concurrent POST requests to:"
Write-Host "  $url"
Write-Host ""

$scriptBlock = {
    param($url)
    try {
        $response = Invoke-WebRequest -Uri $url -Method Post -UseBasicParsing
        [pscustomobject]@{
            Status  = [int]$response.StatusCode
            Body    = $response.Content
            Success = $true
        }
    } catch {
        [pscustomobject]@{
            Status  = [int]$_.Exception.Response.StatusCode.value__
            Body    = $_.ErrorDetails.Message
            Success = $false
        }
    }
}

# Start both jobs, then wait for both to finish.
$job1 = Start-Job -ScriptBlock $scriptBlock -ArgumentList $url
$job2 = Start-Job -ScriptBlock $scriptBlock -ArgumentList $url

$result1 = Receive-Job -Job $job1 -Wait
$result2 = Receive-Job -Job $job2 -Wait

Remove-Job -Job $job1, $job2

# --- Fix: flatten each result into a single object, then collect statuses. ---
# Receive-Job can return a single-element array; unwrap it so .Status reads cleanly.
$r1 = @($result1)[0]
$r2 = @($result2)[0]

Write-Host "Request A:"
Write-Host "  Status: $($r1.Status)"
Write-Host "  Body:   $($r1.Body)"
Write-Host ""
Write-Host "Request B:"
Write-Host "  Status: $($r2.Status)"
Write-Host "  Body:   $($r2.Body)"
Write-Host ""

$statuses = @($r1.Status, $r2.Status)
$successCount  = @($statuses | Where-Object { $_ -eq 201 }).Count
$conflictCount = @($statuses | Where-Object { $_ -eq 409 }).Count

Write-Host "===== Result ====="
Write-Host "201 Created:     $successCount"
Write-Host "409 Conflict:    $conflictCount"
Write-Host ""

if ($successCount -eq 1 -and $conflictCount -eq 1) {
    Write-Host "PASS: exactly one reservation succeeded and exactly one failed."
    exit 0
} else {
    Write-Host "FAIL: expected 1 success and 1 conflict."
    exit 1
}
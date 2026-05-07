#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Helper script to query records via API Gateway.

.DESCRIPTION
    This script simplifies querying the external data API by:
    - Automatically constructing the API URL
    - Formatting the request correctly
    - Displaying the response in a readable format

.PARAMETER Stage
    The deployment stage (e.g., dev, staging, prod)

.PARAMETER PartitionKey
    The partition key value to query (e.g., "CC12345", "1234567890")

.PARAMETER SortKey
    The sort key value to query (e.g., "fedecafetero", "personas-2024")

.PARAMETER ApiUrl
    Override the default API URL (optional)

.EXAMPLE
    .\query.ps1 -Stage dev -PartitionKey "CC12345" -SortKey "fedecafetero"

.EXAMPLE
    .\query.ps1 -Stage dev -PartitionKey "1234567890" -SortKey "personas-2024"

.EXAMPLE
    .\query.ps1 -Stage dev -PartitionKey "doc-123" -SortKey "test" -ApiUrl "https://custom-api.execute-api.us-east-1.amazonaws.com/dev/"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$Stage,

    [Parameter(Mandatory=$true)]
    [string]$PartitionKey,

    [Parameter(Mandatory=$true)]
    [string]$SortKey,

    [Parameter(Mandatory=$false)]
    [string]$ApiUrl = ""
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Color output functions
function Write-Success {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Cyan
}

function Write-Warning {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Red
}

# Default API URL (from CDK output)
if (-not $ApiUrl) {
    $ApiUrl = "https://gvhyyvhmhj.execute-api.us-east-1.amazonaws.com/$Stage/"
}

# Ensure trailing slash
if (-not $ApiUrl.EndsWith("/")) {
    $ApiUrl += "/"
}

# URL encode the keys
$EncodedPartitionKey = [System.Web.HttpUtility]::UrlEncode($PartitionKey)
$EncodedSortKey = [System.Web.HttpUtility]::UrlEncode($SortKey)

# Build full URL
$FullUrl = "${ApiUrl}external/$EncodedPartitionKey/$EncodedSortKey"

Write-Info "======================================"
Write-Info "Querying External Data API"
Write-Info "======================================"
Write-Host "API URL:       $ApiUrl"
Write-Host "Partition Key: $PartitionKey"
Write-Host "Sort Key:      $SortKey"
Write-Info "======================================"
Write-Host ""

# Make API request
try {
    Write-Info "Sending GET request..."

    $response = Invoke-RestMethod -Uri $FullUrl -Method Get -ErrorAction Stop

    Write-Success "`n✅ Record found!"
    Write-Info "`nResponse:"
    Write-Info "======================================"

    # Pretty print JSON
    $response | ConvertTo-Json -Depth 10

    Write-Info "======================================"

    # Show record details if available
    if ($response.data) {
        Write-Host ""
        Write-Success "Record Details:"
        Write-Host "  Partition Key: $($response.data.partitionKey)"
        Write-Host "  Sort Key:      $($response.data.sortKey)"
        Write-Host "  Created At:    $($response.data.createdAt)"
        Write-Host "  Source File:   $($response.data.sourceFile)"
        Write-Host "  Row Index:     $($response.data.rowIndex)"
        Write-Host "  Status:        $($response.data.status)"
    }

} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__

    if ($statusCode -eq 404) {
        Write-Warning "`n⚠️  Record not found"
        Write-Host ""
        Write-Host "Partition Key: $PartitionKey"
        Write-Host "Sort Key:      $SortKey"
        Write-Host ""
        Write-Info "Possible reasons:"
        Write-Host "  • Record does not exist in DynamoDB"
        Write-Host "  • Partition key or sort key value is incorrect"
        Write-Host "  • File ingestion has not completed yet"
        Write-Host ""
        Write-Info "Check DynamoDB directly:"
        Write-Host "  aws dynamodb get-item --table-name $Stage-ExternalData --key '{\"partitionKey\":{\"S\":\"$PartitionKey\"},\"sortKey\":{\"S\":\"$SortKey\"}}'"

    } elseif ($statusCode -eq 403) {
        Write-Error "`n❌ Access Denied (403 Forbidden)"
        Write-Host ""
        Write-Info "Possible reasons:"
        Write-Host "  • API Gateway authorization issue"
        Write-Host "  • CORS configuration problem"
        Write-Host "  • Resource policy restriction"

    } elseif ($statusCode -eq 500) {
        Write-Error "`n❌ Internal Server Error (500)"
        Write-Host ""
        Write-Info "Check Lambda logs:"
        Write-Host "  aws logs tail /aws/lambda/processapp-consumer-$Stage --follow"

    } else {
        Write-Error "`n❌ Error querying API:"
        Write-Error "Status Code: $statusCode"
        Write-Error $_.Exception.Message
    }

    exit 1
}

Write-Host ""

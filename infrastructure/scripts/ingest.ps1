#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Helper script to invoke the Ingester Lambda function for CSV/TXT file ingestion.

.DESCRIPTION
    This script simplifies invoking the ingester Lambda by:
    - Automatically capitalizing the stage name for the table (dev → dev-ExternalData)
    - Formatting the payload correctly
    - Using your default AWS credentials (from AWS_PROFILE or default profile)
    - Showing CloudWatch logs command for monitoring

.PARAMETER Stage
    The deployment stage (e.g., dev, staging, prod)

.PARAMETER File
    The CSV/TXT file name in S3 (e.g., fedecafetero.csv)

.PARAMETER PartitionKey
    The column name in the CSV to use as the partition key (e.g., "doc", "documento")

.PARAMETER SortKey
    The fixed value for the sort key or column name (e.g., "fedecafetero")
    Optional - if omitted, row index will be used

.PARAMETER Profile
    AWS profile to use (optional - defaults to AWS_PROFILE or default profile)

.EXAMPLE
    .\ingest.ps1 -Stage dev -File fedecafetero.csv -PartitionKey "doc" -SortKey "fedecafetero"

.EXAMPLE
    .\ingest.ps1 -Stage dev -File data.csv -PartitionKey "documento" -Profile ans-super

.EXAMPLE
    .\ingest.ps1 -Stage dev -File myfile.csv -PartitionKey "id" -SortKey "dataset-2024"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$Stage,

    [Parameter(Mandatory=$true)]
    [string]$File,

    [Parameter(Mandatory=$true)]
    [string]$PartitionKey,

    [Parameter(Mandatory=$false)]
    [string]$SortKey = "",

    [Parameter(Mandatory=$false)]
    [string]$Profile = ""
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

# Capitalize first letter of stage for table name (dev → dev-ExternalData)
$TableName = $Stage.Substring(0,1).ToUpper() + $Stage.Substring(1) + "-ExternalData"
$FunctionName = "processapp-ingester-$Stage"

# Build config object
$config = @{
    table = $TableName
    partitionKey = $PartitionKey
    file = $File
    ignore = $false
}

# Add sortKey if provided
if ($SortKey) {
    $config.sortKey = $SortKey
}

# Build payload
$payload = @{
    config = @($config)
} | ConvertTo-Json -Compress -Depth 10

Write-Info "======================================"
Write-Info "Invoking Ingester Lambda"
Write-Info "======================================"
Write-Host "Function:      $FunctionName"
Write-Host "File:          $File"
Write-Host "Table:         $TableName"
Write-Host "Partition Key: $PartitionKey"
if ($SortKey) {
    Write-Host "Sort Key:      $SortKey"
} else {
    Write-Host "Sort Key:      (row index)"
}
Write-Info "======================================"

# Build AWS CLI command
$awsCommand = @(
    "lambda", "invoke"
    "--function-name", $FunctionName
    "--payload", $payload
    "--cli-binary-format", "raw-in-base64-out"
    "response.json"
)

# Add profile if specified
if ($Profile) {
    $awsCommand += "--profile"
    $awsCommand += $Profile
    Write-Host "Profile:       $Profile"
}

Write-Info "======================================"
Write-Info ""

# Invoke Lambda
try {
    Write-Info "Invoking Lambda function..."
    & aws @awsCommand

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Lambda invocation failed with exit code $LASTEXITCODE"
        exit 1
    }

    Write-Success "`n✅ Lambda invoked successfully!"

    # Read response
    if (Test-Path "response.json") {
        Write-Info "`nResponse:"
        Write-Info "======================================"

        $response = Get-Content "response.json" -Raw | ConvertFrom-Json

        # Check for Lambda errors
        if ($response.StatusCode -ne 200) {
            Write-Error "Lambda returned status code: $($response.StatusCode)"
            Write-Host ($response | ConvertTo-Json -Depth 10)
            exit 1
        }

        # Parse body
        $body = $response.body | ConvertFrom-Json

        if ($body.results) {
            foreach ($result in $body.results) {
                Write-Host ""
                Write-Success "File: $($result.file)"
                Write-Success "  ✓ Success: $($result.success_count) records"

                if ($result.error_count -gt 0) {
                    Write-Warning "  ⚠ Errors: $($result.error_count) records"
                    Write-Warning "    Check S3 for $($result.file).failed.txt"
                }

                Write-Host "  Status: $($result.status)"
            }
        } else {
            Write-Host ($response | ConvertTo-Json -Depth 10)
        }

        Write-Info "`n======================================"
        Write-Info "Next Steps:"
        Write-Info "======================================"
        Write-Host "1. Check S3 for processed files:"
        Write-Host "   aws s3 ls s3://dev-answering-procesapp-info/$File"
        Write-Host ""
        Write-Host "2. View CloudWatch logs:"
        Write-Host "   aws logs tail /aws/lambda/$FunctionName --follow"
        Write-Host ""
        Write-Host "3. Query a record via API:"
        Write-Host "   .\query.ps1 -Stage $Stage -PartitionKey YOUR_KEY -SortKey YOUR_SORT"
        Write-Info "======================================"

    } else {
        Write-Warning "Response file not found: response.json"
    }

} catch {
    Write-Error "`n❌ Error invoking Lambda:"
    Write-Error $_.Exception.Message
    exit 1
}

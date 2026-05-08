# External Ingester-Consumer Lambda Infrastructure

AWS CDK infrastructure for streaming CSV/TXT file ingestion from S3 to DynamoDB with REST API access.

## Architecture

- **Ingester Lambda**: Streams large CSV/TXT files from S3, processes line-by-line, batch writes to DynamoDB
- **Consumer Lambda**: Query DynamoDB records via REST API
- **DynamoDB**: Pay-per-request table with composite key (partitionKey, sortKey)
- **API Gateway**: REST API for querying records
- **KMS**: Encryption for DynamoDB and S3

## Key Features

- **Streaming Processing**: Handles multi-GB files with constant ~50MB memory usage
- **Native Python**: No external dependencies (boto3, io, csv stdlib only)
- **Error Handling**: Creates .failed.txt CSV files with error_reason column
- **Audit Trail**: Renames processed files with .ingested suffix
- **Scalable**: DynamoDB pay-per-request, Lambda auto-scaling
- **Cross-Platform**: Full support for Linux, macOS, and Windows with native scripts

## System Requirements

### Required Software

| Software | Version | Purpose | Download Link |
|----------|---------|---------|---------------|
| **Node.js** | 18+ | CDK infrastructure deployment | https://nodejs.org/en/download/ |
| **npm** | 9+ | Package management (included with Node.js) | - |
| **AWS CLI** | v2 | AWS resource management | https://aws.amazon.com/cli/ |
| **Git** | 2.0+ | Version control | https://git-scm.com/downloads |
| **AWS CDK** | 2.118+ | Infrastructure as Code | `npm install -g aws-cdk` |

### Optional Tools

| Software | Purpose | Download Link |
|----------|---------|---------------|
| **Python** | 3.8+ | Local Lambda testing | https://www.python.org/downloads/ |
| **jq** | JSON parsing in CLI | https://jqlang.github.io/jq/download/ |
| **PowerShell** | Windows script execution | Pre-installed on Windows 10+ |

### AWS Account Prerequisites

- AWS Account ID: `708819485463`
- AWS profile configured with credentials
- IAM user with appropriate permissions (for authorized users)
- Existing S3 bucket: `dev-answering-procesapp-info`

### Verify Installation

Run these commands to verify your setup:

```bash
# Check Node.js version
node --version  # Should be v18.0.0 or higher

# Check npm version
npm --version   # Should be 9.0.0 or higher

# Check AWS CLI version
aws --version   # Should be aws-cli/2.x.x

# Check CDK version
cdk --version   # Should be 2.118.0 or higher

# Check AWS credentials
aws sts get-caller-identity  # Should show your AWS account info
```

### Platform-Specific Setup

#### Linux/macOS

```bash
# Install Node.js via package manager
# macOS (using Homebrew)
brew install node

# Ubuntu/Debian
sudo apt update && sudo apt install nodejs npm

# Install AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Install CDK
npm install -g aws-cdk

# Install jq (optional)
brew install jq  # macOS
sudo apt install jq  # Ubuntu/Debian
```

#### Windows

```powershell
# Install via Chocolatey (recommended)
choco install nodejs -y
choco install awscli -y
choco install git -y

# Or download installers manually:
# Node.js: https://nodejs.org/en/download/
# AWS CLI: https://awscli.amazonaws.com/AWSCLIV2.msi
# Git: https://git-scm.com/download/win

# Install CDK
npm install -g aws-cdk

# Verify PowerShell version (should be 5.1+)
$PSVersionTable.PSVersion
```

### AWS Profile Configuration

```bash
# Configure AWS profile (all platforms)
aws configure --profile ans-super
# AWS Access Key ID: [Enter your access key]
# AWS Secret Access Key: [Enter your secret key]
# Default region name: us-east-1
# Default output format: json

# Verify profile works
aws sts get-caller-identity --profile ans-super

# Set default profile (optional)
export AWS_PROFILE=ans-super  # Linux/macOS
$env:AWS_PROFILE="ans-super"  # Windows PowerShell
```

## Installation

```bash
cd infrastructure
npm install
npm run build
```

## Deployment

### First-time Setup

```bash
# Bootstrap CDK (only needed once per account/region)
cdk bootstrap aws://708819485463/us-east-1 --profile ans-super
```

### Deploy All Stacks

```bash
# Deploy all stacks (recommended)
npm run deploy

# Or deploy individually
cdk deploy dev-PrereqsStack --profile ans-super
cdk deploy dev-IngesterStack --profile ans-super
cdk deploy dev-ConsumerStack --profile ans-super
```

### Stack Outputs

After deployment, note these outputs:
- **ApiUrl**: API Gateway endpoint URL
- **IngesterFunctionName**: processapp-ingester-dev
- **TableName**: dev-ExternalData

## Authorized Users

The following IAM users have permissions to invoke the ingester Lambda:
- **qohat.prettel**
- **david.jimenez**
- **soportejoven@answering.com.co**

These users can run the ingestion process without needing admin access.

## Usage

> **Platform Note**: This documentation provides commands for both **Linux/macOS** (Bash) and **Windows** (PowerShell). 
> - Linux/macOS users: Use `.sh` scripts with `./scripts/script.sh` syntax
> - Windows users: Use `.ps1` scripts with `.\scripts\script.ps1` syntax
> 
> All AWS CLI commands work identically on both platforms.

### 1. Upload CSV to S3

**All Platforms:**
```bash
# With your AWS profile
aws s3 cp your-file.csv s3://dev-answering-procesapp-info/ --profile YOUR_PROFILE

# Or with default profile
aws s3 cp your-file.csv s3://dev-answering-procesapp-info/
```

**Windows PowerShell Alternative:**
```powershell
# Upload with PowerShell
aws s3 cp your-file.csv s3://dev-answering-procesapp-info/

# Or specify profile
aws s3 cp your-file.csv s3://dev-answering-procesapp-info/ --profile YOUR_PROFILE
```

### 2. Ingest File

#### Option A: Using Helper Script (Recommended)

**Linux/macOS:**
```bash
# Format: ./scripts/ingest.sh <stage> <file> <partitionKey> [sortKey]
./scripts/ingest.sh dev fedecafetero.csv "doc" "fedecafetero"
```

**Windows (PowerShell):**
```powershell
# Format: .\scripts\ingest.ps1 -Stage <stage> -File <file> -PartitionKey <key> -SortKey <value>
.\scripts\ingest.ps1 -Stage dev -File fedecafetero.csv -PartitionKey "doc" -SortKey "fedecafetero"
```

The script automatically:
- Uses your default AWS credentials
- Capitalizes the stage name for the table (dev → Dev-ExternalData)
- Formats the payload correctly
- Shows CloudWatch logs command

#### Option B: Direct AWS CLI Invocation

```bash
aws lambda invoke \
  --function-name processapp-ingester-dev \
  --payload '{"config": [{"table": "Dev-ExternalData", "partitionKey": "doc", "sortKey": "fedecafetero", "file": "fedecafetero.csv", "ignore": false}]}' \
  --cli-binary-format raw-in-base64-out \
  response.json

# View response
cat response.json | jq .
```

### Understanding partitionKey and sortKey

**Important Notes:**
- `partitionKey` refers to the **column name** in the CSV/TXT (e.g., "doc", "documento", "col0")
- The **value** in that column becomes the partition key in DynamoDB
- `sortKey` can be:
  - A **column name** (will use the value from that column)
  - A **fixed value** (same for all records)
  - Omitted (will use row index)

### File Format Support

The ingester **automatically detects** file formats and delimiters. No extra configuration needed!

| Format | Extension | Delimiter | Headers | Auto-Detection |
|--------|-----------|-----------|---------|----------------|
| **CSV (Comma)** | `.csv` | Comma (`,`) | Required | ✅ Automatic |
| **CSV (Semicolon)** | `.csv` | Semicolon (`;`) | Required | ✅ Automatic |
| **TSV** | `.txt` | Tab (`\t`) | Required | ✅ Automatic |
| **Pipe-delimited** | `.txt` | Pipe (`\|`) | Required | ✅ Automatic |

**Auto-detected delimiters:**
- `,` - Comma (standard CSV)
- `;` - Semicolon (European Excel exports)
- `\t` - Tab (TSV files)
- `|` - Pipe (database exports)

**How it works:**
1. Lambda reads the first line of the file
2. Counts occurrences of each delimiter
3. Uses the delimiter with the highest count
4. Automatically parses the file with detected settings

**Important:** All files must have a header row with column names. The `partitionKey` parameter must match one of these column names.

#### Example 1: CSV File (Comma-separated)

CSV file `fedecafetero.csv`:
```csv
doc,name,value
12345,John Doe,100
67890,Jane Smith,200
```

**Linux/macOS:**
```bash
./scripts/ingest.sh dev fedecafetero.csv "doc" "fedecafetero"
```

**Windows:**
```powershell
.\scripts\ingest.ps1 -Stage dev -File fedecafetero.csv -PartitionKey "doc" -SortKey "fedecafetero"
```

Result in DynamoDB:
- Record 1: `partitionKey="12345"`, `sortKey="fedecafetero"`, `data_doc="12345"`, `data_name="John Doe"`, `data_value="100"`
- Record 2: `partitionKey="67890"`, `sortKey="fedecafetero"`, `data_doc="67890"`, `data_name="Jane Smith"`, `data_value="200"`

#### Example 1b: CSV File (Semicolon-separated)

CSV file `data-semicolon.csv`:
```csv
doc;name;value
12345;John Doe;100
67890;Jane Smith;200
```

**Linux/macOS:**
```bash
./scripts/ingest.sh dev data-semicolon.csv "doc" "semicolon-data"
```

**Windows:**
```powershell
.\scripts\ingest.ps1 -Stage dev -File data-semicolon.csv -PartitionKey "doc" -SortKey "semicolon-data"
```

**Note**: The delimiter is automatically detected! No need to specify it.

#### Example 2: Multiple files, same partition column

**Linux/macOS:**
```bash
# File 1: fedecafetero.csv
./scripts/ingest.sh dev fedecafetero.csv "doc" "fedecafetero"

# File 2: fedeaarroz.csv (same partition key column)
./scripts/ingest.sh dev fedeaarroz.csv "doc" "fedeaarroz"
```

**Windows:**
```powershell
# File 1: fedecafetero.csv
.\scripts\ingest.ps1 -Stage dev -File fedecafetero.csv -PartitionKey "doc" -SortKey "fedecafetero"

# File 2: fedeaarroz.csv (same partition key column)
.\scripts\ingest.ps1 -Stage dev -File fedeaarroz.csv -PartitionKey "doc" -SortKey "fedeaarroz"
```

Now you can query by partition key and different sort keys:
```bash
curl https://API_URL/external/12345/fedecafetero
curl https://API_URL/external/12345/fedeaarroz
```

#### Example 3: TXT File (Tab-separated)

TXT file `data.txt`:
```
doc	name	city	value
12345	John Doe	Bogota	100
67890	Jane Smith	Medellin	200
```

**Linux/macOS:**
```bash
./scripts/ingest.sh dev data.txt "doc" "tab-data"
```

**Windows:**
```powershell
.\scripts\ingest.ps1 -Stage dev -File data.txt -PartitionKey "doc" -SortKey "tab-data"
```

**Note**: Tab delimiter is automatically detected!

#### Example 4: TXT File (Pipe-separated)

TXT file `data.txt`:
```
doc|name|city|value
12345|John Doe|Bogota|100
67890|Jane Smith|Medellin|200
```

**Linux/macOS:**
```bash
./scripts/ingest.sh dev data.txt "doc" "pipe-data"
```

**Windows:**
```powershell
.\scripts\ingest.ps1 -Stage dev -File data.txt -PartitionKey "doc" -SortKey "pipe-data"
```

**Note**: Pipe delimiter is automatically detected!

#### Example 5: Using row index as sortKey

**Linux/macOS:**
```bash
# Omit sortKey parameter to use row numbers
./scripts/ingest.sh dev data.csv "documento"
```

**Windows:**
```powershell
# Omit -SortKey parameter to use row numbers
.\scripts\ingest.ps1 -Stage dev -File data.csv -PartitionKey "documento"
```

Result:
- Record 1: `partitionKey="value_from_documento_column"`, `sortKey="1"`
- Record 2: `partitionKey="value_from_documento_column"`, `sortKey="2"`

### 3. Query via API

**Linux/macOS:**
```bash
# Using helper script
./scripts/query.sh dev "12345" "fedecafetero"

# Or directly with curl
curl -X GET "https://API_ID.execute-api.us-east-1.amazonaws.com/dev/external/12345/fedecafetero"
```

**Windows:**
```powershell
# Using helper script
.\scripts\query.ps1 -Stage dev -PartitionKey "12345" -SortKey "fedecafetero"

# Or directly with Invoke-RestMethod
Invoke-RestMethod -Uri "https://API_ID.execute-api.us-east-1.amazonaws.com/dev/external/12345/fedecafetero" -Method Get

# Or with curl (if installed)
curl.exe -X GET "https://API_ID.execute-api.us-east-1.amazonaws.com/dev/external/12345/fedecafetero"
```

### 4. Monitor Processing

#### Check Lambda Response

After invoking, check `response.json`:
```bash
cat response.json | jq .
```

Successful response:
```json
{
  "statusCode": 200,
  "body": "{\"message\":\"Ingestion completed\",\"results\":[{\"file\":\"fedecafetero.csv\",\"success_count\":150,\"error_count\":0,\"status\":\"completed\"}]}"
}
```

#### Check CloudWatch Logs

```bash
# Ingester logs (real-time)
aws logs tail /aws/lambda/processapp-ingester-dev --follow

# Ingester logs (last 10 minutes)
aws logs tail /aws/lambda/processapp-ingester-dev --since 10m

# Consumer logs
aws logs tail /aws/lambda/processapp-consumer-dev --follow
```

#### Check S3 for Processed Files

```bash
# List files in S3
aws s3 ls s3://dev-answering-procesapp-info/

# Should see:
# fedecafetero.csv.ingested (original file renamed)
# fedecafetero.csv.failed.txt (only if errors occurred)
```

## Configuration

Edit `config/environments.ts` to customize:
- Lambda memory and timeout
- DynamoDB settings
- Batch size and retry logic
- Cost allocation tags

## Error Handling

### Failed Records

If ingestion errors occur, a `.failed.txt` file is created in S3:

```csv
doc,name,value,error_reason
,John Doe,100,Missing or empty partition key: doc
12345,Invalid,xyz,Processing error: Invalid value
```

### Processed Files

Successfully processed files are renamed with `.ingested` suffix:
- `fedecafetero.csv` → `fedecafetero.csv.ingested`

This prevents duplicate processing.

## Complete Example Workflows

### Example 1: Basic Ingestion and Query

```bash
# 1. Create a test CSV file
cat > sample-data.csv << EOF
doc,name,email,phone
CC12345,Juan Perez,juan@example.com,3001234567
CC67890,Maria Lopez,maria@example.com,3009876543
CC11111,Carlos Ruiz,carlos@example.com,3005555555
EOF

# 2. Upload to S3
aws s3 cp sample-data.csv s3://dev-answering-procesapp-info/

# 3. Ingest the file
cd infrastructure
./scripts/ingest.sh dev sample-data.csv "doc" "personas-2024"

# 4. Wait for processing (check response.json)
cat response.json | jq .

# 5. Query a record
./scripts/query.sh dev "CC12345" "personas-2024"

# Expected response:
# {
#   "data": {
#     "partitionKey": "CC12345",
#     "sortKey": "personas-2024",
#     "createdAt": "2024-12-31T12:00:00.000Z",
#     "sourceFile": "sample-data.csv",
#     "rowIndex": 1,
#     "status": "active",
#     "data_doc": "CC12345",
#     "data_name": "Juan Perez",
#     "data_email": "juan@example.com",
#     "data_phone": "3001234567"
#   },
#   "status": "success"
# }
```

### Example 2: Multiple Files from Different Sources

```bash
# Fedecafetero data
cat > fedecafetero.csv << EOF
cedula,nombre,ciudad,estado
1234567890,Pedro Garcia,Bogota,Activo
9876543210,Ana Martinez,Medellin,Activo
EOF

aws s3 cp fedecafetero.csv s3://dev-answering-procesapp-info/
./scripts/ingest.sh dev fedecafetero.csv "cedula" "fedecafetero"

# Fedeaarroz data (same partition key column, different sortKey)
cat > fedeaarroz.csv << EOF
cedula,nombre,ciudad,producto
1234567890,Pedro Garcia,Cali,Arroz Premium
5555555555,Luis Gomez,Barranquilla,Arroz Integral
EOF

aws s3 cp fedeaarroz.csv s3://dev-answering-procesapp-info/
./scripts/ingest.sh dev fedeaarroz.csv "cedula" "fedeaarroz"

# Now you can query the same person from different sources
./scripts/query.sh dev "1234567890" "fedecafetero"
./scripts/query.sh dev "1234567890" "fedeaarroz"
```

### Example 3: Error Handling

```bash
# Create a CSV with intentional errors (missing partition key)
cat > bad-data.csv << EOF
doc,name,value
,Missing Doc,100
CC22222,Valid Record,200
,Another Missing,300
EOF

aws s3 cp bad-data.csv s3://dev-answering-procesapp-info/
./scripts/ingest.sh dev bad-data.csv "doc" "test-errors"

# Check the response - should show errors
cat response.json | jq .
# Output: {"success_count": 1, "error_count": 2, ...}

# Check the failed records file
aws s3 cp s3://dev-answering-procesapp-info/bad-data.csv.failed.txt - | cat
# Output:
# doc,name,value,error_reason
# ,Missing Doc,100,Missing or empty partition key: doc
# ,Another Missing,300,Missing or empty partition key: doc

# The valid record was still inserted
./scripts/query.sh dev "CC22222" "test-errors"
```

## Testing

### Quick Test (Small File)

```bash
# Generate 100 records
python -c "
import csv
with open('test.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['doc', 'name', 'value'])
    for i in range(100):
        writer.writerow([f'doc-{i}', f'Name {i}', i * 10])
"

aws s3 cp test.csv s3://dev-answering-procesapp-info/
./scripts/ingest.sh dev test.csv "doc" "test-run"
./scripts/query.sh dev "doc-0" "test-run"
```

### Large File Test (1GB+)

```bash
python -c "
import csv
with open('large-test.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['doc', 'name', 'value', 'description'])
    for i in range(5_000_000):  # 5M rows ~1GB
        writer.writerow([f'doc-{i}', f'Name {i}', i * 100, f'Test record {i}'])
"

aws s3 cp large-test.csv s3://dev-answering-procesapp-info/ --profile ans-super
./scripts/ingest.sh dev large-test.csv "doc" "stress-test"
```

Expected: ~15 minutes processing time, constant ~50-100MB memory usage.

## Monitoring

### CloudWatch Metrics

- **Ingester**: Duration, Memory, Errors, Throttles
- **Consumer**: Duration, Invocations, Errors
- **DynamoDB**: ConsumedReadCapacity, ConsumedWriteCapacity
- **API Gateway**: Count, Latency, 4XXError, 5XXError

### X-Ray Tracing

Both Lambda functions have X-Ray tracing enabled for distributed tracing.

## Cost Estimation

**Dev environment (100 ingestions/day, 1K API calls/day):**
- DynamoDB: ~$2/month
- Lambda: ~$1-2/month
- API Gateway: ~$0.50/month
- S3: ~$1/month
- **Total: ~$5-10/month**

## Cleanup

```bash
# Destroy all stacks
npm run destroy

# Or individually
cdk destroy dev-ConsumerStack --profile ans-super
cdk destroy dev-IngesterStack --profile ans-super
cdk destroy dev-PrereqsStack --profile ans-super
```

**Note**: DynamoDB table and KMS key are retained in production (set in config).

## Troubleshooting

### Issue: "AccessDenied" when invoking Lambda

**Symptom:**
```bash
An error occurred (AccessDeniedException) when calling the Invoke operation: 
User: arn:aws:iam::708819485463:user/username is not authorized to perform: lambda:InvokeFunction
```

**Solution:**
Your IAM user must be one of the authorized users:
- qohat.prettel
- david.jimenez
- soportejoven@answering.com.co

Contact the admin if you need access.

### Issue: Lambda timeout on large files

**Symptom:** Lambda times out after 15 minutes

**Solution:**
- Current limit: 900 seconds (15 minutes)
- Files over 5GB may need to be split
- For very large files, increase timeout in `config/environments.ts` and redeploy

### Issue: "Column not found" error

**Symptom:**
```json
{
  "statusCode": 500,
  "body": "{\"error\":\"Partition key column 'doc' not found in CSV. Available columns: ['documento', 'name', 'value']\"}"
}
```

**Solution:**
Check your CSV headers match the `partitionKey` parameter:
```bash
# If your CSV has "documento" not "doc"
./scripts/ingest.sh dev file.csv "documento" "sortkey"
```

### Issue: DynamoDB throttling

**Current Status:** PAY_PER_REQUEST mode = no throttling

If you see throttling errors:
- Check AWS Service Health Dashboard
- Review DynamoDB CloudWatch metrics
- Consider increasing Lambda retry configuration

### Issue: CSV parsing errors

**Common causes:**
1. **No header row**: CSV must have a header row with column names
2. **Wrong encoding**: File must be UTF-8 encoded
3. **Malformed CSV**: Extra commas, unescaped quotes

**Example fix:**
```bash
# Check file encoding
file -I yourfile.csv

# Convert to UTF-8 if needed
iconv -f ISO-8859-1 -t UTF-8 yourfile.csv > yourfile-utf8.csv
```

### Issue: API Gateway 403/404 errors

**403 Forbidden:**
- Check CORS configuration (currently enabled for all origins)
- Verify API Gateway deployment

**404 Not Found:**
- Verify record exists: `aws dynamodb get-item --table-name Dev-ExternalData --key '{"partitionKey":{"S":"YOUR_KEY"},"sortKey":{"S":"YOUR_SORT"}}'`
- Check partitionKey and sortKey values match exactly

### Issue: File not renamed to .ingested

**Symptom:** Original file still exists, no .ingested file

**Possible causes:**
1. Lambda doesn't have S3 permissions (check IAM role)
2. File processing failed (check CloudWatch logs)
3. S3 versioning is enabled (check bucket configuration)

**Debug:**
```bash
# Check S3 permissions
aws s3 ls s3://dev-answering-procesapp-info/

# Check Lambda logs
aws logs tail /aws/lambda/processapp-ingester-dev --since 30m
```

### Issue: Failed records file not created

**Symptom:** No .failed.txt file despite errors

**Causes:**
- All records succeeded (check response.json: `error_count: 0`)
- Lambda doesn't have S3 write permissions
- Processing crashed before error file creation

**Verify:**
```bash
# Check response
cat response.json | jq '.body | fromjson | .results[0]'

# Should show:
# {
#   "file": "yourfile.csv",
#   "success_count": 100,
#   "error_count": 5,  # <-- If > 0, .failed.txt should exist
#   "status": "completed"
# }
```

### Getting Help

1. **Check CloudWatch Logs** (most informative):
   ```bash
   aws logs tail /aws/lambda/processapp-ingester-dev --since 1h
   ```

2. **Check S3 for files**:
   ```bash
   aws s3 ls s3://dev-answering-procesapp-info/ --recursive
   ```

3. **Verify DynamoDB table**:
   ```bash
   aws dynamodb describe-table --table-name Dev-ExternalData
   ```

4. **Test API endpoint**:
   ```bash
   curl -v https://gvhyyvhmhj.execute-api.us-east-1.amazonaws.com/dev/external/test/test
   ```

## Project Structure

```
infrastructure/
├── bin/
│   └── app.ts              # CDK app entry point
├── lib/
│   ├── PrereqsStack.ts     # DynamoDB, KMS, IAM roles
│   ├── IngesterStack.ts    # Ingester Lambda
│   └── ConsumerStack.ts    # Consumer Lambda + API Gateway
├── config/
│   ├── environments.ts     # Environment configuration
│   └── security.config.ts  # IAM policy helpers
├── lambdas/
│   ├── ingester/
│   │   ├── index.py        # Streaming ingester
│   │   └── requirements.txt
│   └── consumer/
│       ├── index.py        # API consumer
│       └── requirements.txt
└── scripts/
    ├── ingest.sh           # Helper script for ingestion (Bash)
    ├── ingest.ps1          # Helper script for ingestion (PowerShell)
    ├── query.sh            # Helper script for API queries (Bash)
    └── query.ps1           # Helper script for API queries (PowerShell)
```

## Quick Reference

### Ingestion Command Templates

**Linux/macOS:**
```bash
# Standard ingestion
./scripts/ingest.sh dev <FILE.csv> "<PARTITION_KEY_COLUMN>" "<SORT_KEY_VALUE>"

# Using row index as sort key
./scripts/ingest.sh dev <FILE.csv> "<PARTITION_KEY_COLUMN>"

# Direct AWS CLI (if you prefer)
aws lambda invoke \
  --function-name processapp-ingester-dev \
  --payload '{"config":[{"table":"Dev-ExternalData","partitionKey":"COLUMN_NAME","sortKey":"FIXED_VALUE","file":"FILE.csv","ignore":false}]}' \
  --cli-binary-format raw-in-base64-out \
  response.json
```

**Windows:**
```powershell
# Standard ingestion
.\scripts\ingest.ps1 -Stage dev -File <FILE.csv> -PartitionKey "<PARTITION_KEY_COLUMN>" -SortKey "<SORT_KEY_VALUE>"

# Using row index as sort key
.\scripts\ingest.ps1 -Stage dev -File <FILE.csv> -PartitionKey "<PARTITION_KEY_COLUMN>"

# Direct AWS CLI (if you prefer)
aws lambda invoke `
  --function-name processapp-ingester-dev `
  --payload '{\"config\":[{\"table\":\"Dev-ExternalData\",\"partitionKey\":\"COLUMN_NAME\",\"sortKey\":\"FIXED_VALUE\",\"file\":\"FILE.csv\",\"ignore\":false}]}' `
  --cli-binary-format raw-in-base64-out `
  response.json
```

### Query Command Templates

**Linux/macOS:**
```bash
# Using helper script
./scripts/query.sh dev "<PARTITION_KEY>" "<SORT_KEY>"

# Direct curl
curl -X GET "https://gvhyyvhmhj.execute-api.us-east-1.amazonaws.com/dev/external/<PARTITION_KEY>/<SORT_KEY>"
```

**Windows:**
```powershell
# Using helper script
.\scripts\query.ps1 -Stage dev -PartitionKey "<PARTITION_KEY>" -SortKey "<SORT_KEY>"

# Direct Invoke-RestMethod
Invoke-RestMethod -Uri "https://gvhyyvhmhj.execute-api.us-east-1.amazonaws.com/dev/external/<PARTITION_KEY>/<SORT_KEY>" -Method Get

# Or with curl.exe (if installed)
curl.exe -X GET "https://gvhyyvhmhj.execute-api.us-east-1.amazonaws.com/dev/external/<PARTITION_KEY>/<SORT_KEY>"
```

### Useful AWS Commands

```bash
# List files in S3
aws s3 ls s3://dev-answering-procesapp-info/

# Download a file from S3
aws s3 cp s3://dev-answering-procesapp-info/file.csv ./

# View Lambda logs (last 30 minutes)
aws logs tail /aws/lambda/processapp-ingester-dev --since 30m

# Check DynamoDB item count
aws dynamodb scan --table-name Dev-ExternalData --select COUNT

# Get specific item from DynamoDB
aws dynamodb get-item \
  --table-name Dev-ExternalData \
  --key '{"partitionKey":{"S":"YOUR_KEY"},"sortKey":{"S":"YOUR_SORT"}}'
```

### Configuration Files Location

```
infrastructure/
├── config/
│   ├── environments.ts     # Change: Lambda memory, timeout, batch size
│   └── security.config.ts  # Change: IAM permissions
├── lambdas/
│   ├── ingester/index.py   # Ingestion logic
│   └── consumer/index.py   # API query logic
└── scripts/
    ├── ingest.sh           # Ingestion helper
    └── query.sh            # Query helper
```

### Important URLs and ARNs

| Resource | Value |
|----------|-------|
| **API Gateway URL** | https://gvhyyvhmhj.execute-api.us-east-1.amazonaws.com/dev/ |
| **DynamoDB Table** | Dev-ExternalData |
| **Ingester Lambda** | processapp-ingester-dev |
| **Consumer Lambda** | processapp-consumer-dev |
| **S3 Bucket** | dev-answering-procesapp-info |
| **Region** | us-east-1 |

### Authorized Users

Only these users can invoke the ingester Lambda:
1. **qohat.prettel** - arn:aws:iam::708819485463:user/qohat.prettel
2. **david.jimenez** - arn:aws:iam::708819485463:user/david.jimenez
3. **soportejoven@answering.com.co** - arn:aws:iam::708819485463:user/soportejoven@answering.com.co

## DynamoDB Console Access

Any user in the account can access the DynamoDB table by attaching one of the managed policies.

**📖 See detailed instructions**: [docs/CONSOLE_ACCESS.md](docs/CONSOLE_ACCESS.md)

**Managed Policies Available**:

| Policy | ARN | Permissions |
|--------|-----|-------------|
| `processapp-dynamodb-readonly-dev` | `arn:aws:iam::708819485463:policy/processapp-dynamodb-readonly-dev` | Read-only |
| `processapp-dynamodb-readwrite-dev` | `arn:aws:iam::708819485463:policy/processapp-dynamodb-readwrite-dev` | Read-Write |

**Quick Start - Attach Policy to User**:
```bash
# Read-only access
aws iam attach-user-policy \
  --user-name USERNAME \
  --policy-arn arn:aws:iam::708819485463:policy/processapp-dynamodb-readonly-dev \
  --profile ans-super

# Read-write access
aws iam attach-user-policy \
  --user-name USERNAME \
  --policy-arn arn:aws:iam::708819485463:policy/processapp-dynamodb-readwrite-dev \
  --profile ans-super
```

**Or use IAM Console**:
1. Go to **IAM Console** → **Users** → Select user
2. Click **Add permissions** → **Attach policies directly**
3. Search for `processapp-dynamodb-readonly-dev` or `processapp-dynamodb-readwrite-dev`
4. User can now access DynamoDB Console → Tables → `Dev-ExternalData`

**Read-Only Policy**:
- ✅ View, Scan, Query table items
- ✅ Decrypt encrypted data (via KMS)
- ❌ No write or delete permissions

**Read-Write Policy**:
- ✅ All read permissions
- ✅ Create, Update, Delete items
- ✅ Batch operations and PartiQL editor
- ⚠️ Use with caution - can modify/delete data

## License

MIT

---

## Resources Created 

dev-ConsumerStack.ApiEndpoint = https://gvhyyvhmhj.execute-api.us-east-1.amazonaws.com/dev/external/{partitionKey}/{sortKey}
dev-ConsumerStack.ApiUrl = https://gvhyyvhmhj.execute-api.us-east-1.amazonaws.com/dev/
dev-ConsumerStack.ConsumerFunctionArn = arn:aws:lambda:us-east-1:708819485463:function:processapp-consumer-dev
dev-ConsumerStack.ConsumerFunctionName = processapp-consumer-dev
dev-ConsumerStack.ExampleCurlCommand = curl -X GET "https://gvhyyvhmhj.execute-api.us-east-1.amazonaws.com/dev/external/YOUR_PARTITION_KEY/YOUR_SORT_KEY"
dev-ConsumerStack.ExternalDataApiEndpoint1E73F102 = https://gvhyyvhmhj.execute-api.us-east-1.amazonaws.com/dev/
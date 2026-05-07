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

## Prerequisites

- Node.js 18+ and npm
- AWS CLI v2
- AWS CDK CLI (`npm install -g aws-cdk`)
- AWS profile configured (`ans-super`)
- S3 bucket: `dev-answering-procesapp-info` (must exist)

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

## Usage

### 1. Upload CSV to S3

```bash
aws s3 cp your-file.csv s3://dev-answering-procesapp-info/ --profile ans-super
```

### 2. Ingest File

Use the helper script:

```bash
# Format: ./scripts/ingest.sh <stage> <file> <partitionKey> [sortKey]
./scripts/ingest.sh dev fedecafetero.csv "doc" "fedecafetero"
```

**Important Notes:**
- `partitionKey` refers to the **column name** in the CSV (e.g., "doc", "documento")
- The value in that column becomes the partition key in DynamoDB
- `sortKey` is a **fixed value** used for the sort key (or omit to use row index)

Example CSV:
```csv
doc,name,value
12345,John Doe,100
67890,Jane Smith,200
```

With command: `./scripts/ingest.sh dev data.csv "doc" "fedecafetero"`
- DynamoDB record 1: partitionKey="12345", sortKey="fedecafetero"
- DynamoDB record 2: partitionKey="67890", sortKey="fedecafetero"

### 3. Query via API

```bash
# Using helper script
./scripts/query.sh dev "12345" "fedecafetero"

# Or directly with curl
curl -X GET "https://API_ID.execute-api.us-east-1.amazonaws.com/dev/external/12345/fedecafetero"
```

### 4. Check Logs

```bash
# Ingester logs
aws logs tail /aws/lambda/processapp-ingester-dev --follow --profile ans-super

# Consumer logs
aws logs tail /aws/lambda/processapp-consumer-dev --follow --profile ans-super
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

## Testing

### Generate Test CSV

```bash
python -c "
import csv
with open('test.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['doc', 'name', 'value'])
    for i in range(100):
        writer.writerow([f'doc-{i}', f'Name {i}', i * 10])
"

aws s3 cp test.csv s3://dev-answering-procesapp-info/ --profile ans-super
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

### Lambda timeout on large files

- Increase `timeoutSeconds` in `config/environments.ts`
- Current limit: 900 seconds (15 minutes)

### DynamoDB throttling

- Current billing mode: PAY_PER_REQUEST (no throttling)
- If switching to PROVISIONED, adjust capacity units

### CSV parsing errors

- Ensure CSV has header row
- Check column names match `partitionKey`/`sortKey` config
- Verify UTF-8 encoding

### API Gateway 403 errors

- Check CORS configuration in ConsumerStack
- Verify API Gateway deployment stage

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
    ├── ingest.sh           # Helper script for ingestion
    └── query.sh            # Helper script for API queries
```

## License

MIT


## Resources Created 

dev-ConsumerStack.ApiEndpoint = https://gvhyyvhmhj.execute-api.us-east-1.amazonaws.com/dev/external/{partitionKey}/{sortKey}
dev-ConsumerStack.ApiUrl = https://gvhyyvhmhj.execute-api.us-east-1.amazonaws.com/dev/
dev-ConsumerStack.ConsumerFunctionArn = arn:aws:lambda:us-east-1:708819485463:function:processapp-consumer-dev
dev-ConsumerStack.ConsumerFunctionName = processapp-consumer-dev
dev-ConsumerStack.ExampleCurlCommand = curl -X GET "https://gvhyyvhmhj.execute-api.us-east-1.amazonaws.com/dev/external/YOUR_PARTITION_KEY/YOUR_SORT_KEY"
dev-ConsumerStack.ExternalDataApiEndpoint1E73F102 = https://gvhyyvhmhj.execute-api.us-east-1.amazonaws.com/dev/
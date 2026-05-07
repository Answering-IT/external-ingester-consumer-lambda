#!/bin/bash

# Ingestion helper script
# Usage: ./ingest.sh <stage> <file> <partitionKey> [sortKey]
#
# Example:
#   ./ingest.sh dev fedecafetero.csv "doc" "fedecafetero"
#
# Notes:
# - partitionKey refers to the column name in the CSV (e.g., "doc")
# - sortKey is a fixed value that will be used as the sort key

set -e

if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <stage> <file> <partitionKey> [sortKey]"
    echo ""
    echo "Arguments:"
    echo "  stage         : Environment stage (dev, staging, prod)"
    echo "  file          : S3 file name (e.g., fedecafetero.csv)"
    echo "  partitionKey  : Column name in CSV to use as partition key"
    echo "  sortKey       : Fixed sort key value (optional, defaults to row index)"
    echo ""
    echo "Example:"
    echo "  $0 dev fedecafetero.csv doc fedecafetero"
    exit 1
fi

STAGE=$1
FILE=$2
PARTITION_KEY=$3
SORT_KEY=${4:-null}

# Capitalize first letter of stage for table name
TABLE_NAME="$(tr '[:lower:]' '[:upper:]' <<< ${STAGE:0:1})${STAGE:1}-ExternalData"

# Build payload
if [ "$SORT_KEY" == "null" ]; then
    PAYLOAD=$(cat <<EOF
{
  "config": [
    {
      "table": "$TABLE_NAME",
      "partitionKey": "$PARTITION_KEY",
      "file": "$FILE",
      "ignore": false
    }
  ]
}
EOF
)
else
    PAYLOAD=$(cat <<EOF
{
  "config": [
    {
      "table": "$TABLE_NAME",
      "partitionKey": "$PARTITION_KEY",
      "sortKey": "$SORT_KEY",
      "file": "$FILE",
      "ignore": false
    }
  ]
}
EOF
)
fi

echo "Invoking ingester Lambda..."
echo "Stage: $STAGE"
echo "Table: $TABLE_NAME"
echo "File: $FILE"
echo "Partition Key Column: $PARTITION_KEY"
echo "Sort Key: $SORT_KEY"
echo ""

aws lambda invoke \
  --function-name "processapp-ingester-${STAGE}" \
  --payload "$PAYLOAD" \
  --profile ans-super \
  --cli-binary-format raw-in-base64-out \
  response.json

echo ""
echo "Response:"
cat response.json | jq .

echo ""
echo "CloudWatch Logs:"
echo "aws logs tail /aws/lambda/processapp-ingester-${STAGE} --follow --profile ans-super"

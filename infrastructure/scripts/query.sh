#!/bin/bash

# API Query helper script
# Usage: ./query.sh <stage> <partitionKey> <sortKey>
#
# Example:
#   ./query.sh dev doc fedecafetero

set -e

if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <stage> <partitionKey> <sortKey>"
    echo ""
    echo "Arguments:"
    echo "  stage        : Environment stage (dev, staging, prod)"
    echo "  partitionKey : Partition key value to query"
    echo "  sortKey      : Sort key value to query"
    echo ""
    echo "Example:"
    echo "  $0 dev doc fedecafetero"
    exit 1
fi

STAGE=$1
PARTITION_KEY=$2
SORT_KEY=$3

# Get API URL from CloudFormation stack outputs
# Capitalize first letter of stage for stack name
CAPITAL_STAGE="$(tr '[:lower:]' '[:upper:]' <<< ${STAGE:0:1})${STAGE:1}"
STACK_NAME="${CAPITAL_STAGE}-ConsumerStack"

echo "Fetching API URL from CloudFormation stack: $STACK_NAME"

API_URL=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
  --output text \
  --profile ans-super)

if [ -z "$API_URL" ]; then
    echo "Error: Could not retrieve API URL from CloudFormation"
    echo "Make sure the stack is deployed: cdk deploy ${CAPITAL_STAGE}-ConsumerStack"
    exit 1
fi

# Remove trailing slash if present
API_URL=${API_URL%/}

ENDPOINT="${API_URL}/external/${PARTITION_KEY}/${SORT_KEY}"

echo ""
echo "Querying API Gateway..."
echo "Endpoint: $ENDPOINT"
echo ""

curl -s -X GET "$ENDPOINT" | jq .

echo ""

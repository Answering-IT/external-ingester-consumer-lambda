"""
Consumer Lambda: Query DynamoDB records via API Gateway
"""

import json
import os
import boto3
from typing import Dict, Any

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')

# Environment variables
DYNAMODB_TABLE = os.environ['DYNAMODB_TABLE']
STAGE = os.environ['STAGE']


def lambda_handler(event, context):
    """
    Handler for API Gateway GET request
    Path: /external/{partitionKey}/{sortKey}

    Event structure from API Gateway:
    {
      "pathParameters": {
        "partitionKey": "...",
        "sortKey": "..."
      },
      "requestContext": {...},
      ...
    }
    """
    print(f'Received event: {json.dumps(event)}')

    try:
        # Extract path parameters
        path_params = event.get('pathParameters', {})

        if not path_params:
            return format_response(400, {
                'error': 'Missing path parameters',
                'status': 'bad_request'
            })

        partition_key = path_params.get('partitionKey')
        sort_key = path_params.get('sortKey')

        # Validate parameters
        if not partition_key or not sort_key:
            return format_response(400, {
                'error': 'Both partitionKey and sortKey are required',
                'status': 'bad_request',
                'received': {
                    'partitionKey': partition_key,
                    'sortKey': sort_key
                }
            })

        print(f'Querying DynamoDB: partitionKey={partition_key}, sortKey={sort_key}')

        # Query DynamoDB
        table = dynamodb.Table(DYNAMODB_TABLE)

        response = table.get_item(
            Key={
                'partitionKey': partition_key,
                'sortKey': sort_key
            }
        )

        # Check if item exists
        if 'Item' not in response:
            print(f'Record not found: partitionKey={partition_key}, sortKey={sort_key}')
            return format_response(404, {
                'error': 'Record not found',
                'status': 'not_found',
                'query': {
                    'partitionKey': partition_key,
                    'sortKey': sort_key
                }
            })

        # Return item
        item = response['Item']
        print(f'Record found: {item.get("sourceFile", "unknown")} row {item.get("rowIndex", 0)}')

        return format_response(200, {
            'data': serialize_dynamodb_item(item),
            'status': 'success'
        })

    except KeyError as e:
        print(f'Missing required path parameter: {str(e)}')
        return format_response(400, {
            'error': f'Missing required path parameter: {str(e)}',
            'status': 'bad_request'
        })

    except Exception as e:
        print(f'Error: {str(e)}')
        import traceback
        traceback.print_exc()
        return format_response(500, {
            'error': 'Internal server error',
            'status': 'error',
            'details': str(e)
        })


def format_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format API Gateway response with proper headers
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,OPTIONS'
        },
        'body': json.dumps(body, default=str)
    }


def serialize_dynamodb_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize DynamoDB item (handles Decimal types, etc.)
    """
    from decimal import Decimal

    def convert(obj):
        if isinstance(obj, Decimal):
            # Convert Decimal to int or float
            return int(obj) if obj % 1 == 0 else float(obj)
        elif isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert(i) for i in obj]
        return obj

    return convert(item)

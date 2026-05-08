"""
Ingester Lambda: Stream-based CSV/TXT file processor
Processes large files from S3 and writes to DynamoDB with constant memory usage
"""

import io
import csv
import json
import os
import boto3
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Environment variables
S3_BUCKET = os.environ['S3_BUCKET']
DYNAMODB_TABLE = os.environ['DYNAMODB_TABLE']
STAGE = os.environ['STAGE']
KMS_KEY_ID = os.environ.get('KMS_KEY_ID', '')
BATCH_SIZE = int(os.environ.get('BATCH_SIZE', '25'))
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '3'))


def lambda_handler(event, context):
    """
    Main Lambda handler

    Expected payload:
    {
      "config": [
        {
          "table": "dev-ExternalData",
          "partitionKey": "doc",
          "sortKey": "fedecafetero",
          "file": "fedecafetero.csv",
          "ignore": false
        }
      ]
    }
    """
    print(f'Received event: {json.dumps(event)}')

    try:
        config_list = event.get('config', [])

        if not config_list:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing config array in event payload'
                })
            }

        results = []

        for config in config_list:
            # Skip if ignore flag is True
            if config.get('ignore', False):
                print(f'Skipping file {config.get("file")} (ignore flag set)')
                continue

            # Validate config
            validation_error = validate_config(config)
            if validation_error:
                results.append({
                    'file': config.get('file', 'unknown'),
                    'status': 'error',
                    'error': validation_error
                })
                continue

            # Process file
            print(f'Processing file: {config["file"]}')
            result = stream_process_file(config, S3_BUCKET)
            results.append(result)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Ingestion completed',
                'results': results
            })
        }

    except Exception as e:
        print(f'Lambda handler error: {str(e)}')
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error',
                'details': str(e)
            })
        }


def validate_config(config: Dict[str, Any]) -> Optional[str]:
    """Validate configuration object"""
    required_fields = ['table', 'partitionKey', 'file']

    for field in required_fields:
        if field not in config or not config[field]:
            return f'Missing required field: {field}'

    return None


def detect_delimiter(sample_line: str) -> str:
    """
    Auto-detect delimiter from a sample line.
    Tests common delimiters: comma, semicolon, tab, pipe
    """
    delimiters = [',', ';', '\t', '|']
    delimiter_counts = {}

    for delim in delimiters:
        count = sample_line.count(delim)
        if count > 0:
            delimiter_counts[delim] = count

    if not delimiter_counts:
        # Default to comma if no delimiter found
        return ','

    # Return delimiter with highest count
    detected = max(delimiter_counts, key=delimiter_counts.get)
    print(f'Auto-detected delimiter: "{detected}" (found {delimiter_counts[detected]} occurrences)')
    return detected


def stream_process_file(config: Dict[str, Any], bucket: str) -> Dict[str, Any]:
    """
    Stream-based file processor for large CSV/TXT files.
    Constant memory usage regardless of file size.

    Auto-detects:
    - Delimiter (comma, semicolon, tab, pipe)
    - File format (CSV with headers or TXT)
    """
    file_key = config['file']
    table_name = config['table']
    partition_key_name = config['partitionKey']
    sort_key_name = config.get('sortKey')

    table = dynamodb.Table(table_name)

    try:
        # Check if file has already been processed
        if file_key.endswith('.ingested'):
            print(f'File {file_key} already processed (has .ingested suffix)')
            return {
                'file': file_key,
                'status': 'skipped',
                'reason': 'Already processed'
            }

        # Stream file from S3 (no download to disk)
        print(f'Streaming file from S3: s3://{bucket}/{file_key}')
        response = s3_client.get_object(Bucket=bucket, Key=file_key)

        # Wrap streaming body in text wrapper for line-by-line reading
        stream = io.TextIOWrapper(response['Body'], encoding='utf-8', newline='')

        # Read first line (header) to detect delimiter
        first_line = stream.readline()
        if not first_line:
            raise ValueError('File is empty')

        # Detect delimiter from first line
        delimiter = detect_delimiter(first_line)

        # Parse fieldnames from the first line (header row)
        # No seek needed - we already consumed the header, remaining lines are data
        print(f'Processing file with delimiter: "{delimiter}"')
        fieldnames = [f.strip() for f in first_line.strip().split(delimiter)]

        # Create CSV reader for remaining lines using detected fieldnames
        reader = csv.DictReader(stream, fieldnames=fieldnames, delimiter=delimiter)

        if not fieldnames:
            raise ValueError('Could not detect column headers in file')

        print(f'Detected columns: {fieldnames}')

        # Validate partition key exists in headers
        if partition_key_name not in fieldnames:
            raise ValueError(f'Partition key column "{partition_key_name}" not found. Available columns: {fieldnames}')

        # Determine if sortKey is a column name or a fixed value
        sort_key_is_column = sort_key_name and sort_key_name in fieldnames

        # Accumulators
        batch = []
        error_records = []
        success_count = 0
        row_index = 0

        print(f'Processing file with columns: {fieldnames}')

        for row in reader:
            row_index += 1

            try:
                # Extract partition and sort keys
                partition_key = row.get(partition_key_name, '').strip()

                if sort_key_name:
                    if sort_key_is_column:
                        # sortKey is a column name, use value from that column
                        sort_key = row.get(sort_key_name, '').strip()
                    else:
                        # sortKey is a fixed value, use it as-is for all records
                        sort_key = sort_key_name
                else:
                    # Use row index as sort key if not specified
                    sort_key = str(row_index)

                # Validate partition key
                if not partition_key:
                    error_records.append({
                        **row,
                        'error_reason': f'Missing or empty partition key: {partition_key_name}'
                    })
                    continue

                # Build DynamoDB item
                item = {
                    'partitionKey': partition_key,
                    'sortKey': sort_key,
                    'createdAt': datetime.utcnow().isoformat(),
                    'sourceFile': file_key,
                    'rowIndex': row_index,
                    'status': 'active'
                }

                # Add all other columns (preserve original data)
                for col, val in row.items():
                    if col and val:  # Skip empty columns
                        # Use original column name with prefix to avoid conflicts
                        item[f'data_{col}'] = val.strip()

                batch.append(item)

                # Flush batch when full
                if len(batch) >= BATCH_SIZE:
                    batch_success = batch_write_with_retry(table, batch)
                    success_count += batch_success
                    print(f'Processed {success_count} records so far...')
                    batch.clear()

            except Exception as e:
                print(f'Error processing row {row_index}: {str(e)}')
                error_records.append({
                    **row,
                    'error_reason': f'Processing error: {str(e)}'
                })

        # Flush remaining items
        if batch:
            batch_success = batch_write_with_retry(table, batch)
            success_count += batch_success

        print(f'File processing complete. Success: {success_count}, Errors: {len(error_records)}')

        # Write error file if errors occurred
        if error_records:
            print(f'Writing error file with {len(error_records)} failed records')
            write_error_csv(bucket, file_key, error_records, fieldnames)

        # Rename original file with .ingested suffix
        rename_file(bucket, file_key)

        return {
            'file': file_key,
            'success_count': success_count,
            'error_count': len(error_records),
            'status': 'completed'
        }

    except Exception as e:
        print(f'Error processing file {file_key}: {str(e)}')
        import traceback
        traceback.print_exc()
        return {
            'file': file_key,
            'status': 'error',
            'error': str(e)
        }


def batch_write_with_retry(table, items: List[Dict]) -> int:
    """
    Write batch to DynamoDB with exponential backoff retry.
    Returns number of successfully written items.
    """
    if not items:
        return 0

    request_items = {
        table.name: [
            {'PutRequest': {'Item': item}}
            for item in items
        ]
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = table.meta.client.batch_write_item(
                RequestItems=request_items
            )

            # Handle unprocessed items
            unprocessed = response.get('UnprocessedItems', {})
            if not unprocessed:
                return len(items)

            # Retry unprocessed items
            print(f'Retrying {len(unprocessed.get(table.name, []))} unprocessed items (attempt {attempt + 1})')
            request_items = unprocessed
            time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s

        except Exception as e:
            print(f'Batch write error (attempt {attempt + 1}/{MAX_RETRIES}): {str(e)}')
            if attempt == MAX_RETRIES - 1:
                print(f'Batch write failed after {MAX_RETRIES} attempts')
                return 0
            time.sleep(2 ** attempt)

    # Return count of successfully written items
    unprocessed_count = len(request_items.get(table.name, []))
    return len(items) - unprocessed_count


def write_error_csv(bucket: str, file_key: str, errors: List[Dict], fieldnames: List[str]):
    """
    Write failed records to CSV file with error_reason column.
    """
    error_key = f"{file_key}.failed.txt"

    try:
        # Add error_reason to fieldnames
        extended_fieldnames = list(fieldnames) + ['error_reason']

        # Build CSV content
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=extended_fieldnames)
        writer.writeheader()
        writer.writerows(errors)

        # Upload to S3
        s3_client.put_object(
            Bucket=bucket,
            Key=error_key,
            Body=output.getvalue().encode('utf-8'),
            ContentType='text/csv'
        )

        print(f'Error file written: s3://{bucket}/{error_key}')

    except Exception as e:
        print(f'Failed to write error file: {str(e)}')


def rename_file(bucket: str, file_key: str):
    """
    Rename file with .ingested suffix
    """
    new_key = f"{file_key}.ingested"

    try:
        # Copy with new name
        s3_client.copy_object(
            Bucket=bucket,
            Key=new_key,
            CopySource={'Bucket': bucket, 'Key': file_key}
        )

        # Delete original
        s3_client.delete_object(Bucket=bucket, Key=file_key)

        print(f'File renamed: {file_key} -> {new_key}')

    except Exception as e:
        print(f'Failed to rename file: {str(e)}')

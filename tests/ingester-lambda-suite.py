"""
Test Suite: Ingester Lambda Function
=====================================
Tests the ingester lambda using the data files in tests/resources/:
- federacionArroz.txt (comma-separated)
- federacionCafetera.csv (semicolon-separated)
- federacionCafetera.txt (comma-separated)

Uses moto to mock AWS services (S3, DynamoDB) for local testing.

Run: pip install moto boto3
     python -m unittest tests.ingested-lambda-spec -v
"""

import unittest
import json
import os
import sys
import io
import boto3
from unittest.mock import patch
from moto import mock_aws

# Add lambda path to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'infrastructure', 'lambdas', 'ingester'))

# ============================================================
# Constants
# ============================================================

S3_BUCKET = "dev-answering-procesapp-info"
DYNAMODB_TABLE = "dev-ExternalData"
STAGE = "dev"

ENV_VARS = {
    "S3_BUCKET": S3_BUCKET,
    "DYNAMODB_TABLE": DYNAMODB_TABLE,
    "STAGE": STAGE,
    "KMS_KEY_ID": "test-kms-key-id",
    "BATCH_SIZE": "25",
    "MAX_RETRIES": "3",
}

# ============================================================
# Helper Functions
# ============================================================

def load_resource_files():
    """Load test data files from tests/resources/ directory."""
    resources_dir = os.path.join(os.path.dirname(__file__), 'resources')
    file_contents = {}

    resource_files = [
        "federacionArroz.txt",
        "federacionCafetera.csv",
        "federacionCafetera.txt"
    ]

    for filename in resource_files:
        file_path = os.path.join(resources_dir, filename)
        # Use utf-8-sig to handle BOM if present
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            file_contents[filename] = f.read()

    return file_contents

# Load file contents from resources directory
FILE_CONTENTS = load_resource_files()


# ============================================================
# Base Test Class
# ============================================================

class BaseLambdaTest(unittest.TestCase):
    """Base class that sets up mocked AWS environment with seekable S3 streams."""

    def setUp(self):
        """Set up mocked AWS services before each test."""
        self.env_patcher = patch.dict(os.environ, ENV_VARS)
        self.env_patcher.start()

        self.mock_aws = mock_aws()
        self.mock_aws.start()

        # Create S3 bucket and upload test files
        self.s3 = boto3.client("s3", region_name="us-east-1")
        self.s3.create_bucket(Bucket=S3_BUCKET)
        for key, content in FILE_CONTENTS.items():
            self.s3.put_object(Bucket=S3_BUCKET, Key=key, Body=content.encode("utf-8"))

        # Create DynamoDB table
        self.dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        self.table = self.dynamodb.create_table(
            TableName=DYNAMODB_TABLE,
            KeySchema=[
                {"AttributeName": "partitionKey", "KeyType": "HASH"},
                {"AttributeName": "sortKey", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "partitionKey", "AttributeType": "S"},
                {"AttributeName": "sortKey", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        self.table.meta.client.get_waiter("table_exists").wait(TableName=DYNAMODB_TABLE)

        # Import lambda module fresh (picks up mocked clients)
        if "index" in sys.modules:
            del sys.modules["index"]
        import index
        self.index = index

        # Patch the s3_client inside the lambda module to return seekable streams
        self._original_get_object = self.index.s3_client.get_object
        self._original_put_object = self.index.s3_client.put_object
        self._original_copy_object = self.index.s3_client.copy_object
        self._original_delete_object = self.index.s3_client.delete_object

        # Store uploaded files for tracking
        self._s3_store = {}
        for key, content in FILE_CONTENTS.items():
            self._s3_store[key] = content.encode("utf-8")

        def mock_get_object(Bucket, Key):
            """Return a seekable BytesIO stream instead of moto's non-seekable one."""
            if Key in self._s3_store:
                body_bytes = self._s3_store[Key]
            else:
                response = self._original_get_object(Bucket=Bucket, Key=Key)
                body_bytes = response['Body'].read()
            return {
                'Body': io.BytesIO(body_bytes),
                'ContentLength': len(body_bytes),
                'ContentType': 'application/octet-stream',
            }

        def mock_put_object(Bucket, Key, Body, **kwargs):
            """Track put_object calls in our store."""
            if isinstance(Body, bytes):
                self._s3_store[Key] = Body
            elif isinstance(Body, str):
                self._s3_store[Key] = Body.encode("utf-8")
            else:
                self._s3_store[Key] = Body.read() if hasattr(Body, 'read') else bytes(Body)
            return self._original_put_object(Bucket=Bucket, Key=Key, Body=self._s3_store[Key], **kwargs)

        def mock_copy_object(Bucket, Key, CopySource, **kwargs):
            """Track copy operations in our store."""
            source_key = CopySource['Key'] if isinstance(CopySource, dict) else CopySource
            if source_key in self._s3_store:
                self._s3_store[Key] = self._s3_store[source_key]
            return self._original_copy_object(Bucket=Bucket, Key=Key, CopySource=CopySource, **kwargs)

        def mock_delete_object(Bucket, Key, **kwargs):
            """Track delete operations in our store."""
            self._s3_store.pop(Key, None)
            return self._original_delete_object(Bucket=Bucket, Key=Key, **kwargs)

        self.index.s3_client.get_object = mock_get_object
        self.index.s3_client.put_object = mock_put_object
        self.index.s3_client.copy_object = mock_copy_object
        self.index.s3_client.delete_object = mock_delete_object

    def tearDown(self):
        """Clean up mocks after each test."""
        self.mock_aws.stop()
        self.env_patcher.stop()
        if "index" in sys.modules:
            del sys.modules["index"]

    def upload_test_file(self, key, content):
        """Helper to upload additional test files."""
        body = content.encode("utf-8") if isinstance(content, str) else content
        self._s3_store[key] = body
        self.s3.put_object(Bucket=S3_BUCKET, Key=key, Body=body)

    def s3_key_exists(self, key):
        """Check if a key exists in our tracked S3 store."""
        return key in self._s3_store


# ============================================================
# Tests: Validate Config
# ============================================================

class TestValidateConfig(BaseLambdaTest):
    """Tests for config validation logic."""

    def test_valid_config_all_fields(self):
        """Config with all required fields should pass validation."""
        config = {
            "table": DYNAMODB_TABLE,
            "partitionKey": "doc",
            "sortKey": "nombre",
            "file": "federacionArroz.txt",
            "ignore": False,
        }
        result = self.index.validate_config(config)
        self.assertIsNone(result)

    def test_missing_table(self):
        """Config without 'table' should return error."""
        config = {"partitionKey": "doc", "file": "test.csv"}
        result = self.index.validate_config(config)
        self.assertIn("table", result)

    def test_missing_partition_key(self):
        """Config without 'partitionKey' should return error."""
        config = {"table": DYNAMODB_TABLE, "file": "test.csv"}
        result = self.index.validate_config(config)
        self.assertIn("partitionKey", result)

    def test_missing_file(self):
        """Config without 'file' should return error."""
        config = {"table": DYNAMODB_TABLE, "partitionKey": "doc"}
        result = self.index.validate_config(config)
        self.assertIn("file", result)

    def test_empty_partition_key(self):
        """Config with empty partitionKey should return error."""
        config = {"table": DYNAMODB_TABLE, "partitionKey": "", "file": "test.csv"}
        result = self.index.validate_config(config)
        self.assertIn("partitionKey", result)


# ============================================================
# Tests: Delimiter Detection
# ============================================================

class TestDelimiterDetection(BaseLambdaTest):
    """Tests for auto-detection of CSV delimiters."""

    def test_detect_comma(self):
        """Should detect comma delimiter."""
        line = "doc,nombre,edad,estatura,ciudad,celular"
        self.assertEqual(self.index.detect_delimiter(line), ",")

    def test_detect_semicolon(self):
        """Should detect semicolon delimiter."""
        line = "documento;fecha;nombre;edad"
        self.assertEqual(self.index.detect_delimiter(line), ";")

    def test_detect_tab(self):
        """Should detect tab delimiter."""
        line = "doc\tnombre\tedad\tciudad"
        self.assertEqual(self.index.detect_delimiter(line), "\t")

    def test_detect_pipe(self):
        """Should detect pipe delimiter."""
        line = "doc|nombre|edad|ciudad"
        self.assertEqual(self.index.detect_delimiter(line), "|")

    def test_default_comma_when_no_delimiter(self):
        """Should default to comma when no delimiter is found."""
        line = "single_column_no_delimiter"
        self.assertEqual(self.index.detect_delimiter(line), ",")


# ============================================================
# Tests: Ingestion federacionArroz.txt (comma-separated)
# sortKey=nombre means the value of column "nombre" is used as DynamoDB sortKey
# ============================================================

class TestIngesterFederacionArroz(BaseLambdaTest):
    """Test ingestion of federacionArroz.txt (comma-separated, partitionKey=doc, sortKey=nombre)."""

    def _get_event(self):
        """Standard event for federacionArroz.txt ingestion."""
        return {
            "config": [
                {
                    "table": DYNAMODB_TABLE,
                    "partitionKey": "doc",
                    "sortKey": "nombre",
                    "file": "federacionArroz.txt",
                    "ignore": False,
                }
            ]
        }

    def test_ingest_arroz_success(self):
        """Should ingest federacionArroz.txt successfully with 2 records."""
        response = self.index.lambda_handler(self._get_event(), None)

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["message"], "Ingestion completed")
        self.assertEqual(len(body["results"]), 1)
        self.assertEqual(body["results"][0]["status"], "completed")
        self.assertEqual(body["results"][0]["success_count"], 2)
        self.assertEqual(body["results"][0]["error_count"], 0)

    def test_ingest_arroz_dynamodb_records(self):
        """Should write correct records to DynamoDB for federacionArroz.txt."""
        self.index.lambda_handler(self._get_event(), None)

        table = self.dynamodb.Table(DYNAMODB_TABLE)

        # Record 1: doc=11023345, nombre=claude (sortKey value from "nombre" column)
        item1 = table.get_item(Key={"partitionKey": "11023345", "sortKey": "claude"})
        self.assertIn("Item", item1)
        self.assertEqual(item1["Item"]["data_nombre"], "claude")
        self.assertEqual(item1["Item"]["data_ciudad"], "santa marta")
        self.assertEqual(item1["Item"]["data_celular"], "31345789")
        self.assertEqual(item1["Item"]["data_estatura"], "175")
        self.assertEqual(item1["Item"]["sourceFile"], "federacionArroz.txt")

        # Record 2: doc=11023341, nombre=opus
        item2 = table.get_item(Key={"partitionKey": "11023341", "sortKey": "opus"})
        self.assertIn("Item", item2)
        self.assertEqual(item2["Item"]["data_nombre"], "opus")
        self.assertEqual(item2["Item"]["data_ciudad"], "bogota")
        self.assertEqual(item2["Item"]["data_celular"], "31345787")

    def test_ingest_arroz_file_renamed(self):
        """Should rename file to .ingested after processing."""
        self.index.lambda_handler(self._get_event(), None)

        # Original file should be gone, .ingested should exist
        self.assertFalse(self.s3_key_exists("federacionArroz.txt"))
        self.assertTrue(self.s3_key_exists("federacionArroz.txt.ingested"))


# ============================================================
# Tests: Ingestion federacionCafetera.csv (semicolon-separated)
# sortKey=nombre means the value of column "nombre" is used as DynamoDB sortKey
# ============================================================

class TestIngesterFederacionCafeteraSemicolon(BaseLambdaTest):
    """Test ingestion of federacionCafetera.csv (semicolon-separated, partitionKey=documento, sortKey=nombre)."""

    def _get_event(self):
        return {
            "config": [
                {
                    "table": DYNAMODB_TABLE,
                    "partitionKey": "documento",
                    "sortKey": "nombre",
                    "file": "federacionCafetera.csv",
                    "ignore": False,
                }
            ]
        }

    def test_ingest_cafetera_csv_success(self):
        """Should ingest semicolon-separated CSV successfully."""
        response = self.index.lambda_handler(self._get_event(), None)

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["results"][0]["status"], "completed")
        self.assertEqual(body["results"][0]["success_count"], 2)
        self.assertEqual(body["results"][0]["error_count"], 0)

    def test_ingest_cafetera_csv_dynamodb_records(self):
        """Should correctly parse semicolon-separated data into DynamoDB."""
        self.index.lambda_handler(self._get_event(), None)

        table = self.dynamodb.Table(DYNAMODB_TABLE)

        # Record 1: documento=11023345, nombre=claude
        item1 = table.get_item(Key={"partitionKey": "11023345", "sortKey": "claude"})
        self.assertIn("Item", item1)
        self.assertEqual(item1["Item"]["data_nombre"], "claude")
        self.assertEqual(item1["Item"]["data_fecha"], "3/10/2026")
        self.assertEqual(item1["Item"]["data_edad"], "2")

        # Record 2: documento=11023341, nombre=opus
        item2 = table.get_item(Key={"partitionKey": "11023341", "sortKey": "opus"})
        self.assertIn("Item", item2)
        self.assertEqual(item2["Item"]["data_nombre"], "opus")
        self.assertEqual(item2["Item"]["data_fecha"], "3/11/2026")


# ============================================================
# Tests: Ingestion federacionCafetera.txt (comma-separated)
# ============================================================

class TestIngesterFederacionCafeteraComma(BaseLambdaTest):
    """Test ingestion of federacionCafetera.txt (comma-separated, partitionKey=documento, sortKey=fecha)."""

    def _get_event(self):
        return {
            "config": [
                {
                    "table": DYNAMODB_TABLE,
                    "partitionKey": "documento",
                    "sortKey": "fecha",
                    "file": "federacionCafetera.txt",
                    "ignore": False,
                }
            ]
        }

    def test_ingest_cafetera_txt_success(self):
        """Should ingest comma-separated TXT successfully."""
        response = self.index.lambda_handler(self._get_event(), None)

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["results"][0]["status"], "completed")
        self.assertEqual(body["results"][0]["success_count"], 2)

    def test_ingest_cafetera_txt_dynamodb_records(self):
        """Should correctly parse comma-separated TXT into DynamoDB."""
        self.index.lambda_handler(self._get_event(), None)

        table = self.dynamodb.Table(DYNAMODB_TABLE)

        # sortKey is the value of "fecha" column
        item1 = table.get_item(Key={"partitionKey": "11023345", "sortKey": "2026/10/03"})
        self.assertIn("Item", item1)
        self.assertEqual(item1["Item"]["data_nombre"], "claude")
        self.assertEqual(item1["Item"]["data_fecha"], "2026/10/03")

        item2 = table.get_item(Key={"partitionKey": "11023341", "sortKey": "2026/11/03"})
        self.assertIn("Item", item2)
        self.assertEqual(item2["Item"]["data_nombre"], "opus")


# ============================================================
# Tests: Edge Cases and Error Handling
# ============================================================

class TestIngesterEdgeCases(BaseLambdaTest):
    """Test edge cases and error handling."""

    def test_empty_config_returns_400(self):
        """Should return 400 when config array is empty."""
        event = {"config": []}
        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 400)
        body = json.loads(response["body"])
        self.assertIn("error", body)

    def test_missing_config_returns_400(self):
        """Should return 400 when config key is missing."""
        event = {}
        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 400)

    def test_ignore_flag_skips_file(self):
        """Should skip files with ignore=True."""
        event = {
            "config": [
                {
                    "table": DYNAMODB_TABLE,
                    "partitionKey": "doc",
                    "sortKey": "nombre",
                    "file": "federacionArroz.txt",
                    "ignore": True,
                }
            ]
        }

        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(len(body["results"]), 0)

    def test_invalid_partition_key_column(self):
        """Should return error when partitionKey column doesn't exist in file."""
        event = {
            "config": [
                {
                    "table": DYNAMODB_TABLE,
                    "partitionKey": "columna_inexistente",
                    "sortKey": "nombre",
                    "file": "federacionArroz.txt",
                    "ignore": False,
                }
            ]
        }

        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["results"][0]["status"], "error")
        self.assertIn("not found", body["results"][0]["error"].lower())

    def test_invalid_sort_key_column(self):
        """Should use sortKey as fixed value when it doesn't match any column."""
        event = {
            "config": [
                {
                    "table": DYNAMODB_TABLE,
                    "partitionKey": "doc",
                    "sortKey": "fedearroz",
                    "file": "federacionArroz.txt",
                    "ignore": False,
                }
            ]
        }

        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["results"][0]["status"], "completed")
        self.assertEqual(body["results"][0]["success_count"], 2)

        # All records should have the fixed sortKey value
        table = self.dynamodb.Table(DYNAMODB_TABLE)
        item1 = table.get_item(Key={"partitionKey": "11023345", "sortKey": "fedearroz"})
        self.assertIn("Item", item1)
        item2 = table.get_item(Key={"partitionKey": "11023341", "sortKey": "fedearroz"})
        self.assertIn("Item", item2)

    def test_already_ingested_file_skipped(self):
        """Should skip files that already have .ingested suffix."""
        self.upload_test_file("already_done.csv.ingested", "doc,name\n123,test\n")

        event = {
            "config": [
                {
                    "table": DYNAMODB_TABLE,
                    "partitionKey": "doc",
                    "file": "already_done.csv.ingested",
                    "ignore": False,
                }
            ]
        }

        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["results"][0]["status"], "skipped")

    def test_multiple_files_in_single_invocation(self):
        """Should process multiple files in a single lambda invocation."""
        event = {
            "config": [
                {
                    "table": DYNAMODB_TABLE,
                    "partitionKey": "doc",
                    "sortKey": "nombre",
                    "file": "federacionArroz.txt",
                    "ignore": False,
                },
                {
                    "table": DYNAMODB_TABLE,
                    "partitionKey": "documento",
                    "sortKey": "nombre",
                    "file": "federacionCafetera.txt",
                    "ignore": False,
                },
            ]
        }

        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(len(body["results"]), 2)
        self.assertEqual(body["results"][0]["status"], "completed")
        self.assertEqual(body["results"][1]["status"], "completed")
        self.assertEqual(body["results"][0]["success_count"], 2)
        self.assertEqual(body["results"][1]["success_count"], 2)

    def test_sort_key_uses_row_index_when_not_specified(self):
        """Should use row index as sortKey when sortKey is not in config."""
        event = {
            "config": [
                {
                    "table": DYNAMODB_TABLE,
                    "partitionKey": "doc",
                    "file": "federacionArroz.txt",
                    "ignore": False,
                }
            ]
        }

        self.index.lambda_handler(event, None)

        table = self.dynamodb.Table(DYNAMODB_TABLE)

        # Should use row index "1" and "2" as sort keys
        item1 = table.get_item(Key={"partitionKey": "11023345", "sortKey": "1"})
        self.assertIn("Item", item1)
        self.assertEqual(item1["Item"]["data_nombre"], "claude")

        item2 = table.get_item(Key={"partitionKey": "11023341", "sortKey": "2"})
        self.assertIn("Item", item2)
        self.assertEqual(item2["Item"]["data_nombre"], "opus")

    def test_records_have_metadata_fields(self):
        """Should include metadata fields (createdAt, sourceFile, rowIndex, status)."""
        event = {
            "config": [
                {
                    "table": DYNAMODB_TABLE,
                    "partitionKey": "doc",
                    "sortKey": "nombre",
                    "file": "federacionArroz.txt",
                    "ignore": False,
                }
            ]
        }

        self.index.lambda_handler(event, None)

        table = self.dynamodb.Table(DYNAMODB_TABLE)
        # partitionKey=11023345, sortKey=claude (value of "nombre" column)
        item = table.get_item(Key={"partitionKey": "11023345", "sortKey": "claude"})

        self.assertIn("Item", item)
        self.assertIn("createdAt", item["Item"])
        self.assertEqual(item["Item"]["sourceFile"], "federacionArroz.txt")
        self.assertEqual(item["Item"]["rowIndex"], 1)
        self.assertEqual(item["Item"]["status"], "active")


# ============================================================
# Tests: Error Records Handling
# ============================================================

class TestErrorRecords(BaseLambdaTest):
    """Test error handling for records with missing partition keys."""

    def test_missing_partition_key_value_creates_error(self):
        """Records with empty partition key should be counted as errors."""
        bad_data = "doc,nombre,edad\n,sin_doc,25\n11023345,con_doc,30\n"
        self.upload_test_file("bad_data.csv", bad_data)

        event = {
            "config": [
                {
                    "table": DYNAMODB_TABLE,
                    "partitionKey": "doc",
                    "sortKey": "nombre",
                    "file": "bad_data.csv",
                    "ignore": False,
                }
            ]
        }

        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["results"][0]["success_count"], 1)
        self.assertEqual(body["results"][0]["error_count"], 1)

    def test_error_file_created_in_s3(self):
        """Should create .failed.txt file in S3 when errors occur."""
        bad_data = "doc,nombre,edad\n,sin_doc,25\n11023345,con_doc,30\n"
        self.upload_test_file("errors_test.csv", bad_data)

        event = {
            "config": [
                {
                    "table": DYNAMODB_TABLE,
                    "partitionKey": "doc",
                    "sortKey": "nombre",
                    "file": "errors_test.csv",
                    "ignore": False,
                }
            ]
        }

        self.index.lambda_handler(event, None)

        # Check that .failed.txt file was created in our store
        self.assertTrue(self.s3_key_exists("errors_test.csv.failed.txt"))

        # Verify content of failed file
        failed_content = self._s3_store["errors_test.csv.failed.txt"].decode("utf-8")
        self.assertIn("error_reason", failed_content)
        self.assertIn("sin_doc", failed_content)


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    unittest.main()

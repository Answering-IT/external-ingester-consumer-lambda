"""
Test Suite: Consumer Lambda Function
=====================================
Tests the consumer lambda that queries DynamoDB records via API Gateway.

Uses moto to mock AWS services (DynamoDB) for local testing.

Run: pip install moto boto3
     python -m unittest tests.consumer-lambda-suite -v
"""

import unittest
import json
import os
import sys
import boto3
from unittest.mock import patch
from moto import mock_aws
from decimal import Decimal

# Add lambda path to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'infrastructure', 'lambdas', 'consumer'))

# ============================================================
# Constants
# ============================================================

DYNAMODB_TABLE = "Dev-ExternalData"
STAGE = "dev"

ENV_VARS = {
    "DYNAMODB_TABLE": DYNAMODB_TABLE,
    "STAGE": STAGE,
}


# ============================================================
# Base Test Class
# ============================================================

class BaseConsumerTest(unittest.TestCase):
    """Base class that sets up mocked AWS environment."""

    def setUp(self):
        """Set up mocked AWS services before each test."""
        self.env_patcher = patch.dict(os.environ, ENV_VARS)
        self.env_patcher.start()

        self.mock_aws = mock_aws()
        self.mock_aws.start()

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

    def tearDown(self):
        """Clean up mocks after each test."""
        self.mock_aws.stop()
        self.env_patcher.stop()
        if "index" in sys.modules:
            del sys.modules["index"]

    def create_test_record(self, partition_key, sort_key, **additional_data):
        """Helper to create a test record in DynamoDB."""
        item = {
            "partitionKey": partition_key,
            "sortKey": sort_key,
            "createdAt": "2026-05-08T12:00:00.000Z",
            "sourceFile": "test_file.csv",
            "rowIndex": 1,
            "status": "active",
            **additional_data
        }
        self.table.put_item(Item=item)
        return item

    def make_api_gateway_event(self, partition_key, sort_key):
        """Helper to create an API Gateway event."""
        return {
            "pathParameters": {
                "partitionKey": partition_key,
                "sortKey": sort_key
            },
            "requestContext": {
                "requestId": "test-request-id",
                "stage": STAGE
            }
        }


# ============================================================
# Tests: Successful Record Retrieval
# ============================================================

class TestConsumerSuccess(BaseConsumerTest):
    """Tests for successful record retrieval."""

    def test_get_existing_record(self):
        """Should return 200 and record data when record exists."""
        # Create test record
        self.create_test_record(
            "11023345",
            "claude",
            data_nombre="claude",
            data_edad="2",
            data_ciudad="santa marta"
        )

        # Make request
        event = self.make_api_gateway_event("11023345", "claude")
        response = self.index.lambda_handler(event, None)

        # Assertions
        self.assertEqual(response["statusCode"], 200)
        self.assertIn("Content-Type", response["headers"])
        self.assertEqual(response["headers"]["Content-Type"], "application/json")

        body = json.loads(response["body"])
        self.assertEqual(body["status"], "success")
        self.assertIn("data", body)
        self.assertEqual(body["data"]["partitionKey"], "11023345")
        self.assertEqual(body["data"]["sortKey"], "claude")
        self.assertEqual(body["data"]["data_nombre"], "claude")
        self.assertEqual(body["data"]["data_ciudad"], "santa marta")

    def test_cors_headers_present(self):
        """Should include CORS headers in response."""
        self.create_test_record("123", "test")

        event = self.make_api_gateway_event("123", "test")
        response = self.index.lambda_handler(event, None)

        headers = response["headers"]
        self.assertIn("Access-Control-Allow-Origin", headers)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")
        self.assertIn("Access-Control-Allow-Headers", headers)
        self.assertIn("Access-Control-Allow-Methods", headers)

    def test_metadata_fields_included(self):
        """Should include metadata fields in response (createdAt, sourceFile, etc.)."""
        self.create_test_record(
            "11023345",
            "claude",
            createdAt="2026-05-08T10:30:00.000Z",
            sourceFile="federacionArroz.txt",
            rowIndex=5,
            status="active"
        )

        event = self.make_api_gateway_event("11023345", "claude")
        response = self.index.lambda_handler(event, None)

        body = json.loads(response["body"])
        data = body["data"]
        self.assertEqual(data["createdAt"], "2026-05-08T10:30:00.000Z")
        self.assertEqual(data["sourceFile"], "federacionArroz.txt")
        self.assertEqual(data["rowIndex"], 5)
        self.assertEqual(data["status"], "active")


# ============================================================
# Tests: Record Not Found (404)
# ============================================================

class TestConsumerNotFound(BaseConsumerTest):
    """Tests for 404 scenarios."""

    def test_record_not_found(self):
        """Should return 404 when record doesn't exist."""
        event = self.make_api_gateway_event("nonexistent", "key")
        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 404)
        body = json.loads(response["body"])
        self.assertEqual(body["status"], "not_found")
        self.assertIn("error", body)
        self.assertIn("query", body)
        self.assertEqual(body["query"]["partitionKey"], "nonexistent")
        self.assertEqual(body["query"]["sortKey"], "key")

    def test_wrong_partition_key(self):
        """Should return 404 when partitionKey is wrong."""
        self.create_test_record("11023345", "claude")

        event = self.make_api_gateway_event("99999999", "claude")
        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 404)
        body = json.loads(response["body"])
        self.assertEqual(body["status"], "not_found")

    def test_wrong_sort_key(self):
        """Should return 404 when sortKey is wrong."""
        self.create_test_record("11023345", "claude")

        event = self.make_api_gateway_event("11023345", "wrong_sort_key")
        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 404)


# ============================================================
# Tests: Bad Request (400)
# ============================================================

class TestConsumerBadRequest(BaseConsumerTest):
    """Tests for 400 bad request scenarios."""

    def test_missing_path_parameters(self):
        """Should return 400 when pathParameters is missing."""
        event = {
            "requestContext": {
                "requestId": "test-request-id"
            }
        }
        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 400)
        body = json.loads(response["body"])
        self.assertEqual(body["status"], "bad_request")
        self.assertIn("error", body)

    def test_missing_partition_key(self):
        """Should return 400 when partitionKey is missing."""
        event = {
            "pathParameters": {
                "sortKey": "test"
            }
        }
        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 400)
        body = json.loads(response["body"])
        self.assertEqual(body["status"], "bad_request")
        self.assertIn("received", body)

    def test_missing_sort_key(self):
        """Should return 400 when sortKey is missing."""
        event = {
            "pathParameters": {
                "partitionKey": "test"
            }
        }
        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 400)
        body = json.loads(response["body"])
        self.assertEqual(body["status"], "bad_request")

    def test_empty_partition_key(self):
        """Should return 400 when partitionKey is empty string."""
        event = {
            "pathParameters": {
                "partitionKey": "",
                "sortKey": "test"
            }
        }
        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 400)
        body = json.loads(response["body"])
        self.assertEqual(body["status"], "bad_request")

    def test_empty_sort_key(self):
        """Should return 400 when sortKey is empty string."""
        event = {
            "pathParameters": {
                "partitionKey": "test",
                "sortKey": ""
            }
        }
        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 400)


# ============================================================
# Tests: Data Type Serialization
# ============================================================

class TestConsumerSerialization(BaseConsumerTest):
    """Tests for DynamoDB data type serialization."""

    def test_decimal_serialization(self):
        """Should serialize Decimal types to int or float."""
        # Create record with Decimal values
        item = {
            "partitionKey": "123",
            "sortKey": "test",
            "data_price": Decimal("99.99"),
            "data_quantity": Decimal("10"),
            "data_rate": Decimal("0.5")
        }
        self.table.put_item(Item=item)

        event = self.make_api_gateway_event("123", "test")
        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        data = body["data"]

        # Verify Decimal conversion
        self.assertEqual(data["data_price"], 99.99)
        self.assertEqual(data["data_quantity"], 10)  # Whole number → int
        self.assertEqual(data["data_rate"], 0.5)

    def test_nested_data_structures(self):
        """Should serialize nested dicts and lists properly."""
        item = {
            "partitionKey": "456",
            "sortKey": "nested",
            "data_metadata": {
                "tags": ["tag1", "tag2"],
                "counts": {"views": Decimal("100"), "likes": Decimal("25")}
            }
        }
        self.table.put_item(Item=item)

        event = self.make_api_gateway_event("456", "nested")
        response = self.index.lambda_handler(event, None)

        body = json.loads(response["body"])
        data = body["data"]
        self.assertIn("data_metadata", data)
        self.assertEqual(data["data_metadata"]["tags"], ["tag1", "tag2"])
        self.assertEqual(data["data_metadata"]["counts"]["views"], 100)
        self.assertEqual(data["data_metadata"]["counts"]["likes"], 25)


# ============================================================
# Tests: Different Data Scenarios
# ============================================================

class TestConsumerDataScenarios(BaseConsumerTest):
    """Tests for different data scenarios from ingestion."""

    def test_federacion_arroz_record(self):
        """Should retrieve record from federacionArroz.txt format."""
        self.create_test_record(
            "11023345",
            "claude",
            data_doc="11023345",
            data_nombre="claude",
            data_edad="2",
            data_estatura="175",
            data_ciudad="santa marta",
            data_celular="31345789",
            sourceFile="federacionArroz.txt"
        )

        event = self.make_api_gateway_event("11023345", "claude")
        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        data = body["data"]
        self.assertEqual(data["data_nombre"], "claude")
        self.assertEqual(data["data_ciudad"], "santa marta")
        self.assertEqual(data["data_celular"], "31345789")

    def test_federacion_cafetera_record(self):
        """Should retrieve record from federacionCafetera.csv format."""
        self.create_test_record(
            "11023345",
            "claude",
            data_documento="11023345",
            data_fecha="3/10/2026",
            data_nombre="claude",
            data_edad="2",
            sourceFile="federacionCafetera.csv"
        )

        event = self.make_api_gateway_event("11023345", "claude")
        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        data = body["data"]
        self.assertEqual(data["data_fecha"], "3/10/2026")
        self.assertEqual(data["data_nombre"], "claude")

    def test_fixed_sort_key_record(self):
        """Should retrieve records that use fixed sortKey value."""
        self.create_test_record(
            "11023345",
            "fedearroz",  # Fixed sortKey value
            data_doc="11023345",
            data_nombre="claude",
            sourceFile="federacionArroz.txt"
        )

        event = self.make_api_gateway_event("11023345", "fedearroz")
        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["data"]["sortKey"], "fedearroz")

    def test_row_index_as_sort_key(self):
        """Should retrieve records that use row index as sortKey."""
        self.create_test_record(
            "11023345",
            "1",  # Row index used as sortKey
            data_doc="11023345",
            data_nombre="claude",
            rowIndex=1
        )

        event = self.make_api_gateway_event("11023345", "1")
        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["data"]["sortKey"], "1")
        self.assertEqual(body["data"]["rowIndex"], 1)


# ============================================================
# Tests: Multiple Records with Same Partition Key
# ============================================================

class TestConsumerMultipleRecords(BaseConsumerTest):
    """Tests for querying when multiple records share the same partitionKey."""

    def test_different_sort_keys_same_partition(self):
        """Should correctly distinguish records with same partitionKey but different sortKeys."""
        # Create multiple records with same partition key
        self.create_test_record("11023345", "claude", data_nombre="claude")
        self.create_test_record("11023345", "opus", data_nombre="opus")
        self.create_test_record("11023345", "haiku", data_nombre="haiku")

        # Query each one
        event1 = self.make_api_gateway_event("11023345", "claude")
        response1 = self.index.lambda_handler(event1, None)
        body1 = json.loads(response1["body"])
        self.assertEqual(body1["data"]["data_nombre"], "claude")

        event2 = self.make_api_gateway_event("11023345", "opus")
        response2 = self.index.lambda_handler(event2, None)
        body2 = json.loads(response2["body"])
        self.assertEqual(body2["data"]["data_nombre"], "opus")

        event3 = self.make_api_gateway_event("11023345", "haiku")
        response3 = self.index.lambda_handler(event3, None)
        body3 = json.loads(response3["body"])
        self.assertEqual(body3["data"]["data_nombre"], "haiku")


# ============================================================
# Tests: Special Characters in Keys
# ============================================================

class TestConsumerSpecialCharacters(BaseConsumerTest):
    """Tests for special characters in partition/sort keys."""

    def test_special_characters_in_keys(self):
        """Should handle special characters in partition and sort keys."""
        # Create record with special chars
        self.create_test_record(
            "doc-123/456",
            "name@test.com",
            data_info="special chars"
        )

        event = self.make_api_gateway_event("doc-123/456", "name@test.com")
        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["data"]["partitionKey"], "doc-123/456")
        self.assertEqual(body["data"]["sortKey"], "name@test.com")

    def test_unicode_characters(self):
        """Should handle unicode characters in keys."""
        self.create_test_record(
            "11023345",
            "José García",
            data_nombre="José García",
            data_ciudad="Bogotá"
        )

        event = self.make_api_gateway_event("11023345", "José García")
        response = self.index.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["data"]["data_nombre"], "José García")
        self.assertEqual(body["data"]["data_ciudad"], "Bogotá")


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    unittest.main()

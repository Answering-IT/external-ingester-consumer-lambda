# Lambda Test Suites

Comprehensive integration tests for the Ingester and Consumer Lambda functions using moto mocks.

## Overview

These test suites use `moto` to mock AWS services (S3, DynamoDB) for local testing without requiring real AWS resources.

## Test Files

### 1. `ingester-lambda-suite.py` (28 tests)

Tests the ingester lambda (`infrastructure/lambdas/ingester/index.py`) that processes CSV/TXT files from S3 and writes to DynamoDB.

**Test Coverage:**
- ✅ Config validation (required fields, empty values)
- ✅ Delimiter auto-detection (comma, semicolon, tab, pipe)
- ✅ Successful ingestion scenarios
  - federacionArroz.txt (comma-separated)
  - federacionCafetera.csv (semicolon-separated)
  - federacionCafetera.txt (comma-separated)
- ✅ DynamoDB record verification
- ✅ File renaming (.ingested suffix)
- ✅ Edge cases
  - Empty/missing config
  - Ignore flag
  - Invalid partition/sort key columns
  - Fixed sortKey values
  - Row index as sortKey
  - Already ingested files
  - Multiple files in single invocation
  - Metadata fields
- ✅ Error handling
  - Missing partition key values
  - Error file creation (.failed.txt)

**Run:**
```bash
python3 -m unittest tests.ingester-lambda-suite -v
```

**Expected:** ✅ Ran 28 tests - OK

---

### 2. `consumer-lambda-suite.py` (20 tests)

Tests the consumer lambda (`infrastructure/lambdas/consumer/index.py`) that queries DynamoDB records via API Gateway.

**Test Coverage:**
- ✅ Successful record retrieval (200)
  - Get existing records
  - CORS headers
  - Metadata fields included
- ✅ Record not found scenarios (404)
  - Non-existent records
  - Wrong partition key
  - Wrong sort key
- ✅ Bad request scenarios (400)
  - Missing path parameters
  - Missing/empty partitionKey
  - Missing/empty sortKey
- ✅ Data serialization
  - Decimal type conversion (int/float)
  - Nested data structures
- ✅ Different data scenarios
  - federacionArroz.txt format
  - federacionCafetera.csv format
  - Fixed sortKey values
  - Row index as sortKey
- ✅ Multiple records with same partitionKey
- ✅ Special characters
  - Special characters in keys
  - Unicode characters

**Run:**
```bash
python3 -m unittest tests.consumer-lambda-suite -v
```

**Expected:** ✅ Ran 20 tests - OK

---

## Installation

### Requirements

```bash
pip3 install moto boto3
```

Or using the public PyPI (if corporate proxy blocks):
```bash
pip3 install moto --index-url https://pypi.org/simple
pip3 install boto3 --index-url https://pypi.org/simple
```

---

## Test Architecture

### Base Test Classes

Both suites use base test classes that handle mocking setup and teardown:

**`BaseLambdaTest`** (Ingester)
- Sets up mock S3 bucket with test files
- Creates mock DynamoDB table (dev-ExternalData)
- Patches S3 client methods for seekable streams
- Tracks file operations in memory

**`BaseConsumerTest`** (Consumer)
- Creates mock DynamoDB table (dev-ExternalData)
- Provides helpers for creating test records
- Generates API Gateway event payloads

### Mock Data

**Ingester Test Data:**
```python
# federacionArroz.txt (comma-separated)
"doc,nombre,edad,estatura,ciudad,celular\n"
"11023345,claude,2,175,santa marta,31345789\n"
"11023341,opus,3,174,bogota,31345787\n"

# federacionCafetera.csv (semicolon-separated)
"documento;fecha;nombre;edad\n"
"11023345;3/10/2026;claude;2\n"
"11023341;3/11/2026;opus;3\n"

# federacionCafetera.txt (comma-separated)
"documento,fecha,nombre,edad\n"
"11023345,2026/10/03,claude,2\n"
"11023341,2026/11/03,opus,3\n"
```

**Consumer Test Data:**
- Creates DynamoDB records programmatically
- Tests various partition/sort key combinations
- Validates API Gateway response format

---

## Running Tests

### Individual Test Suite

```bash
# Run ingester tests only
python3 -m unittest tests.ingester-lambda-suite -v

# Run consumer tests only
python3 -m unittest tests.consumer-lambda-suite -v
```

### Specific Test Class

```bash
# Run specific test class
python3 -m unittest tests.ingester-lambda-suite.TestIngesterFederacionArroz -v
```

### Specific Test Method

```bash
# Run single test
python3 -m unittest tests.ingester-lambda-suite.TestIngesterFederacionArroz.test_ingest_arroz_success -v
```

### Run Both Suites (Sequential)

```bash
# Run separately (recommended due to moto mock state)
python3 -m unittest tests.ingester-lambda-suite && \
python3 -m unittest tests.consumer-lambda-suite
```

---

## Test Results Summary

| Suite | Tests | Status |
|-------|-------|--------|
| **Ingester Lambda** | 28 | ✅ OK |
| **Consumer Lambda** | 20 | ✅ OK |
| **Total** | 48 | ✅ OK |

---

## Key Test Scenarios

### Ingester Lambda

1. **Config Validation**: Ensures required fields (table, partitionKey, file) are present
2. **Delimiter Detection**: Auto-detects CSV delimiters from file headers
3. **Data Ingestion**: Processes files and writes to DynamoDB with proper keys
4. **sortKey Modes**:
   - Column value (e.g., `sortKey="nombre"` uses value from "nombre" column)
   - Fixed value (e.g., `sortKey="fedearroz"` uses literal value for all records)
   - Row index (when sortKey not specified, uses "1", "2", "3"...)
5. **File Management**: Renames processed files with `.ingested` suffix
6. **Error Handling**: Creates `.failed.txt` files for records with errors

### Consumer Lambda

1. **API Gateway Integration**: Handles pathParameters from API Gateway events
2. **DynamoDB Queries**: Retrieves records by partitionKey + sortKey
3. **HTTP Status Codes**:
   - 200: Record found
   - 404: Record not found
   - 400: Bad request (missing/invalid parameters)
   - 500: Internal server error
4. **CORS Headers**: Includes Access-Control-* headers for cross-origin requests
5. **Data Serialization**: Converts DynamoDB types (Decimal) to JSON-compatible types

---

## Environment Variables

Both test suites mock these environment variables:

**Ingester:**
```python
S3_BUCKET = "dev-answering-procesapp-info"
DYNAMODB_TABLE = "dev-ExternalData"
STAGE = "dev"
KMS_KEY_ID = "test-kms-key-id"
BATCH_SIZE = "25"
MAX_RETRIES = "3"
```

**Consumer:**
```python
DYNAMODB_TABLE = "dev-ExternalData"
STAGE = "dev"
```

---

## Troubleshooting

### ModuleNotFoundError: No module named 'moto'

**Solution:** Install moto:
```bash
pip3 install moto boto3
```

### Tests Fail When Run Together

**Issue:** Moto mock state persists across test modules

**Solution:** Run test suites separately:
```bash
python3 -m unittest tests.ingester-lambda-suite
python3 -m unittest tests.consumer-lambda-suite
```

### Import Errors for Lambda Modules

**Issue:** Lambda modules not in Python path

**Solution:** Test suites automatically add lambda directories to `sys.path`:
```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'infrastructure', 'lambdas', 'ingester'))
```

---

## Test Data Files

### Ingester Tests

The ingester tests load actual files from `tests/resources/`:
- `federacionArroz.txt` (comma-separated)
- `federacionCafetera.csv` (semicolon-separated, with UTF-8 BOM)
- `federacionCafetera.txt` (comma-separated)

Files are loaded using `utf-8-sig` encoding to handle UTF-8 BOM (Byte Order Mark) if present.

### Consumer Tests

The consumer tests create DynamoDB records programmatically (no external files needed).

---

## CI/CD Integration

To integrate these tests into CI/CD:

```yaml
# Example GitHub Actions workflow
- name: Install dependencies
  run: pip3 install moto boto3

- name: Run Ingester Tests
  run: python3 -m unittest tests.ingester-lambda-suite -v

- name: Run Consumer Tests
  run: python3 -m unittest tests.consumer-lambda-suite -v
```

---

## Contributing

When adding new tests:

1. Inherit from `BaseLambdaTest` or `BaseConsumerTest`
2. Follow naming convention: `test_<scenario>_<expected_result>`
3. Add docstrings describing what the test validates
4. Group related tests in test classes
5. Update this README with new test coverage

---

## License

Internal use - Answering IT

---

**Last Updated:** 2026-05-08

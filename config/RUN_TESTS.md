# Running Tests Locally

## Setup

### 1. Install Python dependencies
```bash
pip install -r infrastructure/lambdas/ingester/requirements.txt
pip install -r infrastructure/lambdas/consumer/requirements.txt
pip install moto boto3
```

### 2. Set AWS region (required for boto3)
```bash
export AWS_DEFAULT_REGION=us-east-1
```

## Run All Tests

### Option 1: Run both test suites
```bash
python3 -m unittest tests.consumer-lambda-suite -v
python3 -m unittest tests.ingester-lambda-suite -v
```

### Option 2: Run from tests directory
```bash
cd tests
python3 consumer-lambda-suite.py -v
python3 ingester-lambda-suite.py -v
```

## Run Specific Tests

### Run specific test class
```bash
python3 -m unittest tests.consumer-lambda-suite.TestConsumerSuccess -v
```

### Run specific test method
```bash
python3 -m unittest tests.consumer-lambda-suite.TestConsumerSuccess.test_get_existing_record -v
```

## Common Issues

### NoRegionError
If you get `botocore.exceptions.NoRegionError: You must specify a region.`, set the AWS region:
```bash
export AWS_DEFAULT_REGION=us-east-1
```

### ModuleNotFoundError
If you get import errors, make sure you're running from the project root:
```bash
cd /Users/qohatpretel/Answering/external-ingester-consumer-lambda
```

### AWS Credentials Warning
Tests use moto to mock AWS services, so you don't need real AWS credentials.

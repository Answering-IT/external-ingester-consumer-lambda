/**
 * IAM Policy configuration helpers for Lambda functions
 */

import * as iam from 'aws-cdk-lib/aws-iam';

/**
 * Get IAM policy for Ingester Lambda
 * Permissions: S3 (read/write), DynamoDB (write), KMS (encrypt/decrypt)
 */
export function getIngesterLambdaPolicy(
  s3BucketArn: string,
  dynamodbTableArn: string,
  kmsKeyArn: string,
  region: string,
  accountId: string
): iam.PolicyDocument {
  const statements = [
    // S3 Permissions: Read source files, write .ingested and .failed.txt
    new iam.PolicyStatement({
      sid: 'AccessS3Bucket',
      effect: iam.Effect.ALLOW,
      actions: [
        's3:GetObject',
        's3:GetObjectVersion',
        's3:PutObject',
        's3:DeleteObject',
        's3:ListBucket',
      ],
      resources: [
        s3BucketArn,
        `${s3BucketArn}/*`,
      ],
    }),

    // DynamoDB Permissions: Write items in batches
    new iam.PolicyStatement({
      sid: 'WriteToDynamoDB',
      effect: iam.Effect.ALLOW,
      actions: [
        'dynamodb:PutItem',
        'dynamodb:BatchWriteItem',
        'dynamodb:UpdateItem',
      ],
      resources: [dynamodbTableArn],
    }),

    // KMS Permissions: Encrypt/decrypt data
    new iam.PolicyStatement({
      sid: 'EncryptDecryptWithKMS',
      effect: iam.Effect.ALLOW,
      actions: [
        'kms:Decrypt',
        'kms:Encrypt',
        'kms:GenerateDataKey',
        'kms:DescribeKey',
      ],
      resources: [kmsKeyArn],
    }),

    // CloudWatch Logs: Write logs
    new iam.PolicyStatement({
      sid: 'WriteCloudWatchLogs',
      effect: iam.Effect.ALLOW,
      actions: [
        'logs:CreateLogGroup',
        'logs:CreateLogStream',
        'logs:PutLogEvents',
      ],
      resources: [
        `arn:aws:logs:${region}:${accountId}:log-group:/aws/lambda/*`,
      ],
    }),

    // X-Ray: Distributed tracing
    new iam.PolicyStatement({
      sid: 'WriteXRayTraces',
      effect: iam.Effect.ALLOW,
      actions: [
        'xray:PutTraceSegments',
        'xray:PutTelemetryRecords',
      ],
      resources: ['*'],
    }),
  ];

  return new iam.PolicyDocument({ statements });
}

/**
 * Get IAM policy for Consumer Lambda
 * Permissions: DynamoDB (read), KMS (decrypt)
 */
export function getConsumerLambdaPolicy(
  dynamodbTableArn: string,
  kmsKeyArn: string,
  region: string,
  accountId: string
): iam.PolicyDocument {
  const statements = [
    // DynamoDB Permissions: Read items
    new iam.PolicyStatement({
      sid: 'ReadFromDynamoDB',
      effect: iam.Effect.ALLOW,
      actions: [
        'dynamodb:GetItem',
        'dynamodb:Query',
        'dynamodb:Scan',
      ],
      resources: [
        dynamodbTableArn,
        `${dynamodbTableArn}/index/*`,
      ],
    }),

    // KMS Permissions: Decrypt data
    new iam.PolicyStatement({
      sid: 'DecryptWithKMS',
      effect: iam.Effect.ALLOW,
      actions: [
        'kms:Decrypt',
        'kms:DescribeKey',
      ],
      resources: [kmsKeyArn],
    }),

    // CloudWatch Logs: Write logs
    new iam.PolicyStatement({
      sid: 'WriteCloudWatchLogs',
      effect: iam.Effect.ALLOW,
      actions: [
        'logs:CreateLogGroup',
        'logs:CreateLogStream',
        'logs:PutLogEvents',
      ],
      resources: [
        `arn:aws:logs:${region}:${accountId}:log-group:/aws/lambda/*`,
      ],
    }),

    // X-Ray: Distributed tracing
    new iam.PolicyStatement({
      sid: 'WriteXRayTraces',
      effect: iam.Effect.ALLOW,
      actions: [
        'xray:PutTraceSegments',
        'xray:PutTelemetryRecords',
      ],
      resources: ['*'],
    }),
  ];

  return new iam.PolicyDocument({ statements });
}

/**
 * Get KMS key policy statements
 */
export function getKMSKeyPolicyStatements(
  accountId: string,
  region: string
): iam.PolicyStatement[] {
  return [
    // Allow account root to manage key
    new iam.PolicyStatement({
      sid: 'EnableIAMUserPermissions',
      effect: iam.Effect.ALLOW,
      principals: [new iam.AccountRootPrincipal()],
      actions: ['kms:*'],
      resources: ['*'],
    }),

    // Allow Lambda service to use key
    new iam.PolicyStatement({
      sid: 'AllowLambdaServiceToUseKey',
      effect: iam.Effect.ALLOW,
      principals: [new iam.ServicePrincipal('lambda.amazonaws.com')],
      actions: [
        'kms:Decrypt',
        'kms:Encrypt',
        'kms:GenerateDataKey',
        'kms:DescribeKey',
      ],
      resources: ['*'],
      conditions: {
        StringEquals: {
          'kms:ViaService': [
            `dynamodb.${region}.amazonaws.com`,
            `s3.${region}.amazonaws.com`,
          ],
        },
      },
    }),

    // Allow DynamoDB service to use key
    new iam.PolicyStatement({
      sid: 'AllowDynamoDBToUseKey',
      effect: iam.Effect.ALLOW,
      principals: [new iam.ServicePrincipal('dynamodb.amazonaws.com')],
      actions: [
        'kms:Decrypt',
        'kms:Encrypt',
        'kms:GenerateDataKey',
        'kms:CreateGrant',
        'kms:DescribeKey',
      ],
      resources: ['*'],
      conditions: {
        StringEquals: {
          'kms:ViaService': `dynamodb.${region}.amazonaws.com`,
        },
      },
    }),

    // Allow IAM users to decrypt DynamoDB data from console
    new iam.PolicyStatement({
      sid: 'AllowIAMUsersToDecryptDynamoDB',
      effect: iam.Effect.ALLOW,
      principals: [new iam.AccountRootPrincipal()],
      actions: [
        'kms:Decrypt',
        'kms:DescribeKey',
      ],
      resources: ['*'],
      conditions: {
        StringEquals: {
          'kms:ViaService': `dynamodb.${region}.amazonaws.com`,
        },
      },
    }),
  ];
}

/**
 * Get IAM policy document for DynamoDB console read access
 * This can be attached to users/groups to allow read-only access from console
 */
export function getDynamoDBReadOnlyPolicy(
  dynamodbTableArn: string,
  kmsKeyArn: string,
  _region: string
): iam.PolicyDocument {
  const statements = [
    // DynamoDB Permissions: Read, Scan, Query
    new iam.PolicyStatement({
      sid: 'ReadDynamoDBTable',
      effect: iam.Effect.ALLOW,
      actions: [
        'dynamodb:DescribeTable',
        'dynamodb:GetItem',
        'dynamodb:Query',
        'dynamodb:Scan',
        'dynamodb:DescribeTimeToLive',
        'dynamodb:ListTables',
      ],
      resources: [
        dynamodbTableArn,
        `${dynamodbTableArn}/index/*`,
      ],
    }),

    // KMS Permissions: Decrypt to read encrypted data
    new iam.PolicyStatement({
      sid: 'DecryptKMSKey',
      effect: iam.Effect.ALLOW,
      actions: [
        'kms:Decrypt',
        'kms:DescribeKey',
      ],
      resources: [kmsKeyArn],
    }),

    // Allow listing DynamoDB tables in console
    new iam.PolicyStatement({
      sid: 'ListDynamoDBTables',
      effect: iam.Effect.ALLOW,
      actions: [
        'dynamodb:ListTables',
      ],
      resources: ['*'],
    }),
  ];

  return new iam.PolicyDocument({ statements });
}

/**
 * Get IAM policy document for DynamoDB console read-write access
 * This can be attached to users/groups to allow full access from console
 */
export function getDynamoDBReadWritePolicy(
  dynamodbTableArn: string,
  kmsKeyArn: string,
  _region: string
): iam.PolicyDocument {
  const statements = [
    // DynamoDB Permissions: Full CRUD operations
    new iam.PolicyStatement({
      sid: 'ReadWriteDynamoDBTable',
      effect: iam.Effect.ALLOW,
      actions: [
        // Read operations
        'dynamodb:DescribeTable',
        'dynamodb:GetItem',
        'dynamodb:Query',
        'dynamodb:Scan',
        'dynamodb:DescribeTimeToLive',
        // Write operations
        'dynamodb:PutItem',
        'dynamodb:UpdateItem',
        'dynamodb:DeleteItem',
        'dynamodb:BatchWriteItem',
        'dynamodb:BatchGetItem',
      ],
      resources: [
        dynamodbTableArn,
        `${dynamodbTableArn}/index/*`,
      ],
    }),

    // KMS Permissions: Encrypt and Decrypt
    new iam.PolicyStatement({
      sid: 'EncryptDecryptKMSKey',
      effect: iam.Effect.ALLOW,
      actions: [
        'kms:Decrypt',
        'kms:Encrypt',
        'kms:GenerateDataKey',
        'kms:DescribeKey',
      ],
      resources: [kmsKeyArn],
    }),

    // Allow listing DynamoDB tables in console
    new iam.PolicyStatement({
      sid: 'ListDynamoDBTables',
      effect: iam.Effect.ALLOW,
      actions: [
        'dynamodb:ListTables',
      ],
      resources: ['*'],
    }),
  ];

  return new iam.PolicyDocument({ statements });
}

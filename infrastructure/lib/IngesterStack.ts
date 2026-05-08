/**
 * Ingester Stack: Lambda function for streaming CSV ingestion from S3 to DynamoDB
 */

import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';
import * as path from 'path';
import { EnvironmentConfig, getLambdaFunctionName, getCostAllocationTags } from '../config/environments';

export interface IngesterStackProps extends cdk.StackProps {
  config: EnvironmentConfig;
  kmsKey: kms.IKey;
  s3Bucket: s3.IBucket;
  ingesterRole: iam.IRole;
}

export class IngesterStack extends cdk.Stack {
  public readonly ingesterFunction: lambda.Function;

  constructor(scope: Construct, id: string, props: IngesterStackProps) {
    super(scope, id, props);

    const { config, kmsKey, s3Bucket, ingesterRole } = props;
    const functionName = getLambdaFunctionName(config.stage, 'ingester');

    // Ingester Lambda Function
    this.ingesterFunction = new lambda.Function(this, 'IngesterFunction', {
      functionName: functionName,
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.lambda_handler',
      code: lambda.Code.fromAsset(
        path.join(__dirname, '../lambdas/ingester')
      ),
      role: ingesterRole,
      timeout: cdk.Duration.seconds(config.lambdas.ingester.timeoutSeconds),
      memorySize: config.lambdas.ingester.memoryMB,
      ephemeralStorageSize: cdk.Size.mebibytes(config.lambdas.ingester.ephemeralStorageMB),
      reservedConcurrentExecutions: config.lambdas.ingester.reservedConcurrency,
      environment: {
        S3_BUCKET: s3Bucket.bucketName,
        STAGE: config.stage,
        KMS_KEY_ID: kmsKey.keyId,
        BATCH_SIZE: config.processing.batchSize.toString(),
        MAX_RETRIES: config.processing.maxRetries.toString(),
      },
      description: `Ingester Lambda for external data (${config.stage}) - Streaming CSV processing`,
      tracing: lambda.Tracing.ACTIVE,
    });

    // Grant invoke permissions to specific IAM users using their ARNs
    const allowedUserArns = [
      'arn:aws:iam::708819485463:user/qohat.prettel',
      'arn:aws:iam::708819485463:user/david.jimenez',
      'arn:aws:iam::708819485463:user/soportejoven@answering.com.co',
    ];

    allowedUserArns.forEach((userArn, index) => {
      const user = iam.User.fromUserArn(this, `AllowedUser${index}`, userArn);
      this.ingesterFunction.grantInvoke(user);
    });

    // Apply cost allocation tags
    const tags = getCostAllocationTags(config.stage);
    Object.entries(tags).forEach(([key, value]) => {
      cdk.Tags.of(this).add(key, value);
    });

    // Stack outputs
    new cdk.CfnOutput(this, 'IngesterFunctionName', {
      value: this.ingesterFunction.functionName,
      description: 'Ingester Lambda function name',
      exportName: `${config.stage}-IngesterFunctionName`,
    });

    new cdk.CfnOutput(this, 'IngesterFunctionArn', {
      value: this.ingesterFunction.functionArn,
      description: 'Ingester Lambda function ARN',
      exportName: `${config.stage}-IngesterFunctionArn`,
    });

    new cdk.CfnOutput(this, 'InvocationCommand', {
      value: `aws lambda invoke --function-name ${functionName} --payload '{"config": [{"table": "dev-tableName", "partitionKey": "YOUR_PARTITION_KEY_COLUMN", "sortKey": "YOUR_SORT_KEY_VALUE", "file": "YOUR_FILE.csv", "ignore": false}]}' --profile ${config.profile} response.json`,
      description: 'AWS CLI command to invoke ingester',
    });
  }
}

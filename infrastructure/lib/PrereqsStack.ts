/**
 * Prerequisites Stack: DynamoDB table, KMS key, IAM roles
 */

import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';
import { EnvironmentConfig, getTableName, getCostAllocationTags } from '../config/environments';
import {
  getIngesterLambdaPolicy,
  getConsumerLambdaPolicy,
  getKMSKeyPolicyStatements,
} from '../config/security.config';

export interface PrereqsStackProps extends cdk.StackProps {
  config: EnvironmentConfig;
}

export class PrereqsStack extends cdk.Stack {
  public readonly table: dynamodb.Table;
  public readonly kmsKey: kms.Key;
  public readonly s3Bucket: s3.IBucket;
  public readonly ingesterRole: iam.Role;
  public readonly consumerRole: iam.Role;

  constructor(scope: Construct, id: string, props: PrereqsStackProps) {
    super(scope, id, props);

    const { config } = props;
    const tableName = getTableName(config.stage);

    // KMS Key for encryption
    this.kmsKey = new kms.Key(this, 'DataEncryptionKey', {
      alias: `alias/processapp-external-data-${config.stage}`,
      description: `Encryption key for external data ingester (${config.stage})`,
      enableKeyRotation: true,
      removalPolicy: config.stage === 'prod'
        ? cdk.RemovalPolicy.RETAIN
        : cdk.RemovalPolicy.DESTROY,
      pendingWindow: config.stage === 'prod'
        ? cdk.Duration.days(30)
        : cdk.Duration.days(7),
    });

    // Add key policy statements
    const keyPolicyStatements = getKMSKeyPolicyStatements(
      config.account,
      config.region
    );
    keyPolicyStatements.forEach(statement => {
      this.kmsKey.addToResourcePolicy(statement);
    });

    // Reference existing S3 bucket (don't create it)
    this.s3Bucket = s3.Bucket.fromBucketName(
      this,
      'ExternalDataBucket',
      config.s3.bucket
    );

    // DynamoDB Table with CapitalCase naming (e.g., dev-ExternalData)
    this.table = new dynamodb.Table(this, 'ExternalDataTable', {
      tableName: tableName,
      partitionKey: {
        name: 'partitionKey',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'sortKey',
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.CUSTOMER_MANAGED,
      encryptionKey: this.kmsKey,
      pointInTimeRecovery: config.dynamodb.pitrEnabled,
      removalPolicy: config.stage === 'prod'
        ? cdk.RemovalPolicy.RETAIN
        : cdk.RemovalPolicy.DESTROY,
      timeToLiveAttribute: 'expirationTime',
    });

    // IAM Role for Ingester Lambda
    this.ingesterRole = new iam.Role(this, 'IngesterLambdaRole', {
      roleName: `processapp-ingester-role-${config.stage}`,
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      description: `Execution role for ingester Lambda (${config.stage})`,
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          'service-role/AWSLambdaBasicExecutionRole'
        ),
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          'AWSXRayDaemonWriteAccess'
        ),
      ],
      inlinePolicies: {
        IngesterPolicy: getIngesterLambdaPolicy(
          this.s3Bucket.bucketArn,
          this.table.tableArn,
          this.kmsKey.keyArn,
          config.region,
          config.account
        ),
      },
    });

    // IAM Role for Consumer Lambda
    this.consumerRole = new iam.Role(this, 'ConsumerLambdaRole', {
      roleName: `processapp-consumer-role-${config.stage}`,
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      description: `Execution role for consumer Lambda (${config.stage})`,
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          'service-role/AWSLambdaBasicExecutionRole'
        ),
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          'AWSXRayDaemonWriteAccess'
        ),
      ],
      inlinePolicies: {
        ConsumerPolicy: getConsumerLambdaPolicy(
          this.table.tableArn,
          this.kmsKey.keyArn,
          config.region,
          config.account
        ),
      },
    });

    // Apply cost allocation tags
    const tags = getCostAllocationTags(config.stage);
    Object.entries(tags).forEach(([key, value]) => {
      cdk.Tags.of(this).add(key, value);
    });

    // Stack outputs
    new cdk.CfnOutput(this, 'TableName', {
      value: this.table.tableName,
      description: 'DynamoDB table name',
      exportName: `${config.stage}-ExternalDataTableName`,
    });

    new cdk.CfnOutput(this, 'TableArn', {
      value: this.table.tableArn,
      description: 'DynamoDB table ARN',
      exportName: `${config.stage}-ExternalDataTableArn`,
    });

    new cdk.CfnOutput(this, 'KMSKeyId', {
      value: this.kmsKey.keyId,
      description: 'KMS key ID',
      exportName: `${config.stage}-DataEncryptionKeyId`,
    });

    new cdk.CfnOutput(this, 'KMSKeyArn', {
      value: this.kmsKey.keyArn,
      description: 'KMS key ARN',
      exportName: `${config.stage}-DataEncryptionKeyArn`,
    });

    new cdk.CfnOutput(this, 'S3BucketName', {
      value: this.s3Bucket.bucketName,
      description: 'S3 bucket name',
      exportName: `${config.stage}-ExternalDataBucketName`,
    });
  }
}

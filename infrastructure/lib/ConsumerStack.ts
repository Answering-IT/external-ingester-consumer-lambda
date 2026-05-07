/**
 * Consumer Stack: Lambda function + API Gateway for querying DynamoDB
 */

import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as kms from 'aws-cdk-lib/aws-kms';
import { Construct } from 'constructs';
import * as path from 'path';
import { EnvironmentConfig, getLambdaFunctionName, getApiGatewayName, getCostAllocationTags } from '../config/environments';

export interface ConsumerStackProps extends cdk.StackProps {
  config: EnvironmentConfig;
  table: dynamodb.ITable;
  kmsKey: kms.IKey;
  consumerRole: iam.IRole;
}

export class ConsumerStack extends cdk.Stack {
  public readonly consumerFunction: lambda.Function;
  public readonly api: apigateway.RestApi;

  constructor(scope: Construct, id: string, props: ConsumerStackProps) {
    super(scope, id, props);

    const { config, table, kmsKey, consumerRole } = props;
    const functionName = getLambdaFunctionName(config.stage, 'consumer');
    const apiName = getApiGatewayName(config.stage);

    // Consumer Lambda Function
    this.consumerFunction = new lambda.Function(this, 'ConsumerFunction', {
      functionName: functionName,
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.lambda_handler',
      code: lambda.Code.fromAsset(
        path.join(__dirname, '../lambdas/consumer')
      ),
      role: consumerRole,
      timeout: cdk.Duration.seconds(config.lambdas.consumer.timeoutSeconds),
      memorySize: config.lambdas.consumer.memoryMB,
      environment: {
        DYNAMODB_TABLE: table.tableName,
        STAGE: config.stage,
        KMS_KEY_ID: kmsKey.keyId,
      },
      description: `Consumer Lambda for external data API (${config.stage})`,
      tracing: lambda.Tracing.ACTIVE,
    });

    // API Gateway REST API
    this.api = new apigateway.RestApi(this, 'ExternalDataApi', {
      restApiName: apiName,
      description: `REST API for querying external data (${config.stage})`,
      deployOptions: {
        stageName: config.stage,
        tracingEnabled: true,
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        dataTraceEnabled: true,
        metricsEnabled: true,
      },
      cloudWatchRole: true,
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: ['GET', 'OPTIONS'],
        allowHeaders: ['Content-Type', 'Authorization'],
      },
    });

    // API Resources: /external/{partitionKey}/{sortKey}
    const externalResource = this.api.root.addResource('external');
    const partitionKeyResource = externalResource.addResource('{partitionKey}');
    const sortKeyResource = partitionKeyResource.addResource('{sortKey}');

    // Lambda integration
    const lambdaIntegration = new apigateway.LambdaIntegration(this.consumerFunction, {
      proxy: true,
      integrationResponses: [
        {
          statusCode: '200',
          responseParameters: {
            'method.response.header.Access-Control-Allow-Origin': "'*'",
          },
        },
        {
          statusCode: '404',
          selectionPattern: '.*"status":"not_found".*',
          responseParameters: {
            'method.response.header.Access-Control-Allow-Origin': "'*'",
          },
        },
        {
          statusCode: '500',
          selectionPattern: '.*"status":"error".*',
          responseParameters: {
            'method.response.header.Access-Control-Allow-Origin': "'*'",
          },
        },
      ],
    });

    // GET method on /external/{partitionKey}/{sortKey}
    sortKeyResource.addMethod('GET', lambdaIntegration, {
      methodResponses: [
        {
          statusCode: '200',
          responseParameters: {
            'method.response.header.Access-Control-Allow-Origin': true,
          },
        },
        {
          statusCode: '404',
          responseParameters: {
            'method.response.header.Access-Control-Allow-Origin': true,
          },
        },
        {
          statusCode: '500',
          responseParameters: {
            'method.response.header.Access-Control-Allow-Origin': true,
          },
        },
      ],
      requestParameters: {
        'method.request.path.partitionKey': true,
        'method.request.path.sortKey': true,
      },
    });

    // Apply cost allocation tags
    const tags = getCostAllocationTags(config.stage);
    Object.entries(tags).forEach(([key, value]) => {
      cdk.Tags.of(this).add(key, value);
    });

    // Stack outputs
    new cdk.CfnOutput(this, 'ConsumerFunctionName', {
      value: this.consumerFunction.functionName,
      description: 'Consumer Lambda function name',
      exportName: `${config.stage}-ConsumerFunctionName`,
    });

    new cdk.CfnOutput(this, 'ConsumerFunctionArn', {
      value: this.consumerFunction.functionArn,
      description: 'Consumer Lambda function ARN',
      exportName: `${config.stage}-ConsumerFunctionArn`,
    });

    new cdk.CfnOutput(this, 'ApiUrl', {
      value: this.api.url,
      description: 'API Gateway endpoint URL',
      exportName: `${config.stage}-ApiGatewayUrl`,
    });

    new cdk.CfnOutput(this, 'ApiEndpoint', {
      value: `${this.api.url}external/{partitionKey}/{sortKey}`,
      description: 'Full API endpoint pattern',
    });

    new cdk.CfnOutput(this, 'ExampleCurlCommand', {
      value: `curl -X GET "${this.api.url}external/YOUR_PARTITION_KEY/YOUR_SORT_KEY"`,
      description: 'Example curl command to query API',
    });
  }
}

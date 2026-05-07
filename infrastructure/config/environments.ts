/**
 * Environment configuration for External Ingester-Consumer Lambda Infrastructure
 */

export interface EnvironmentConfig {
  stage: string;
  region: string;
  account: string;
  profile: string;
  s3: {
    bucket: string;
  };
  dynamodb: {
    tableNamePattern: string;
    billingMode: 'PAY_PER_REQUEST' | 'PROVISIONED';
    pitrEnabled: boolean;
  };
  lambdas: {
    ingester: {
      memoryMB: number;
      timeoutSeconds: number;
      ephemeralStorageMB: number;
      reservedConcurrency: number;
      runtime: string;
    };
    consumer: {
      memoryMB: number;
      timeoutSeconds: number;
      runtime: string;
    };
  };
  processing: {
    batchSize: number;
    maxRetries: number;
    streamBufferSize: number;
  };
  tags: {
    [key: string]: string;
  };
}

/**
 * Development environment configuration
 */
export const DevConfig: EnvironmentConfig = {
  stage: 'dev',
  region: 'us-east-1',
  account: '708819485463',
  profile: 'ans-super',
  s3: {
    bucket: 'dev-answering-procesapp-info',
  },
  dynamodb: {
    tableNamePattern: '{Stage}-ExternalData', // dev-ExternalData
    billingMode: 'PAY_PER_REQUEST',
    pitrEnabled: true,
  },
  lambdas: {
    ingester: {
      memoryMB: 1024,
      timeoutSeconds: 900, // 15 minutes
      ephemeralStorageMB: 2048, // 2GB
      reservedConcurrency: 5,
      runtime: 'python3.11',
    },
    consumer: {
      memoryMB: 256,
      timeoutSeconds: 30,
      runtime: 'python3.11',
    },
  },
  processing: {
    batchSize: 25, // DynamoDB BatchWriteItem limit
    maxRetries: 3,
    streamBufferSize: 65536, // 64KB
  },
  tags: {
    Application: 'processapp',
    Component: 'external-ingester-consumer',
    ManagedBy: 'cdk',
    CostCenter: 'engineering',
  },
};

/**
 * Get table name with stage prefix in CapitalCase
 * Example: dev -> dev-ExternalData
 */
export function getTableName(stage: string): string {
  const capitalizedStage = stage.charAt(0).toUpperCase() + stage.slice(1);
  return `${capitalizedStage}-ExternalData`;
}

/**
 * Get Lambda function name
 */
export function getLambdaFunctionName(stage: string, functionType: 'ingester' | 'consumer'): string {
  return `processapp-${functionType}-${stage}`;
}

/**
 * Get API Gateway name
 */
export function getApiGatewayName(stage: string): string {
  return `processapp-external-api-${stage}`;
}

/**
 * Get cost allocation tags for resources
 */
export function getCostAllocationTags(stage: string): Record<string, string> {
  return {
    Environment: stage,
    Application: 'processapp',
    Component: 'external-pipeline',
    ManagedBy: 'cdk',
  };
}

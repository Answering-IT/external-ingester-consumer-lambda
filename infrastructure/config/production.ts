/**
 * Production environment configuration
 */

import { EnvironmentConfig } from './environments';

export const ProductionConfig: EnvironmentConfig = {
  stage: 'prod',
  region: 'us-east-2',
  account: '708819485463',
  profile: 'ans-super',
  s3: {
    bucket: 'prod-answering-procesapp-info',
  },
  dynamodb: {
    tableNamePattern: '{Stage}-ExternalData', // prod-ExternalData
    billingMode: 'PAY_PER_REQUEST',
    pitrEnabled: true,
  },
  lambdas: {
    ingester: {
      memoryMB: 2048, // More memory for production
      timeoutSeconds: 900,
      ephemeralStorageMB: 4096, // 4GB for production
      reservedConcurrency: 20, // Higher concurrency
      runtime: 'python3.11',
    },
    consumer: {
      memoryMB: 512,
      timeoutSeconds: 30,
      runtime: 'python3.11',
    },
  },
  processing: {
    batchSize: 25,
    maxRetries: 5, // More retries in production
    streamBufferSize: 131072, // 128KB
  },
  tags: {
    Environment: 'production',
    Application: 'processapp',
    Component: 'external-ingester-consumer',
    ManagedBy: 'cdk',
    CostCenter: 'engineering',
    Compliance: 'required',
  },
};

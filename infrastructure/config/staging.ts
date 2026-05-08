/**
 * Staging environment configuration
 */

import { EnvironmentConfig } from './environments';

export const StagingConfig: EnvironmentConfig = {
  stage: 'stg',
  region: 'us-east-1',
  account: '708819485463',
  profile: 'ans-super',
  s3: {
    bucket: 'stg-answering-procesapp-info',
  },
  dynamodb: {
    tableNamePattern: '{Stage}-ExternalData', // stg-ExternalData
    billingMode: 'PAY_PER_REQUEST',
    pitrEnabled: true,
  },
  lambdas: {
    ingester: {
      memoryMB: 1024,
      timeoutSeconds: 900, // 15 minutes
      ephemeralStorageMB: 2048, // 2GB
      reservedConcurrency: 10, // Higher than dev
      runtime: 'python3.11',
    },
    consumer: {
      memoryMB: 512, // More memory than dev
      timeoutSeconds: 30,
      runtime: 'python3.11',
    },
  },
  processing: {
    batchSize: 25,
    maxRetries: 3,
    streamBufferSize: 65536,
  },
  tags: {
    Environment: 'staging',
    Application: 'processapp',
    Component: 'external-ingester-consumer',
    ManagedBy: 'cdk',
    CostCenter: 'engineering',
  },
};

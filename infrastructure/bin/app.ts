#!/usr/bin/env node

/**
 * CDK App Entry Point
 * External Ingester-Consumer Lambda Infrastructure
 */

import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { PrereqsStack } from '../lib/PrereqsStack';
import { IngesterStack } from '../lib/IngesterStack';
import { ConsumerStack } from '../lib/ConsumerStack';
import { DevConfig } from '../config/environments';
import { StagingConfig } from '../config/staging';
import { ProductionConfig } from '../config/production';

const app = new cdk.App();

// Get stage and region from CDK context
const stage = app.node.tryGetContext('stage') || 'dev';
const region = app.node.tryGetContext('region');

// Select configuration based on stage
let config;
switch (stage) {
  case 'stg':
  case 'staging':
    config = StagingConfig;
    break;
  case 'prod':
  case 'production':
    config = ProductionConfig;
    break;
  case 'dev':
  case 'development':
  default:
    config = DevConfig;
}

// Override region if provided in context
if (region) {
  config = { ...config, region };
}

// Environment configuration
const env = {
  account: config.account,
  region: config.region,
};

// Prerequisites Stack: DynamoDB, KMS, IAM Roles
const prereqsStack = new PrereqsStack(app, `${config.stage}-PrereqsStack`, {
  config,
  env,
  description: `Prerequisites for external ingester-consumer (${config.stage})`,
  tags: config.tags,
});

// Ingester Stack: Lambda for streaming CSV ingestion
const ingesterStack = new IngesterStack(app, `${config.stage}-IngesterStack`, {
  config,
  kmsKey: prereqsStack.kmsKey,
  s3Bucket: prereqsStack.s3Bucket,
  ingesterRole: prereqsStack.ingesterRole,
  env,
  description: `Ingester Lambda for external data (${config.stage})`,
  tags: config.tags,
});

// Consumer Stack: Lambda + API Gateway for querying
const consumerStack = new ConsumerStack(app, `${config.stage}-ConsumerStack`, {
  config,
  table: prereqsStack.table,
  kmsKey: prereqsStack.kmsKey,
  consumerRole: prereqsStack.consumerRole,
  env,
  description: `Consumer Lambda + API Gateway for external data (${config.stage})`,
  tags: config.tags,
});

// Stack dependencies
ingesterStack.addDependency(prereqsStack);
consumerStack.addDependency(prereqsStack);

// Synthesize CloudFormation templates
app.synth();

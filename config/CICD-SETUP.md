# CI/CD Setup Guide

GitHub Actions CI/CD pipeline using OIDC authentication with AWS.

---

## 🔐 AWS Authentication (OIDC)

This project uses **OpenID Connect (OIDC)** for secure, keyless authentication.

### ✅ Already Configured

The following AWS resources have been created:

- **OIDC Provider**: `token.actions.githubusercontent.com`
- **IAM Role**: `GitHubActions-external-ingester-consumer-lambda-Role`
- **Role ARN**: `arn:aws:iam::708819485463:role/GitHubActions-external-ingester-consumer-lambda-Role`

**No GitHub secrets required!** Workflows use temporary credentials via OIDC.

### Recreate OIDC Setup

If you need to recreate or update the OIDC configuration:

```bash
bash setup-github-oidc.sh
```

This script will:
1. Create OIDC Identity Provider in AWS (if not exists)
2. Create IAM Role with trust policy for this repository
3. Attach permissions policy for CDK deployments

---

## 🚀 Workflows

### 1. Build.yml
**Trigger:** Push or PR to `main`

**Actions:**
- Python formatting and linting
- Unit tests
- TypeScript build
- CDK synth
- **CDK diff on PRs** (posts infrastructure changes as comment)

### 2. Deploy.yml
**Trigger:** Push to `main`

**Deploys to:**
- Stage: `dev`
- Region: `us-east-1`

### 3. Release.yml
**Trigger:** Push tag `v*`

**Logic:**
- Tag with `-rc1`, `-rc2`, etc. → **Staging** (us-east-1)
- Tag without `-rc` suffix → **Production** (us-east-2)

---

## 📋 Usage

### Deploy to Dev
```bash
git push origin main
```

### Deploy to Staging
```bash
git tag v1.0.0-rc1
git push origin v1.0.0-rc1
```

### Deploy to Production
```bash
git tag v1.0.0
git push origin v1.0.0
```

---

## 🔧 Permissions

The IAM role has permissions for:
- CloudFormation (all stacks)
- Lambda (create/update functions)
- DynamoDB (tables and operations)
- API Gateway (REST APIs)
- IAM (roles and policies)
- KMS (encryption keys)
- CloudWatch Logs
- S3 (buckets and objects)
- SSM (parameters)

---

## 🧪 Testing Locally

See [RUN_TESTS.md](./RUN_TESTS.md) for running tests locally.

---

## 📚 Resources

- [GitHub OIDC Documentation](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [AWS Configure Credentials Action](https://github.com/aws-actions/configure-aws-credentials)
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)

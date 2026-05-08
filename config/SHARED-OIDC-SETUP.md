# Shared OIDC Role for All Repositories

Use **one IAM role** across all repositories in the Answering-IT organization.

---

## ✅ Already Setup

**Shared Role ARN:**
```
arn:aws:iam::708819485463:role/GitHubActions-Answering-IT-SharedRole
```

This role can be used by **ANY** repository in the `Answering-IT` organization.

---

## 🚀 Use in Any Repository

Add this to `.github/workflows/deploy.yml` in **any** Answering-IT repository:

```yaml
name: Deploy

on:
  push:
    branches:
      - main

permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::708819485463:role/GitHubActions-Answering-IT-SharedRole
          aws-region: us-east-1

      - name: Deploy
        run: |
          # Your deployment commands
          aws sts get-caller-identity
          npx cdk deploy --all
```

---

## 📋 Permissions Included

The shared role has permissions for:

- **CloudFormation** - All stack operations
- **Lambda** - Functions, layers, triggers
- **DynamoDB** - Tables and operations
- **API Gateway** - REST APIs, stages
- **S3** - All bucket and object operations
- **IAM** - Roles, policies (for CDK)
- **KMS** - Encryption keys
- **CloudWatch** - Logs and metrics
- **ECR** - Docker registries
- **RDS** - Database instances
- **ElastiCache** - Redis/Memcached
- **SQS/SNS** - Messaging
- **EventBridge** - Event rules
- **Step Functions** - State machines
- **Cognito** - User pools
- **Route53** - DNS
- **CloudFront** - CDN
- **ACM** - SSL certificates
- **Secrets Manager** - Secrets
- **ELB/ALB** - Load balancers
- **Auto Scaling** - Scaling groups
- **SSM** - Parameter Store

---

## 🔒 Security

The trust policy allows:
- **Organization**: `Answering-IT/*` (all repos)
- **Action**: `sts:AssumeRoleWithWebIdentity`
- **Condition**: Must be GitHub OIDC token with correct audience

**No secrets needed** - temporary credentials issued per workflow run.

---

## 🔄 Update Shared Role

To update permissions or trust policy:

```bash
bash setup-github-oidc-shared.sh
```

This will update the existing role without disrupting running workflows.

---

## ❌ Delete Old Repository-Specific Roles

Since we now have a shared role, you can delete the old repository-specific roles:

```bash
# List existing GitHub Actions roles
aws iam list-roles --query 'Roles[?starts_with(RoleName, `GitHubActions-`)].RoleName' --output table --profile ans-super

# Delete old role (example)
ROLE_NAME="GitHubActions-external-ingester-consumer-lambda-Role"
POLICY_ARN=$(aws iam list-attached-role-policies --role-name $ROLE_NAME --query 'AttachedPolicies[0].PolicyArn' --output text --profile ans-super)
aws iam detach-role-policy --role-name $ROLE_NAME --policy-arn $POLICY_ARN --profile ans-super
aws iam delete-policy --policy-arn $POLICY_ARN --profile ans-super
aws iam delete-role --role-name $ROLE_NAME --profile ans-super
```

---

## 💡 Benefits

1. **Simplicity**: One role for all repositories
2. **No per-repo setup**: Just use the same ARN everywhere
3. **Easy updates**: Update permissions once, affects all repos
4. **No secrets**: OIDC handles authentication
5. **Auditable**: CloudTrail shows which repo used the role

---

## 📚 For Other Organizations

To create a shared role for a different GitHub organization:

```bash
# Edit the script to change GITHUB_ORG
bash setup-github-oidc-shared.sh
```

---

**Questions?** See `CICD-SETUP.md` for detailed workflow examples.

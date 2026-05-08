# Setting Up OIDC for Other Repositories

Quick guide to enable GitHub Actions OIDC authentication for any repository in the Answering-IT organization.

---

## 🚀 Quick Setup

### For a new repository:

```bash
bash setup-github-oidc-for-repo.sh <repo-name>
```

**Example:**
```bash
bash setup-github-oidc-for-repo.sh my-lambda-api
```

This will:
1. ✅ Reuse the existing OIDC Provider (already created)
2. ✅ Create a new IAM Role specific to that repository
3. ✅ Attach default CDK deployment permissions
4. ✅ Output the workflow configuration to copy

---

## 📋 What Gets Created

For a repo named `my-lambda-api`, the script creates:

- **IAM Role**: `GitHubActions-my-lambda-api-Role`
- **IAM Policy**: `GitHubActions-my-lambda-api-Role-Policy`
- **Role ARN**: `arn:aws:iam::708819485463:role/GitHubActions-my-lambda-api-Role`

The role can ONLY be assumed by workflows running in `Answering-IT/my-lambda-api`.

---

## 🔧 Custom Permissions

If your repository needs different permissions, create a JSON file:

**custom-permissions.json:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:*",
        "cloudfront:*",
        "lambda:InvokeFunction"
      ],
      "Resource": "*"
    }
  ]
}
```

Then run:
```bash
bash setup-github-oidc-for-repo.sh my-repo ans-super custom-permissions.json
```

---

## 📝 Default Permissions Included

The default policy includes permissions for:

- **CloudFormation**: Create/update/delete stacks
- **Lambda**: Create/update functions, layers
- **DynamoDB**: Create tables, read/write data
- **API Gateway**: Create/manage REST APIs
- **S3**: Bucket operations, object read/write
- **IAM**: Create/manage roles and policies
- **KMS**: Encryption key operations
- **CloudWatch Logs**: Create log groups, write logs
- **SSM**: Parameter Store operations
- **ECR**: Docker image operations
- **EC2**: Describe resources (for VPC lookups)

---

## 🔐 Adding to Your Workflow

After running the script, add this to `.github/workflows/deploy.yml`:

```yaml
name: Deploy

on:
  push:
    branches:
      - main

permissions:
  id-token: write   # Required for OIDC
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
          role-to-assume: arn:aws:iam::708819485463:role/GitHubActions-<YOUR-REPO>-Role
          aws-region: us-east-1

      - name: Deploy
        run: |
          # Your deployment commands
          aws sts get-caller-identity
          npx cdk deploy --all
```

Replace `<YOUR-REPO>` with your repository name.

---

## ✅ No Secrets Needed

With OIDC, you **don't need** to add any GitHub secrets:
- ❌ No `AWS_ACCESS_KEY_ID`
- ❌ No `AWS_SECRET_ACCESS_KEY`

GitHub automatically gets temporary credentials from AWS.

---

## 🔄 For Multiple Environments

Create environment-specific roles:

```bash
# Development role
bash setup-github-oidc-for-repo.sh my-app-dev

# Staging role (with staging permissions)
bash setup-github-oidc-for-repo.sh my-app-stg ans-super staging-permissions.json

# Production role (with production permissions)
bash setup-github-oidc-for-repo.sh my-app-prod ans-super prod-permissions.json
```

Then use GitHub Environments to control which role is used:

```yaml
jobs:
  deploy-prod:
    environment: production
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::708819485463:role/GitHubActions-my-app-prod-Role
          aws-region: us-east-1
```

---

## 🛠️ Advanced Usage

### Different AWS Profile
```bash
bash setup-github-oidc-for-repo.sh my-repo other-profile
```

### Update Existing Role
Just run the script again - it will update the trust policy and permissions:
```bash
bash setup-github-oidc-for-repo.sh my-repo ans-super updated-permissions.json
```

### Delete a Role
```bash
ROLE_NAME="GitHubActions-my-repo-Role"
aws iam detach-role-policy --role-name $ROLE_NAME --policy-arn $(aws iam list-attached-role-policies --role-name $ROLE_NAME --query 'AttachedPolicies[0].PolicyArn' --output text) --profile ans-super
aws iam delete-role --role-name $ROLE_NAME --profile ans-super
```

---

## 📚 Resources

- [GitHub OIDC Documentation](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [AWS Configure Credentials Action](https://github.com/aws-actions/configure-aws-credentials)
- [IAM Roles for OIDC](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html)

---

## 💡 Benefits

1. **Security**: No long-lived credentials to rotate or leak
2. **Auditability**: Each workflow run gets unique temporary credentials
3. **Simplicity**: No secrets to manage in GitHub
4. **Flexibility**: Different roles for different repos/environments
5. **Cost**: Free! No additional AWS costs

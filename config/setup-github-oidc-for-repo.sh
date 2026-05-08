#!/bin/bash
# Setup GitHub OIDC for any repository
# Usage: bash setup-github-oidc-for-repo.sh <repo-name> [aws-profile] [permissions-file]

set -e

# Check arguments
if [ -z "$1" ]; then
  echo "❌ Error: Repository name required"
  echo "Usage: bash setup-github-oidc-for-repo.sh <repo-name> [aws-profile] [permissions-file]"
  echo ""
  echo "Examples:"
  echo "  bash setup-github-oidc-for-repo.sh my-lambda-project"
  echo "  bash setup-github-oidc-for-repo.sh my-api ans-super"
  echo "  bash setup-github-oidc-for-repo.sh my-app ans-super custom-permissions.json"
  exit 1
fi

GITHUB_REPO="$1"
AWS_PROFILE="${2:-ans-super}"
PERMISSIONS_FILE="$3"

AWS_ACCOUNT_ID="708819485463"
AWS_REGION="us-east-1"
GITHUB_ORG="Answering-IT"

echo "🚀 Setting up GitHub OIDC for repository..."
echo "Account: $AWS_ACCOUNT_ID"
echo "Repository: $GITHUB_ORG/$GITHUB_REPO"
echo "Profile: $AWS_PROFILE"
echo ""

# Step 1: Check OIDC Provider exists (reuse if it does)
echo "Step 1: Checking OIDC Identity Provider..."

OIDC_PROVIDER_ARN=$(aws iam list-open-id-connect-providers \
  --profile $AWS_PROFILE \
  --query "OpenIDConnectProviderList[?contains(Arn, 'token.actions.githubusercontent.com')].Arn" \
  --output text)

if [ -z "$OIDC_PROVIDER_ARN" ]; then
  echo "Creating OIDC provider..."
  aws iam create-open-id-connect-provider \
    --profile $AWS_PROFILE \
    --url https://token.actions.githubusercontent.com \
    --client-id-list sts.amazonaws.com \
    --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 1c58a3a8518e8759bf075b76b750d4f2df264fcd \
    > /dev/null

  OIDC_PROVIDER_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
  echo "✅ OIDC Provider created"
else
  echo "✅ OIDC Provider already exists (reusing)"
fi

echo ""

# Step 2: Create IAM Role
echo "Step 2: Creating IAM Role..."

ROLE_NAME="GitHubActions-${GITHUB_REPO}-Role"

cat > /tmp/github-oidc-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "${OIDC_PROVIDER_ARN}"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:${GITHUB_ORG}/${GITHUB_REPO}:*"
        }
      }
    }
  ]
}
EOF

if aws iam get-role --role-name $ROLE_NAME --profile $AWS_PROFILE >/dev/null 2>&1; then
  echo "Role exists, updating trust policy..."
  aws iam update-assume-role-policy \
    --profile $AWS_PROFILE \
    --role-name $ROLE_NAME \
    --policy-document file:///tmp/github-oidc-trust-policy.json
else
  echo "Creating new role..."
  aws iam create-role \
    --profile $AWS_PROFILE \
    --role-name $ROLE_NAME \
    --assume-role-policy-document file:///tmp/github-oidc-trust-policy.json \
    --description "GitHub Actions OIDC role for ${GITHUB_REPO}" \
    > /dev/null
fi

ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}"
echo "✅ Role: $ROLE_ARN"

echo ""

# Step 3: Attach permissions
echo "Step 3: Configuring permissions..."

POLICY_NAME="${ROLE_NAME}-Policy"

# Use custom permissions file if provided, otherwise use default CDK permissions
if [ -n "$PERMISSIONS_FILE" ] && [ -f "$PERMISSIONS_FILE" ]; then
  echo "Using custom permissions from: $PERMISSIONS_FILE"
  cp "$PERMISSIONS_FILE" /tmp/github-actions-permissions.json
else
  echo "Using default CDK deployment permissions..."
  cat > /tmp/github-actions-permissions.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CDKDeployPermissions",
      "Effect": "Allow",
      "Action": [
        "cloudformation:*",
        "s3:*",
        "lambda:*",
        "dynamodb:*",
        "apigateway:*",
        "iam:*",
        "kms:*",
        "logs:*",
        "sts:GetCallerIdentity",
        "ssm:GetParameter",
        "ssm:PutParameter",
        "ecr:*",
        "ec2:DescribeAvailabilityZones",
        "ec2:DescribeVpcs",
        "ec2:DescribeSubnets",
        "ec2:DescribeSecurityGroups"
      ],
      "Resource": "*"
    }
  ]
}
EOF
fi

# Check if policy exists
POLICY_ARN=$(aws iam list-policies \
  --profile $AWS_PROFILE \
  --scope Local \
  --query "Policies[?PolicyName=='${POLICY_NAME}'].Arn" \
  --output text)

if [ -z "$POLICY_ARN" ]; then
  echo "Creating policy..."
  POLICY_ARN=$(aws iam create-policy \
    --profile $AWS_PROFILE \
    --policy-name $POLICY_NAME \
    --policy-document file:///tmp/github-actions-permissions.json \
    --query 'Policy.Arn' \
    --output text)
else
  echo "Updating existing policy..."
  # Delete old versions if at limit (max 5 versions)
  OLD_VERSIONS=$(aws iam list-policy-versions \
    --profile $AWS_PROFILE \
    --policy-arn $POLICY_ARN \
    --query 'Versions[?!IsDefaultVersion].VersionId' \
    --output text)

  for version in $OLD_VERSIONS; do
    aws iam delete-policy-version \
      --profile $AWS_PROFILE \
      --policy-arn $POLICY_ARN \
      --version-id $version 2>/dev/null || true
  done

  aws iam create-policy-version \
    --profile $AWS_PROFILE \
    --policy-arn $POLICY_ARN \
    --policy-document file:///tmp/github-actions-permissions.json \
    --set-as-default \
    > /dev/null
fi

# Attach policy to role
aws iam attach-role-policy \
  --profile $AWS_PROFILE \
  --role-name $ROLE_NAME \
  --policy-arn $POLICY_ARN 2>/dev/null || echo "(Policy already attached)"

echo "✅ Permissions configured"

echo ""
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "📋 Add this to your GitHub Actions workflow:"
echo ""
echo "permissions:"
echo "  id-token: write    # Required for OIDC"
echo "  contents: read"
echo ""
echo "jobs:"
echo "  deploy:"
echo "    runs-on: ubuntu-latest"
echo "    steps:"
echo "      - name: Configure AWS Credentials"
echo "        uses: aws-actions/configure-aws-credentials@v4"
echo "        with:"
echo "          role-to-assume: ${ROLE_ARN}"
echo "          aws-region: ${AWS_REGION}"
echo ""
echo "      - name: Deploy"
echo "        run: |"
echo "          # Your deployment commands here"
echo "          aws sts get-caller-identity"
echo ""
echo "🔐 Role ARN: ${ROLE_ARN}"
echo ""

# Cleanup
rm -f /tmp/github-oidc-trust-policy.json /tmp/github-actions-permissions.json

echo "💡 Tip: You can create custom permissions by providing a JSON file:"
echo "   bash $0 $GITHUB_REPO $AWS_PROFILE my-permissions.json"
echo ""

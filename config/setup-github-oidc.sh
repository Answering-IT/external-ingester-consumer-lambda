#!/bin/bash
# Setup GitHub OIDC for AWS
# Run with: bash setup-github-oidc.sh

set -e

AWS_ACCOUNT_ID="708819485463"
AWS_PROFILE="ans-super"
AWS_REGION="us-east-1"
GITHUB_ORG="Answering-IT"
GITHUB_REPO="external-ingester-consumer-lambda"

echo "🚀 Setting up GitHub OIDC for AWS..."
echo "Account: $AWS_ACCOUNT_ID"
echo "Repository: $GITHUB_ORG/$GITHUB_REPO"
echo ""

# Step 1: Create OIDC Provider (if it doesn't exist)
echo "Step 1: Creating OIDC Identity Provider..."

OIDC_PROVIDER_ARN=$(aws iam list-open-id-connect-providers \
  --profile $AWS_PROFILE \
  --query "OpenIDConnectProviderList[?contains(Arn, 'token.actions.githubusercontent.com')].Arn" \
  --output text)

if [ -z "$OIDC_PROVIDER_ARN" ]; then
  echo "Creating new OIDC provider..."
  aws iam create-open-id-connect-provider \
    --profile $AWS_PROFILE \
    --url https://token.actions.githubusercontent.com \
    --client-id-list sts.amazonaws.com \
    --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 1c58a3a8518e8759bf075b76b750d4f2df264fcd

  OIDC_PROVIDER_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
  echo "✅ OIDC Provider created: $OIDC_PROVIDER_ARN"
else
  echo "✅ OIDC Provider already exists: $OIDC_PROVIDER_ARN"
fi

echo ""

# Step 2: Create IAM Role with trust policy
echo "Step 2: Creating IAM Role for GitHub Actions..."

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

# Check if role exists
if aws iam get-role --role-name $ROLE_NAME --profile $AWS_PROFILE >/dev/null 2>&1; then
  echo "Role already exists, updating trust policy..."
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
    --description "GitHub Actions OIDC role for ${GITHUB_REPO}"
fi

ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}"
echo "✅ Role created/updated: $ROLE_ARN"

echo ""

# Step 3: Attach permissions policy
echo "Step 3: Attaching permissions to role..."

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
        "ssm:PutParameter"
      ],
      "Resource": "*"
    }
  ]
}
EOF

POLICY_NAME="${ROLE_NAME}-Policy"

# Check if policy exists
POLICY_ARN=$(aws iam list-policies \
  --profile $AWS_PROFILE \
  --scope Local \
  --query "Policies[?PolicyName=='${POLICY_NAME}'].Arn" \
  --output text)

if [ -z "$POLICY_ARN" ]; then
  echo "Creating new policy..."
  POLICY_ARN=$(aws iam create-policy \
    --profile $AWS_PROFILE \
    --policy-name $POLICY_NAME \
    --policy-document file:///tmp/github-actions-permissions.json \
    --query 'Policy.Arn' \
    --output text)
  echo "✅ Policy created: $POLICY_ARN"
else
  echo "Policy already exists, creating new version..."
  aws iam create-policy-version \
    --profile $AWS_PROFILE \
    --policy-arn $POLICY_ARN \
    --policy-document file:///tmp/github-actions-permissions.json \
    --set-as-default
  echo "✅ Policy updated: $POLICY_ARN"
fi

# Attach policy to role
aws iam attach-role-policy \
  --profile $AWS_PROFILE \
  --role-name $ROLE_NAME \
  --policy-arn $POLICY_ARN 2>/dev/null || echo "Policy already attached"

echo "✅ Policy attached to role"

echo ""
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "📋 Add this to your GitHub Actions workflow:"
echo ""
echo "permissions:"
echo "  id-token: write"
echo "  contents: read"
echo "  pull-requests: write"
echo ""
echo "- name: Configure AWS Credentials"
echo "  uses: aws-actions/configure-aws-credentials@v4"
echo "  with:"
echo "    role-to-assume: ${ROLE_ARN}"
echo "    aws-region: ${AWS_REGION}"
echo ""
echo "🔐 Role ARN: ${ROLE_ARN}"
echo ""

# Cleanup temp files
rm -f /tmp/github-oidc-trust-policy.json /tmp/github-actions-permissions.json

#!/bin/bash
# Setup a SHARED GitHub OIDC role for ALL repositories in the organization
# Usage: bash setup-github-oidc-shared.sh [aws-profile]

set -e

AWS_PROFILE="${1:-ans-super}"
AWS_ACCOUNT_ID="708819485463"
AWS_REGION="us-east-1"
GITHUB_ORG="Answering-IT"

echo "🚀 Setting up SHARED GitHub OIDC role..."
echo "Account: $AWS_ACCOUNT_ID"
echo "Organization: $GITHUB_ORG"
echo "Profile: $AWS_PROFILE"
echo ""

# Step 1: Check OIDC Provider exists
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
  echo "✅ OIDC Provider already exists"
fi

echo ""

# Step 2: Create SHARED IAM Role
echo "Step 2: Creating SHARED IAM Role..."

ROLE_NAME="GitHubActions-${GITHUB_ORG}-SharedRole"

# Trust policy allows ALL repositories in the organization
cat > /tmp/github-oidc-shared-trust-policy.json <<EOF
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
          "token.actions.githubusercontent.com:sub": "repo:${GITHUB_ORG}/*:*"
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
    --policy-document file:///tmp/github-oidc-shared-trust-policy.json
else
  echo "Creating new shared role..."
  aws iam create-role \
    --profile $AWS_PROFILE \
    --role-name $ROLE_NAME \
    --assume-role-policy-document file:///tmp/github-oidc-shared-trust-policy.json \
    --description "Shared GitHub Actions OIDC role for all ${GITHUB_ORG} repositories" \
    > /dev/null
fi

ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}"
echo "✅ Role: $ROLE_ARN"

echo ""

# Step 3: Attach comprehensive permissions
echo "Step 3: Configuring permissions..."

POLICY_NAME="${ROLE_NAME}-Policy"

cat > /tmp/github-actions-shared-permissions.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CDKAndServerlessDeployment",
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
        "ssm:*",
        "ecr:*",
        "ec2:Describe*",
        "ec2:CreateTags",
        "ec2:DeleteTags",
        "rds:*",
        "elasticache:*",
        "sqs:*",
        "sns:*",
        "events:*",
        "states:*",
        "cognito-idp:*",
        "route53:*",
        "cloudfront:*",
        "acm:*",
        "secretsmanager:*",
        "elasticloadbalancing:*",
        "autoscaling:*",
        "cloudwatch:*",
        "application-autoscaling:*"
      ],
      "Resource": "*"
    }
  ]
}
EOF

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
    --policy-document file:///tmp/github-actions-shared-permissions.json \
    --query 'Policy.Arn' \
    --output text)
else
  echo "Updating existing policy..."
  # Delete old versions
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
    --policy-document file:///tmp/github-actions-shared-permissions.json \
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
echo "✅ Shared Role Setup Complete!"
echo "=========================================="
echo ""
echo "This role can be used by ANY repository in the ${GITHUB_ORG} organization."
echo ""
echo "📋 Use this in ALL your GitHub Actions workflows:"
echo ""
echo "permissions:"
echo "  id-token: write"
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
echo "🔐 Shared Role ARN: ${ROLE_ARN}"
echo ""
echo "✅ No per-repository setup needed!"
echo "   Just use this role ARN in any ${GITHUB_ORG} repository."
echo ""

# Cleanup
rm -f /tmp/github-oidc-shared-trust-policy.json /tmp/github-actions-shared-permissions.json

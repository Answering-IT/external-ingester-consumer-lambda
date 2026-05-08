# Managing Repository Access to OIDC Role

Guide to understanding and managing which repositories can use the shared OIDC role.

---

## 🎯 Current Setup

The shared role **already allows ALL repositories** in the `Answering-IT` organization.

**Trust Policy Pattern:**
```json
"token.actions.githubusercontent.com:sub": "repo:Answering-IT/*:*"
```

This means:
- ✅ Any repository in `Answering-IT` can use the role
- ✅ Works for all branches, tags, and PRs
- ✅ **No additional setup needed for new repos**

---

## ✅ Adding a New Repository

### Option 1: Do Nothing (Recommended)

Since the trust policy uses a wildcard (`Answering-IT/*`), **new repositories automatically have access**.

Just use the role ARN in your workflow:

```yaml
permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::708819485463:role/GitHubActions-Answering-IT-SharedRole
          aws-region: us-east-1
```

### Option 2: Restrict to Specific Repositories

If you want to **limit** which repositories can use the role, update the trust policy:

```bash
# Edit the trust policy to specify repositories
aws iam get-role --role-name GitHubActions-Answering-IT-SharedRole --profile ans-super --query 'Role.AssumeRolePolicyDocument' > trust-policy.json

# Edit trust-policy.json and change the condition:
# FROM: "repo:Answering-IT/*:*"
# TO: List specific repos
```

**Example Restricted Trust Policy:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::708819485463:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": [
            "repo:Answering-IT/external-ingester-consumer-lambda:*",
            "repo:Answering-IT/my-api-project:*",
            "repo:Answering-IT/my-frontend-app:*"
          ]
        }
      }
    }
  ]
}
```

**Apply the updated policy:**

```bash
aws iam update-assume-role-policy \
  --role-name GitHubActions-Answering-IT-SharedRole \
  --policy-document file://trust-policy.json \
  --profile ans-super
```

---

## 🔍 View Current Trust Policy

See which repositories currently have access:

```bash
aws iam get-role \
  --role-name GitHubActions-Answering-IT-SharedRole \
  --profile ans-super \
  --query 'Role.AssumeRolePolicyDocument' \
  --output json
```

---

## 📝 Trust Policy Patterns

### Allow All Repositories in Organization
```json
"token.actions.githubusercontent.com:sub": "repo:Answering-IT/*:*"
```
✅ Current setup  
✅ Easiest to manage  
✅ No updates needed for new repos

### Allow Specific Repositories
```json
"token.actions.githubusercontent.com:sub": [
  "repo:Answering-IT/repo1:*",
  "repo:Answering-IT/repo2:*"
]
```
✅ More restrictive  
❌ Requires updates for each new repo

### Allow Specific Branch in Specific Repository
```json
"token.actions.githubusercontent.com:sub": "repo:Answering-IT/my-repo:ref:refs/heads/main"
```
✅ Most restrictive  
❌ Only main branch can deploy  
❌ Tags and PRs cannot use role

### Allow Main Branch Across All Repositories
```json
"token.actions.githubusercontent.com:sub": "repo:Answering-IT/*:ref:refs/heads/main"
```
✅ Only main branch deployments  
⚠️ Prevents PR workflows from using role

---

## 🔄 Adding a Repository to Restricted Policy

If you're using a restricted policy (specific repo list):

### Step 1: Get Current Policy
```bash
aws iam get-role \
  --role-name GitHubActions-Answering-IT-SharedRole \
  --profile ans-super \
  --query 'Role.AssumeRolePolicyDocument' \
  > current-trust-policy.json
```

### Step 2: Edit the JSON
Add your new repository to the `StringLike.token.actions.githubusercontent.com:sub` array:

```json
"token.actions.githubusercontent.com:sub": [
  "repo:Answering-IT/existing-repo:*",
  "repo:Answering-IT/NEW-REPO-NAME:*"
]
```

### Step 3: Update the Policy
```bash
aws iam update-assume-role-policy \
  --role-name GitHubActions-Answering-IT-SharedRole \
  --policy-document file://current-trust-policy.json \
  --profile ans-super
```

### Step 4: Verify
```bash
aws iam get-role \
  --role-name GitHubActions-Answering-IT-SharedRole \
  --profile ans-super \
  --query 'Role.AssumeRolePolicyDocument.Statement[0].Condition'
```

---

## 🛡️ Security Considerations

### Current Wildcard Setup (`Answering-IT/*`)

**Pros:**
- ✅ Simple management
- ✅ No updates needed
- ✅ Works for all branches, tags, PRs

**Cons:**
- ⚠️ Any repo in the organization can deploy
- ⚠️ Compromised repo could access AWS

**Recommendation:** Use wildcard if you trust all organization members.

### Specific Repository List

**Pros:**
- ✅ More secure
- ✅ Explicit allow list

**Cons:**
- ❌ Manual updates for each repo
- ❌ Can forget to add new repos

**Recommendation:** Use if you have untrusted/public repos in the organization.

---

## 🔧 Helper Script: Add Repository

Create a helper script to add repos easily:

```bash
#!/bin/bash
# add-repo-to-oidc.sh
# Usage: bash add-repo-to-oidc.sh <repo-name>

REPO_NAME="$1"
ROLE_NAME="GitHubActions-Answering-IT-SharedRole"
PROFILE="ans-super"

if [ -z "$REPO_NAME" ]; then
  echo "Usage: bash add-repo-to-oidc.sh <repo-name>"
  exit 1
fi

echo "Adding repo: Answering-IT/$REPO_NAME"

# Get current policy
aws iam get-role \
  --role-name $ROLE_NAME \
  --profile $PROFILE \
  --query 'Role.AssumeRolePolicyDocument' \
  > /tmp/trust-policy.json

# Add the repo using jq
jq --arg repo "repo:Answering-IT/${REPO_NAME}:*" \
  '.Statement[0].Condition.StringLike."token.actions.githubusercontent.com:sub" += [$repo]' \
  /tmp/trust-policy.json > /tmp/updated-trust-policy.json

# Update the policy
aws iam update-assume-role-policy \
  --role-name $ROLE_NAME \
  --policy-document file:///tmp/updated-trust-policy.json \
  --profile $PROFILE

echo "✅ Repository added to trust policy"

# Cleanup
rm /tmp/trust-policy.json /tmp/updated-trust-policy.json
```

---

## 📊 Audit Repository Access

### See Which Repos Have Used the Role

Check CloudTrail for AssumeRoleWithWebIdentity events:

```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceName,AttributeValue=GitHubActions-Answering-IT-SharedRole \
  --profile ans-super \
  --query 'Events[*].[EventTime,Username]' \
  --output table
```

### Check Recent Role Assumptions

```bash
aws iam get-role \
  --role-name GitHubActions-Answering-IT-SharedRole \
  --profile ans-super \
  --query 'Role.RoleLastUsed'
```

---

## 🚨 Troubleshooting

### Error: "Not authorized to perform sts:AssumeRoleWithWebIdentity"

**Cause:** Repository not in trust policy

**Solution:**
1. Check current trust policy (see above)
2. Verify repository name matches exactly
3. Ensure pattern includes your branch/tag/PR

### Error: "No OpenIDConnect provider found"

**Cause:** OIDC provider not created

**Solution:**
```bash
bash setup-github-oidc-shared.sh
```

---

## 📚 References

- [GitHub OIDC Subject Claims](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect#understanding-the-oidc-token)
- [IAM Trust Policies](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html)
- [GitHub Actions Security Best Practices](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)

---

## 💡 Recommendations

**For small teams (< 10 repos):**
- ✅ Use wildcard pattern (`Answering-IT/*:*`)
- Simple and low maintenance

**For larger organizations:**
- ✅ Use specific repository list
- Better security and auditability
- Use helper script to manage additions

**For production environments:**
- ✅ Restrict to main branch only
- ✅ Use separate roles for dev/staging/prod
- ✅ Enable CloudTrail logging

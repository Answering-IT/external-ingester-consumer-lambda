# DynamoDB Console Access Guide

This guide explains how to grant users access to view, scan, query, and write to the DynamoDB table from the AWS Console.

## Overview

The DynamoDB table is encrypted using a customer-managed KMS key. The stack creates **Managed Policies** that any user in the account can attach.

## Available Managed Policies

| Policy Name | ARN | Permissions |
|-------------|-----|-------------|
| `processapp-dynamodb-readonly-dev` | `arn:aws:iam::708819485463:policy/processapp-dynamodb-readonly-dev` | Read-only access |
| `processapp-dynamodb-readwrite-dev` | `arn:aws:iam::708819485463:policy/processapp-dynamodb-readwrite-dev` | Full read-write access |

These policies can be attached to:
- ✅ Individual IAM users
- ✅ IAM roles  
- ✅ IAM groups
- ✅ Federated users via role assumptions

---

## How to Grant Access

### Method 1: Attach Policy Directly to User (Easiest)

**For Read-Only Access:**
```bash
aws iam attach-user-policy \
  --user-name USERNAME \
  --policy-arn arn:aws:iam::708819485463:policy/processapp-dynamodb-readonly-dev \
  --profile ans-super
```

**For Read-Write Access:**
```bash
aws iam attach-user-policy \
  --user-name USERNAME \
  --policy-arn arn:aws:iam::708819485463:policy/processapp-dynamodb-readwrite-dev \
  --profile ans-super
```

**Via AWS Console:**
1. Go to **IAM Console** → **Users**
2. Select the user
3. Click **Add permissions** → **Attach policies directly**
4. Search for `processapp-dynamodb-readonly-dev` or `processapp-dynamodb-readwrite-dev`
5. Select the policy and click **Add permissions**

### Method 2: Use IAM Groups (For managing multiple users)

The stack also creates two IAM groups:

**Read-Only Group**: `processapp-dynamodb-readers-dev`
**Read-Write Group**: `processapp-dynamodb-writers-dev`

Add users to groups:
```bash
# Add to read-only group
aws iam add-user-to-group \
  --group-name processapp-dynamodb-readers-dev \
  --user-name USERNAME \
  --profile ans-super

# Add to read-write group
aws iam add-user-to-group \
  --group-name processapp-dynamodb-writers-dev \
  --user-name USERNAME \
  --profile ans-super
```

**Via AWS Console:**
1. Go to **IAM Console** → **User groups**
2. Select the appropriate group
3. Click **Add users** and select users

---

## Permissions Included

### Read-Only Policy (`processapp-dynamodb-readonly-dev`)

- ✅ `dynamodb:DescribeTable`
- ✅ `dynamodb:GetItem`
- ✅ `dynamodb:Query`
- ✅ `dynamodb:Scan`
- ✅ `dynamodb:DescribeTimeToLive`
- ✅ `dynamodb:ListTables`
- ✅ `kms:Decrypt` (read encrypted data)
- ✅ `kms:DescribeKey`
- ❌ No write or delete permissions

### Read-Write Policy (`processapp-dynamodb-readwrite-dev`)

- ✅ All read permissions (same as above)
- ✅ `dynamodb:PutItem` (create new items)
- ✅ `dynamodb:UpdateItem` (update existing items)
- ✅ `dynamodb:DeleteItem` (delete items)
- ✅ `dynamodb:BatchWriteItem` (bulk operations)
- ✅ `dynamodb:BatchGetItem` (bulk reads)
- ✅ `kms:Encrypt` (write encrypted data)
- ✅ `kms:GenerateDataKey` (encryption operations)

---

## Accessing the Table

Once permissions are granted, users can access the table:

1. Go to **DynamoDB Console** → **Tables**
2. Select the table: `dev-ExternalData`
3. Click **Explore table items** to view data
4. Use **Scan** or **Query** to search for specific items

### Reading Data (Both Policies)

1. Click **Explore table items**
2. Use **Scan** to read all items (warning: expensive for large tables)
3. Use **Query** to search by partition key

### Writing Data (Read-Write Policy Only)

Users with write permissions can also:

1. Click **Create item** to add a new record
2. Click **Actions** → **Edit item** to modify an existing record
3. Click **Actions** → **Delete item** to remove a record
4. Use **PartiQL editor** for advanced SQL-like operations

---

## Table Structure

**Table Name**: `dev-ExternalData`

**Primary Key**:
- **Partition Key**: `partitionKey` (String)
- **Sort Key**: `sortKey` (String)

**TTL Attribute**: `expirationTime` (automatically deletes expired items)

**Encryption**: Customer-managed KMS key (`alias/processapp-external-data-dev`)

---

## Example Queries

### Scan all items
- Go to **Explore table items**
- Click **Scan** (warning: this reads all items and may be expensive for large tables)

### Query by partition key
- Go to **Explore table items**
- Click **Query**
- Enter the partition key value
- Optionally add sort key conditions

### Query specific item
```
Partition key: <your-partition-key>
Sort key: <your-sort-key>
```

---

## Troubleshooting

### "User is not authorized to perform: kms:Decrypt"

The user doesn't have KMS permissions. Make sure the managed policy is attached to the user:

```bash
aws iam list-attached-user-policies --user-name USERNAME --profile ans-super
```

### "User is not authorized to perform: dynamodb:Scan"

The user doesn't have DynamoDB permissions. Verify the policy is attached:

```bash
aws iam list-attached-user-policies --user-name USERNAME --profile ans-super
```

### Can't see any data (encrypted values)

This usually means KMS permissions are missing. Double-check the policy is attached correctly.

---

## Stack Outputs

After deploying, the stack outputs the following values:

```bash
# Get the read-only policy ARN
aws cloudformation describe-stacks \
  --stack-name dev-PrereqsStack \
  --query "Stacks[0].Outputs[?OutputKey=='ReadOnlyPolicyArn'].OutputValue" \
  --output text \
  --profile ans-super

# Get the read-write policy ARN
aws cloudformation describe-stacks \
  --stack-name dev-PrereqsStack \
  --query "Stacks[0].Outputs[?OutputKey=='ReadWritePolicyArn'].OutputValue" \
  --output text \
  --profile ans-super

# Get the table name
aws cloudformation describe-stacks \
  --stack-name dev-PrereqsStack \
  --query "Stacks[0].Outputs[?OutputKey=='TableName'].OutputValue" \
  --output text \
  --profile ans-super
```

---

## Security Notes

### Read-Only Policy
- ✅ View, scan, query items only
- ✅ Scoped to specific table and KMS key
- ✅ CloudTrail logs all access for auditing
- ❌ Cannot create, modify, or delete items
- ❌ Cannot change table configuration

### Read-Write Policy
- ✅ Full CRUD operations (Create, Read, Update, Delete)
- ✅ Can use PartiQL editor for advanced queries
- ✅ CloudTrail logs all write operations
- ⚠️ **Use with caution**: Users can delete data
- ❌ Cannot change table configuration or delete the table

---

## Removing Access

To revoke access:

**Method 1: Detach Policy from User**
```bash
aws iam detach-user-policy \
  --user-name USERNAME \
  --policy-arn arn:aws:iam::708819485463:policy/processapp-dynamodb-readonly-dev \
  --profile ans-super
```

**Method 2: Remove from Group**
```bash
aws iam remove-user-from-group \
  --group-name processapp-dynamodb-readers-dev \
  --user-name USERNAME \
  --profile ans-super
```

**Via Console:**
1. Go to **IAM Console** → **Users**
2. Select the user
3. Go to **Permissions** tab
4. Find the policy and click **Remove**

---

**Last Updated**: 2026-05-08  
**Stack**: PrereqsStack  
**Related Files**:
- `infrastructure/lib/PrereqsStack.ts`
- `infrastructure/config/security.config.ts`

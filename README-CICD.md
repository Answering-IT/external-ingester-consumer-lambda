# CI/CD Pipeline

GitHub Actions workflows for automated testing and deployment.

## Workflows

### 1. Build.yml
**Trigger:** Push or PR to `main` branch

**Actions:**
- Format Python code with Black
- Lint with Flake8
- Run unit tests
- Build TypeScript
- CDK synth validation

### 2. Deploy.yml
**Trigger:** Push to `main` branch

**Deploys to:**
- Stage: `dev`
- Region: `us-east-1`
- Account: `708819485463`

### 3. Release.yml
**Trigger:** Push tag matching `v*`

**Logic:**
- Tag with `-rc[0-9]+` suffix → **Staging** (us-east-1)
- Tag without `-rc` suffix → **Production** (us-east-2)

## Usage

### Deploy to Dev
```bash
git push origin main
```

### Deploy to Staging
```bash
# Tag must have -rc suffix
git tag v1.0.0-rc1
git push origin v1.0.0-rc1
```

### Deploy to Production
```bash
# Tag must NOT have -rc suffix
git tag v1.0.0
git push origin v1.0.0
```

## Environment Configuration

Environments are configured in TypeScript files:

- **Dev:** `infrastructure/config/environments.ts` (DevConfig)
- **Staging:** `infrastructure/config/staging.ts` (StagingConfig)
- **Production:** `infrastructure/config/production.ts` (ProductionConfig)

The `app.ts` file automatically selects the correct configuration based on the `--context stage=<env>` parameter passed by the workflow.

## Required Secrets

Configure in GitHub repository settings:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

## Tag Examples

| Tag | Deploys To | Region |
|-----|-----------|--------|
| `v1.0.0-rc1` | Staging | us-east-1 |
| `v1.0.0-rc2` | Staging | us-east-1 |
| `v1.0.0` | Production | us-east-2 |
| `v1.2.3` | Production | us-east-2 |

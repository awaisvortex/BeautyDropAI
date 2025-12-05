# GitHub Actions CI/CD Setup Guide

This guide walks you through setting up automated deployment to Google Cloud Run using GitHub Actions.

## Overview

The CI/CD pipeline automatically:
1. **On Pull Requests**: Runs tests and linting
2. **On Push to Main**: Runs tests → Builds Docker image → Pushes to Artifact Registry → Deploys to Cloud Run

## Prerequisites

- Access to Google Cloud Project: `beautydrop-dev`
- GitHub repository admin access
- `gcloud` CLI installed locally

## Setup Instructions

### Step 1: Create GCP Service Account

```bash
# Set your project
gcloud config set project beautydrop-dev

# Create service account
gcloud iam service-accounts create github-actions-deployer \
  --display-name="GitHub Actions Deployer" \
  --description="Service account for GitHub Actions to deploy to Cloud Run"

# Get the email
SA_EMAIL=$(gcloud iam service-accounts list \
  --filter="displayName:GitHub Actions Deployer" \
  --format='value(email)')

echo "Service Account Email: $SA_EMAIL"
```

### Step 2: Grant Required Permissions

```bash
# Artifact Registry permissions (push images)
gcloud projects add-iam-policy-binding beautydrop-dev \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/artifactregistry.writer"

# Cloud Run permissions (deploy services)
gcloud projects add-iam-policy-binding beautydrop-dev \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.admin"

# Service Account User (required for Cloud Run)
gcloud projects add-iam-policy-binding beautydrop-dev \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/iam.serviceAccountUser"

# Storage permissions (if needed for static files)
gcloud projects add-iam-policy-binding beautydrop-dev \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.admin"
```

### Step 3: Create Service Account Key

```bash
# Create and download the key
gcloud iam service-accounts keys create github-actions-key.json \
  --iam-account="${SA_EMAIL}"

# Display the key (you'll copy this to GitHub)
cat github-actions-key.json
```

⚠️ **IMPORTANT**: Keep this key secure! It provides access to your GCP project.

### Step 4: Create GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions → New repository secret

Create these two secrets:

#### Secret 1: `GCP_SERVICE_ACCOUNT_KEY`

**Value**: Paste the entire contents of `github-actions-key.json`

```json
{
  "type": "service_account",
  "project_id": "beautydrop-dev",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "github-actions-deployer@beautydrop-dev.iam.gserviceaccount.com",
  ...
}
```

#### Secret 2: `CLOUD_RUN_ENV_YAML`

**Value**: Your Cloud Run environment variables in YAML format

```yaml
SECRET_KEY: "django-insecure-comp+hw+ao)$*3=g+)x-+l%lxh&"
DEBUG: "False"
ALLOWED_HOSTS: "*"
DJANGO_SETTINGS_MODULE: "config.settings.production"
DB_ENGINE: "django.db.backends.postgresql"
DB_NAME: "neondb"
DB_USER: "neondb_owner"
DB_PASSWORD: "npg_p3MxwQbULrC0"
DB_HOST: "ep-flat-sea-adm0k7ty-pooler.c-2.us-east-1.aws.neon.tech"
DB_PORT: "5432"
DB_SSLMODE: "require"
REDIS_URL: "redis://localhost:6379/0"
REDIS_HOST: "localhost"
REDIS_PORT: "6379"
CLERK_PUBLISHABLE_KEY: "pk_test_YWxpdmUtaG91bmQtMTYuY2xlcmsuYWNjb3VudHMuZGV2JA"
CLERK_SECRET_KEY: "sk_test_daV5yTHskpItSNpXHN6Fs7YnXqyoiZTQEJUB28jT0O"
CLERK_API_URL: "https://api.clerk.com/v1"
STRIPE_SECRET_KEY: "sk_test_51SY7XeDKMGdQKiWarFWtcK7m6HWlmFXC0q79LrlGYIXIbWFiykPax168DDjntLO7anxPTb1N6AdbSB1wAmGLJ0R200wjEfEwBe"
STRIPE_PUBLISHABLE_KEY: "pk_test_51SY7XeDKMGdQKiWaI1AoqhsC46wMli2GmmW7WR9bdpPreXghfusUUyLRevk0mLrO1y8TDWeP2pIIG4tdWe7r652w00Qhq3NoCn"
STRIPE_WEBHOOK_SECRET: ""
EMAIL_BACKEND: "django.core.mail.backends.console.EmailBackend"
EMAIL_HOST: "smtp.gmail.com"
EMAIL_PORT: "587"
EMAIL_USE_TLS: "True"
EMAIL_HOST_USER: "zeerak.abbas@artilence.com"
EMAIL_HOST_PASSWORD: "emllombahcjgqmjm"
DEFAULT_FROM_EMAIL: "noreply@beautydropai.com"
CORS_ALLOWED_ORIGINS: "http://localhost:3000,http://localhost:5173"
GOOGLE_CALENDAR_CLIENT_ID: "your-google-client-id"
GOOGLE_CALENDAR_CLIENT_SECRET: "your-google-client-secret"
```

⚠️ **NOTE**: Set `DEBUG: "False"` for production!

### Step 5: Clean Up Local Key

```bash
# IMPORTANT: Delete the local key file after uploading to GitHub
rm github-actions-key.json
```

### Step 6: Test the Pipeline

1. Create a test branch:
   ```bash
   git checkout -b test-ci-cd
   ```

2. Make a small change (e.g., add a comment to README)

3. Push and create a PR:
   ```bash
   git add .
   git commit -m "Test CI/CD pipeline"
   git push origin test-ci-cd
   ```

4. Check the Actions tab in GitHub to see tests running

5. Merge the PR to trigger deployment

## Pipeline Stages

### Stage 1: Test (runs on all PRs and pushes)
- ✅ Checkout code
- ✅ Install Python & Poetry
- ✅ Install dependencies
- ✅ Run linting (flake8, black)
- ✅ Run tests with coverage
- ✅ Upload coverage to Codecov (optional)

### Stage 2: Build & Deploy (runs only on main branch)
- ✅ Authenticate to GCP
- ✅ Build Docker image
- ✅ Tag with both `latest` and git SHA
- ✅ Push to Artifact Registry
- ✅ Deploy to Cloud Run with env vars
- ✅ Test deployment health endpoint

### Stage 3: Notify (runs after deploy)
- ✅ Print deployment status
- ✅ Show service URL

## Monitoring Deployments

### View Workflow Runs
Go to: https://github.com/awaisvortex/BeautyDropAI/actions

### Check Deployed Revision
```bash
gcloud run revisions list \
  --service beautydrop-api \
  --region us-east1 \
  --project beautydrop-dev
```

### View Logs
```bash
gcloud run services logs read beautydrop-api \
  --region us-east1 \
  --project beautydrop-dev \
  --limit 50
```

## Troubleshooting

### Issue: "Permission denied" errors

**Solution**: Verify service account has all required roles:
```bash
gcloud projects get-iam-policy beautydrop-dev \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:github-actions-deployer*"
```

### Issue: "Image not found" during deployment

**Solution**: Check if image was pushed to Artifact Registry:
```bash
gcloud artifacts docker images list \
  us-east1-docker.pkg.dev/beautydrop-dev/beautydrop-django/app \
  --include-tags
```

### Issue: Tests failing in CI but passing locally

**Solution**: Check Python version and dependencies:
- CI uses Python 3.13 (defined in workflow)
- Ensure `pyproject.toml` has all test dependencies in `[tool.poetry.group.dev.dependencies]`

### Issue: Environment variables not loading

**Solution**: Verify `CLOUD_RUN_ENV_YAML` secret:
- Must be valid YAML format
- Each key must be quoted
- Multi-line values must use proper YAML syntax

## Security Best Practices

1. **Rotate Service Account Keys**: Rotate every 90 days
   ```bash
   # Delete old keys
   gcloud iam service-accounts keys list --iam-account=$SA_EMAIL
   gcloud iam service-accounts keys delete KEY_ID --iam-account=$SA_EMAIL
   
   # Create new key and update GitHub secret
   gcloud iam service-accounts keys create new-key.json --iam-account=$SA_EMAIL
   ```

2. **Use Least Privilege**: Only grant necessary permissions

3. **Enable Branch Protection**: Require PR reviews before merging to main

4. **Monitor Access**: Regularly audit service account usage:
   ```bash
   gcloud logging read \
     "protoPayload.authenticationInfo.principalEmail=$SA_EMAIL" \
     --limit 50 \
     --format json
   ```

## Additional Features to Enable (Optional)

### Add Slack/Discord Notifications

Add a notification step:
```yaml
- name: Notify Slack
  if: always()
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

### Add Deployment Previews for PRs

Create a separate workflow that deploys PR branches to unique Cloud Run services for testing.

### Enable Rollback on Failure

Add a rollback step:
```yaml
- name: Rollback on failure
  if: failure()
  run: |
    gcloud run services update-traffic beautydrop-api \
      --to-revisions=PREVIOUS=100 \
      --region us-east1
```

## Support

For issues with the pipeline:
1. Check GitHub Actions logs
2. Review Cloud Run logs in GCP Console
3. Test deployment manually using `./deploy-latest.sh`

---

**Pipeline Status**: [![CI/CD](https://github.com/awaisvortex/BeautyDropAI/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/awaisvortex/BeautyDropAI/actions/workflows/ci-cd.yml)


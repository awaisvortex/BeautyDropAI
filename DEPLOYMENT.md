# BeautyDropAI - Deployment Guide

## Current Deployment Status

- **Service URL**: https://beautydrop-api-rbjcchnovq-ue.a.run.app
- **Latest Revision**: `beautydrop-api-00003-xul` 
- **Deployed**: December 5, 2025
- **Image Digest**: `sha256:ef85854ff1fb3a094bc1b81639fc5b6fa5449cf9318825e8b790e0cb5e0ddf25`
- **Code Base**: `main` branch (commit `bed03ac` - Stripe integration + Django admin)

## What's Deployed

The current deployment includes:
- Latest code from `main` branch with Stripe integration
- Django admin panel 
- Payment webhooks (Clerk + Stripe)
- Cloud Run PORT environment variable support
- All authentication, booking, schedule, and subscription features

## Manual Deployment Process

### Prerequisites
```bash
# Ensure you're authenticated
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud auth login --no-launch-browser

# Set correct project
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud config set project beautydrop-dev
```

### Step-by-Step Deployment

1. **Pull latest code**
   ```bash
   git checkout main
   git pull origin main
   ```

2. **Build Docker image**
   ```bash
   docker build -t beautydropai:latest .
   ```

3. **Tag for Artifact Registry**
   ```bash
   docker tag beautydropai:latest \
     us-east1-docker.pkg.dev/beautydrop-dev/beautydrop-django/app:latest
   ```

4. **Configure Docker authentication**
   ```bash
   CLOUDSDK_PYTHON=/usr/bin/python3 gcloud auth configure-docker us-east1-docker.pkg.dev
   ```

5. **Push to Artifact Registry**
   ```bash
   CLOUDSDK_PYTHON=/usr/bin/python3 docker push \
     us-east1-docker.pkg.dev/beautydrop-dev/beautydrop-django/app:latest
   ```

6. **Deploy to Cloud Run**
   ```bash
   ./deploy-latest.sh
   ```
   
   Or manually:
   ```bash
   CLOUDSDK_PYTHON=/usr/bin/python3 gcloud run deploy beautydrop-api \
     --image us-east1-docker.pkg.dev/beautydrop-dev/beautydrop-django/app:latest \
     --region us-east1 \
     --platform managed \
     --allow-unauthenticated \
     --memory 1Gi \
     --cpu 1 \
     --min-instances 0 \
     --max-instances 10 \
     --timeout 300 \
     --port 8080 \
     --env-vars-file cloudrun-env.yaml
   ```

### Verify Deployment

1. **Check deployed image**
   ```bash
   CLOUDSDK_PYTHON=/usr/bin/python3 gcloud run services describe beautydrop-api \
     --region us-east1 \
     --format='value(spec.template.spec.containers[0].image)'
   ```

2. **Test health endpoint**
   ```bash
   curl https://beautydrop-api-rbjcchnovq-ue.a.run.app/api/v1/auth/health/
   ```

3. **Check recent revisions**
   ```bash
   CLOUDSDK_PYTHON=/usr/bin/python3 gcloud run revisions list \
     --service beautydrop-api \
     --region us-east1 \
     --limit 5
   ```

## CI/CD (Planned)

GitHub Actions workflow exists at `.github/workflows/ci-cd.yml` but currently blocked due to GCP IAM restrictions. 

To enable:
1. Grant service account permissions:
   - `roles/artifactregistry.writer`
   - `roles/run.admin`
   - `roles/iam.serviceAccountUser`
2. Add GitHub secrets:
   - `GCP_SERVICE_ACCOUNT_KEY`
   - `CLOUD_RUN_ENV_FILE`

## Environment Variables

All environment variables are stored in `cloudrun-env.yaml` during deployment (auto-deleted after). Key variables:
- Database: Neon PostgreSQL (external)
- Redis: localhost (reports unhealthy, not critical)
- Clerk: Authentication & webhooks
- Stripe: Payment processing & webhooks
- Email: SMTP via Gmail

## Troubleshooting

### Authentication Errors
If you get `unauthorized: authentication failed`:
```bash
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud auth login --no-launch-browser
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud auth configure-docker us-east1-docker.pkg.dev
```

### Check What's Running
```bash
# Current image digest
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud artifacts docker images list \
  us-east1-docker.pkg.dev/beautydrop-dev/beautydrop-django/app \
  --include-tags

# Compare with local
docker images --digests beautydropai
```

### IAM Permission Issues
The deployment warning about `Setting IAM policy failed` is expected. Public access works despite the warning. To fix:
```bash
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud run services add-iam-policy-binding beautydrop-api \
  --region us-east1 \
  --member="allUsers" \
  --role="roles/run.invoker"
```

## Notes

- Python 3.13.7 is used in Docker image
- Poetry manages dependencies (see `pyproject.toml`)
- `CLOUDSDK_PYTHON=/usr/bin/python3` required due to gcloud/Python 3.13 compatibility
- Redis connection fails (localhost) but app works without it
- Dockerfile respects `$PORT` environment variable for Cloud Run


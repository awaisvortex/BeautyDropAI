# CI/CD Quick Start Guide

## ⚠️ Prerequisites

Your GCP account needs **admin permissions** to set up CI/CD. If you see permission errors, see [`CI_CD_SETUP_NEEDED.md`](CI_CD_SETUP_NEEDED.md) for alternatives.

## 🚀 One-Command Setup (Requires Admin)

### Option 1: Workload Identity Federation (Recommended - No Keys!)

```bash
cd /Users/softwareengineer-frontend/Desktop/BeautyDropAI
CLOUDSDK_PYTHON=/usr/bin/python3 ./scripts/setup-workload-identity.sh
```

This will output three GitHub secrets you need to add.

### Option 2: Service Account Keys (Fallback)

```bash
cd /Users/softwareengineer-frontend/Desktop/BeautyDropAI
./scripts/setup-cicd.sh
```

This will:
1. Create GCP service account: `github-actions-deployer`
2. Grant all required permissions
3. Generate `github-actions-key.json`
4. Create `cloudrun-env-template.yaml` template

⚠️ **Note**: Your organization may block service account key creation for security

## 📝 Add GitHub Secrets (Required)

Go to: https://github.com/awaisvortex/BeautyDropAI/settings/secrets/actions

### For Workload Identity (Option 1)

**Secret 1: `WIF_PROVIDER`**
```
projects/497422674710/locations/global/workloadIdentityPools/github-actions-pool/providers/github-provider
```
(Get this from the setup script output)

**Secret 2: `WIF_SERVICE_ACCOUNT`**
```
github-actions-deployer@beautydrop-dev.iam.gserviceaccount.com
```

**Secret 3: `CLOUD_RUN_ENV_YAML`**

### For Service Account Keys (Option 2)

**Secret 1: `GCP_SERVICE_ACCOUNT_KEY`**
```bash
# Copy the entire JSON output from the script
cat github-actions-key.json
```
Paste as GitHub secret value.

**Secret 2: `CLOUD_RUN_ENV_YAML`**

### Environment Variables (Both Options)
```yaml
# Use your actual production values (YAML format)
SECRET_KEY: "your-production-secret"
DEBUG: "False"
ALLOWED_HOSTS: "*"
DJANGO_SETTINGS_MODULE: "config.settings.production"
DB_NAME: "neondb"
DB_USER: "neondb_owner"
DB_PASSWORD: "npg_p3MxwQbULrC0"
DB_HOST: "ep-flat-sea-adm0k7ty-pooler.c-2.us-east-1.aws.neon.tech"
DB_PORT: "5432"
DB_SSLMODE: "require"
REDIS_URL: "redis://localhost:6379/0"
REDIS_HOST: "localhost"
REDIS_PORT: "6379"
CLERK_PUBLISHABLE_KEY: "pk_test_..."
CLERK_SECRET_KEY: "sk_test_..."
CLERK_API_URL: "https://api.clerk.com/v1"
STRIPE_SECRET_KEY: "sk_test_..."
STRIPE_PUBLISHABLE_KEY: "pk_test_..."
STRIPE_WEBHOOK_SECRET: ""
EMAIL_BACKEND: "django.core.mail.backends.console.EmailBackend"
EMAIL_HOST: "smtp.gmail.com"
EMAIL_PORT: "587"
EMAIL_USE_TLS: "True"
EMAIL_HOST_USER: "your-email@example.com"
EMAIL_HOST_PASSWORD: "your-app-password"
DEFAULT_FROM_EMAIL: "noreply@beautydropai.com"
CORS_ALLOWED_ORIGINS: "http://localhost:3000,http://localhost:5173"
GOOGLE_CALENDAR_CLIENT_ID: "your-google-client-id"
GOOGLE_CALENDAR_CLIENT_SECRET: "your-google-client-secret"
```

⚠️ **IMPORTANT**: 
- Set `DEBUG: "False"` for production
- Use production Clerk/Stripe keys (replace `test` with `live`)
- Update CORS origins to your actual frontend domain

## 🧪 Test the Pipeline

```bash
# 1. Create test branch
git checkout -b test-cicd

# 2. Make a small change
echo "# CI/CD Test" >> README.md

# 3. Commit and push
git add .
git commit -m "test: CI/CD pipeline"
git push origin test-cicd

# 4. Watch in GitHub Actions
# https://github.com/awaisvortex/BeautyDropAI/actions

# 5. Create PR and merge to main
```

## 🔄 How It Works

### On Pull Request → Runs Tests Only
- Linting (flake8, black)
- Unit tests with coverage
- No deployment

### On Push to Main → Full Deployment
1. Run all tests
2. Build Docker image (tagged with git SHA + `latest`)
3. Push to Artifact Registry
4. Deploy to Cloud Run
5. Test health endpoint
6. Report status

## 🔍 Monitor Deployments

### View Active Workflow
```bash
open https://github.com/awaisvortex/BeautyDropAI/actions
```

### Check Cloud Run Revisions
```bash
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud run revisions list \
  --service beautydrop-api \
  --region us-east1 \
  --project beautydrop-dev
```

### View Deployment Logs
```bash
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud run services logs read beautydrop-api \
  --region us-east1 \
  --project beautydrop-dev \
  --limit 50
```

## ⚡ Manual Deployment (If CI/CD Blocked)

If GitHub Actions can't run due to permissions, use:

```bash
cd /Users/softwareengineer-frontend/Desktop/BeautyDropAI
./deploy-latest.sh
```

This replicates what the CI/CD pipeline does automatically.

## 🔒 Cleanup

After adding secrets to GitHub:
```bash
# Delete local key file (contains sensitive credentials)
rm github-actions-key.json cloudrun-env-template.yaml
```

## 📊 Expected Pipeline Duration

- **Tests only (PRs)**: ~3-5 minutes
- **Full deployment (main)**: ~5-8 minutes
  - Tests: 2-3 min
  - Docker build: 1-2 min
  - Push to registry: 1-2 min
  - Cloud Run deploy: 1-2 min

## 🎯 Success Criteria

After setup, you should see:
1. ✅ Green checkmark on PRs after tests pass
2. ✅ Automatic deployment on main branch
3. ✅ Service URL responds with healthy status
4. ✅ New revision visible in Cloud Run console

---

**Need Help?** See detailed guide: `.github/workflows/README.md`


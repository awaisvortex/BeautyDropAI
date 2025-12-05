# ⚠️ CI/CD Setup Requires Admin Access

Your GCP organization has security policies that prevent:
1. ❌ Service account key creation (`constraints/iam.disableServiceAccountKeyCreation`)
2. ❌ IAM policy modifications (requires `setIamPolicy` permission)
3. ❌ Workload Identity Pool creation (requires `iam.workloadIdentityPools.create`)

**Current account**: `afaq@vortexnow.ai` doesn't have these permissions.

## 🔧 What Needs to Be Done

Someone with **Owner** or **Organization Admin** role needs to complete this setup.

---

## Option 1: Workload Identity Federation (Recommended - No Keys!)

This is the most secure method and doesn't require downloading any keys.

### Steps for Admin to Run:

```bash
# Run this script with admin account
cd /Users/softwareengineer-frontend/Desktop/BeautyDropAI
CLOUDSDK_PYTHON=/usr/bin/python3 ./scripts/setup-workload-identity.sh
```

This will output three values to add as GitHub secrets:
- `WIF_PROVIDER` 
- `WIF_SERVICE_ACCOUNT`
- `CLOUD_RUN_ENV_YAML` (you create this - see below)

### GitHub Secrets to Add

Go to: https://github.com/awaisvortex/BeautyDropAI/settings/secrets/actions

**Secret 1: `WIF_PROVIDER`**
```
projects/497422674710/locations/global/workloadIdentityPools/github-actions-pool/providers/github-provider
```
(Admin will give you this value)

**Secret 2: `WIF_SERVICE_ACCOUNT`**
```
github-actions-deployer@beautydrop-dev.iam.gserviceaccount.com
```

**Secret 3: `CLOUD_RUN_ENV_YAML`**
```yaml
SECRET_KEY: "your-production-secret-key"
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

⚠️ **Update for Production**: Change `DEBUG` to `False` and use production keys!

---

## Option 2: Service Account Key (If Workload Identity Not Available)

If your admin can't set up Workload Identity, they need to:

1. **Temporarily disable the org policy** that blocks key creation
2. **Create a key** for the existing service account:
   ```bash
   gcloud iam service-accounts keys create github-actions-key.json \
     --iam-account=github-actions-deployer@beautydrop-dev.iam.gserviceaccount.com
   ```
3. **Add the key as GitHub secret** `GCP_SERVICE_ACCOUNT_KEY`
4. **Update the workflow** to use keys instead of Workload Identity

---

## 🚨 Until CI/CD is Set Up

Use manual deployment:

```bash
cd /Users/softwareengineer-frontend/Desktop/BeautyDropAI

# Pull latest code
git checkout main
git pull origin main

# Deploy
./deploy-latest.sh
```

This script will:
1. Prompt for gcloud authentication (if needed)
2. Build Docker image from latest code
3. Push to Artifact Registry
4. Deploy to Cloud Run
5. Show the service URL

---

## ✅ Current Manual Deployment Works

Your current setup works perfectly for manual deployments:
- ✅ Docker image builds successfully
- ✅ Pushes to Artifact Registry (when authenticated)
- ✅ Deploys to Cloud Run
- ✅ Service is live: https://beautydrop-api-rbjcchnovq-ue.a.run.app

**You can keep using manual deployments until admin access is available for CI/CD.**

---

## 📞 Ask Your Admin To:

Forward them this file and ask them to run:

```bash
# Option 1 (Recommended): Set up Workload Identity
cd /path/to/BeautyDropAI
./scripts/setup-workload-identity.sh

# Then share the WIF_PROVIDER and WIF_SERVICE_ACCOUNT values

# Option 2: Generate service account key
gcloud iam service-accounts keys create github-actions-key.json \
  --iam-account=github-actions-deployer@beautydrop-dev.iam.gserviceaccount.com

# Then share the github-actions-key.json contents
```

---

## 🎯 What You Can Do Right Now

1. ✅ **Deploy manually** using `./deploy-latest.sh` (works now)
2. ✅ **Test your API** at the Cloud Run URL
3. ✅ **Commit CI/CD files** to your repo (already done)
4. ⏳ **Wait for admin** to run the setup script
5. 🎉 **Add GitHub secrets** once admin provides them

Once secrets are added, every push to `main` will auto-deploy! 🚀


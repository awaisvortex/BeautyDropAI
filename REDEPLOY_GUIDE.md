# 🚀 Quick Redeploy Guide

Use this guide whenever you want to deploy new code to Cloud Run.

---

## ⚡ One-Command Deploy

```bash
cd /Users/softwareengineer-frontend/Desktop/BeautyDropAI && ./deploy-latest.sh
```

**That's it!** The script does everything automatically.

---

## 📋 Manual Step-by-Step (If Script Fails)

### Prerequisites Check
```bash
# 1. Check you're authenticated
gcloud auth list

# 2. Check Docker is running
docker ps

# 3. Check current branch
git branch --show-current
```

### Deployment Steps

**Step 1: Get Latest Code**
```bash
cd /Users/softwareengineer-frontend/Desktop/BeautyDropAI
git checkout main
git pull origin main
```

**Step 2: Build Docker Image**
```bash
docker build -t beautydropai:latest .
```
⏱️ Takes ~2-3 minutes

**Step 3: Tag for Artifact Registry**
```bash
docker tag beautydropai:latest \
  us-east1-docker.pkg.dev/beautydrop-dev/beautydrop-django/app:latest
```

**Step 4: Configure Docker Auth (if needed)**
```bash
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud auth configure-docker us-east1-docker.pkg.dev --quiet
```

**Step 5: Push to Registry**
```bash
CLOUDSDK_PYTHON=/usr/bin/python3 docker push \
  us-east1-docker.pkg.dev/beautydrop-dev/beautydrop-django/app:latest
```
⏱️ Takes ~2-3 minutes (uploading ~650MB)

**Step 6: Create Environment File**
```bash
cat > cloudrun-env.yaml <<'EOF'
SECRET_KEY: "django-insecure-comp+hw+ao)$*3=g+)x-+l%lxh&"
DEBUG: "True"
ALLOWED_HOSTS: "*"
DJANGO_SETTINGS_MODULE: "config.settings.development"
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
EOF
```

**Step 7: Deploy to Cloud Run**
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
  --env-vars-file cloudrun-env.yaml \
  --project beautydrop-dev
```
⏱️ Takes ~1-2 minutes

**Step 8: Cleanup**
```bash
rm cloudrun-env.yaml
```

**Step 9: Verify**
```bash
# Check deployment
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud run services describe beautydrop-api \
  --region us-east1 \
  --format='value(spec.template.spec.containers[0].image)'

# Test health endpoint
curl https://beautydrop-api-497422674710.us-east1.run.app/api/v1/auth/health/
```

---

## ⏱️ Expected Timeline

| Step | Duration | What's Happening |
|------|----------|------------------|
| Pull code | 5-10 sec | Getting latest changes |
| Docker build | 2-3 min | Creating container image |
| Tag image | <1 sec | Preparing for upload |
| Push to registry | 2-3 min | Uploading 650MB |
| Deploy to Cloud Run | 1-2 min | Rolling out new revision |
| **TOTAL** | **~5-7 minutes** | From code to production |

---

## 🔍 Verify Deployment

After deployment completes, check:

**1. Health Endpoint**
```bash
curl https://beautydrop-api-497422674710.us-east1.run.app/api/v1/auth/health/
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2025-12-05T...",
  "database": "healthy",
  "cache": "unhealthy: ..."  ← Expected if Redis not set up
}
```

**2. API Docs** (open in browser)
```bash
open https://beautydrop-api-497422674710.us-east1.run.app/api/docs/
```

**3. Recent Revisions**
```bash
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud run revisions list \
  --service beautydrop-api \
  --region us-east1 \
  --limit 3
```

**4. Service Logs** (check for errors)
```bash
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud run services logs read beautydrop-api \
  --region us-east1 \
  --limit 30
```

---

## 🔧 Troubleshooting

### Problem: "Authentication required"

**Solution**: Re-authenticate
```bash
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud auth login --no-launch-browser
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud config set project beautydrop-dev
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud auth configure-docker us-east1-docker.pkg.dev
```

### Problem: "Docker daemon not running"

**Solution**: Start Docker Desktop
```bash
open -a Docker
# Wait 30 seconds, then try again
```

### Problem: "No space left on device"

**Solution**: Clean up old Docker images
```bash
# Remove old images
docker image prune -a

# See disk usage
docker system df
```

### Problem: "Port 8080 not responding"

**Solution**: Check your Dockerfile uses `$PORT`
```dockerfile
CMD ["sh", "-c", "python manage.py runserver 0.0.0.0:${PORT:-8000}"]
```

### Problem: "Module not found" errors in logs

**Solution**: Rebuild without cache
```bash
docker build --no-cache -t beautydropai:latest .
```

### Problem: Push is taking too long

**Tip**: Push happens in background, you'll see progress by layer:
```
Pushing layer 1/10
Pushing layer 2/10
...
```
Just wait, it's uploading ~650MB.

---

## 📝 Quick Reference

### Check What's Deployed
```bash
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud run services describe beautydrop-api \
  --region us-east1 \
  --format='value(status.url,status.latestCreatedRevisionName,spec.template.spec.containers[0].image)'
```

### Check Local Images
```bash
docker images beautydropai
docker images us-east1-docker.pkg.dev/beautydrop-dev/beautydrop-django/app
```

### Check Artifact Registry
```bash
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud artifacts docker images list \
  us-east1-docker.pkg.dev/beautydrop-dev/beautydrop-django/app \
  --include-tags
```

### Rollback to Previous Revision
```bash
# List revisions
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud run revisions list \
  --service beautydrop-api \
  --region us-east1

# Rollback to specific revision
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud run services update-traffic beautydrop-api \
  --to-revisions REVISION_NAME=100 \
  --region us-east1
```

---

## 🎯 Common Workflows

### Deploy Latest Code from Main
```bash
cd /Users/softwareengineer-frontend/Desktop/BeautyDropAI
./deploy-latest.sh
```

### Deploy Specific Branch (Testing)
```bash
cd /Users/softwareengineer-frontend/Desktop/BeautyDropAI
git checkout feature-branch
git pull origin feature-branch

# Build with branch tag
docker build -t beautydropai:feature-test .
docker tag beautydropai:feature-test \
  us-east1-docker.pkg.dev/beautydrop-dev/beautydrop-django/app:feature-test

# Push
CLOUDSDK_PYTHON=/usr/bin/python3 docker push \
  us-east1-docker.pkg.dev/beautydrop-dev/beautydrop-django/app:feature-test

# Deploy (change service name or use --tag for testing)
# ... create cloudrun-env.yaml ...
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud run deploy beautydrop-api-test \
  --image us-east1-docker.pkg.dev/beautydrop-dev/beautydrop-django/app:feature-test \
  --region us-east1 \
  --env-vars-file cloudrun-env.yaml
```

### Check Deployment Logs Live
```bash
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud run services logs tail beautydrop-api \
  --region us-east1
```
Press Ctrl+C to stop.

---

## ✅ Pre-Deployment Checklist

Before deploying to production:

- [ ] Code tested locally
- [ ] All tests passing (`poetry run pytest`)
- [ ] Database migrations created (`python manage.py makemigrations`)
- [ ] `.env` file up to date
- [ ] No secrets in code (check git diff)
- [ ] Docker builds successfully
- [ ] Branch is up to date with main

---

## 🚨 Emergency: Quick Rollback

If deployment breaks production:

```bash
# 1. List recent revisions
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud run revisions list \
  --service beautydrop-api \
  --region us-east1 \
  --limit 5

# 2. Find the last working revision (e.g., beautydrop-api-00002-abc)

# 3. Rollback instantly
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud run services update-traffic beautydrop-api \
  --to-revisions beautydrop-api-00002-abc=100 \
  --region us-east1
```

This redirects 100% traffic to the old revision in ~10 seconds.

---

## 📱 Save These Commands

**Add to your terminal aliases** (optional):

```bash
# Add to ~/.zshrc
alias bd-deploy="cd /Users/softwareengineer-frontend/Desktop/BeautyDropAI && ./deploy-latest.sh"
alias bd-logs="CLOUDSDK_PYTHON=/usr/bin/python3 gcloud run services logs tail beautydrop-api --region us-east1"
alias bd-status="CLOUDSDK_PYTHON=/usr/bin/python3 gcloud run services describe beautydrop-api --region us-east1 --format='value(status.url,status.latestCreatedRevisionName)'"
alias bd-health="curl https://beautydrop-api-497422674710.us-east1.run.app/api/v1/auth/health/"

# Then reload
source ~/.zshrc

# Now you can use:
bd-deploy    # Deploy
bd-logs      # View logs
bd-status    # Check status
bd-health    # Test health
```

---

## 🎓 Tips & Best Practices

1. **Always pull before deploy**: `git pull origin main`
2. **Test locally first**: `docker run` your image locally
3. **Check logs after deploy**: Make sure no errors
4. **Deploy during low traffic**: If possible
5. **Keep old revisions**: Cloud Run keeps them for rollback
6. **Tag important releases**: `git tag v1.0.0 && git push --tags`

---

## 📞 Need Help?

- **Deployment docs**: `DEPLOYMENT.md`
- **CI/CD setup**: `CI_CD_QUICKSTART.md`
- **Current status**: `DEPLOYMENT_STATUS.md`
- **Full README**: `README.md`

---

**Remember**: The script `./deploy-latest.sh` does all of this automatically! 🚀


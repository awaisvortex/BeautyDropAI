#!/bin/bash
# Deploy script for BeautyDropAI to Cloud Run

set -e

echo "🔐 Step 1: Authenticating with Google Cloud..."
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud auth login --no-launch-browser

echo "✅ Logged in successfully"
echo ""

echo "🔧 Step 2: Setting project..."
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud config set project beautydrop-dev

echo "🔑 Step 3: Configuring Docker..."
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud auth configure-docker us-east1-docker.pkg.dev

echo "📦 Step 4: Pushing image to Artifact Registry..."
CLOUDSDK_PYTHON=/usr/bin/python3 docker push us-east1-docker.pkg.dev/beautydrop-dev/beautydrop-django/app:latest

echo "☁️  Step 5: Creating Cloud Run env file..."
cat > cloudrun-env.yaml <<'ENVEOF'
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
CORS_ALLOWED_ORIGINS: "http://localhost:3000,http://localhost:5173,https://beautydrop-frontend-497422674710.us-east1.run.app"
FRONTEND_URL: "https://beautydrop-frontend-497422674710.us-east1.run.app"
GOOGLE_CALENDAR_CLIENT_ID: "your-google-client-id"
GOOGLE_CALENDAR_CLIENT_SECRET: "your-google-client-secret"
ENVEOF

echo "🚀 Step 6: Deploying to Cloud Run..."
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

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🔍 Verifying deployment..."
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud run services describe beautydrop-api \
  --region us-east1 \
  --format='value(status.url)'

echo ""
echo "🧹 Cleaning up..."
rm cloudrun-env.yaml

echo ""
echo "🎉 All done!"


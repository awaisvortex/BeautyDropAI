#!/bin/bash
set -euo pipefail

echo "🚀 BeautyDrop AI - Manual STAGING Deployment Script"
echo "=================================================="
echo ""

# Configuration
PROJECT_ID="beautydrop-dev"
REGION="us-east1"
SERVICE_NAME="beautydrop-api-staging"
IMAGE_NAME="us-east1-docker.pkg.dev/${PROJECT_ID}/beautydrop-django/app-staging:latest"

# Step 1: Pull latest code from staging
echo "📥 Step 1: Pulling latest code from staging branch..."
git checkout staging
git pull origin staging
echo "✅ Code updated"
echo ""

# Step 2: Build Docker image
echo "🔨 Step 2: Building Docker image..."
docker build -t "${IMAGE_NAME}" .
echo "✅ Image built"
echo ""

# Step 3: Push to Artifact Registry
echo "📤 Step 3: Pushing image to Artifact Registry..."
# Note: Using gcloud as the credential helper is expected to be configured
docker push "${IMAGE_NAME}"
echo "✅ Image pushed"
echo ""

# Step 4: Deploy to Cloud Run (Staging)
echo "☁️  Step 4: Deploying to Cloud Run Staging..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE_NAME}" \
  --region "${REGION}" \
  --platform managed \
  --project "${PROJECT_ID}" \
  --set-env-vars "DJANGO_SETTINGS_MODULE=config.settings.production"
echo "✅ Deployed"
echo ""

# Step 5: Get service URL
echo "🌐 Step 5: Getting service URL..."
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --format='value(status.url)')
echo "✅ Service URL: ${SERVICE_URL}"
echo ""

# Step 6: Test health endpoint
echo "🏥 Step 6: Testing health endpoint..."
curl -s "${SERVICE_URL}/api/v1/auth/health/" | python3 -m json.tool || echo "⚠️ Could not parse health response as JSON"
echo ""
echo ""

echo "🎉 Staging deployment completed successfully!"
echo "=================================================="

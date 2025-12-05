#!/bin/bash
set -euo pipefail

echo "🚀 BeautyDrop AI - Manual Deployment Script"
echo "============================================"
echo ""

# Configuration
PROJECT_ID="beautydrop-dev"
REGION="us-east1"
SERVICE_NAME="beautydrop-api"
IMAGE_NAME="us-east1-docker.pkg.dev/${PROJECT_ID}/beautydrop-django/app:latest"

# Step 1: Pull latest code
echo "📥 Step 1: Pulling latest code from main branch..."
git checkout main
git pull origin main
echo "✅ Code updated"
echo ""

# Step 2: Build Docker image
echo "🔨 Step 2: Building Docker image..."
docker build -t "${IMAGE_NAME}" .
echo "✅ Image built"
echo ""

# Step 3: Push to Artifact Registry
echo "📤 Step 3: Pushing image to Artifact Registry..."
CLOUDSDK_PYTHON=/usr/bin/python3 docker push "${IMAGE_NAME}"
echo "✅ Image pushed"
echo ""

# Step 4: Deploy to Cloud Run
echo "☁️  Step 4: Deploying to Cloud Run..."
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE_NAME}" \
  --region "${REGION}" \
  --platform managed \
  --project "${PROJECT_ID}"
echo "✅ Deployed"
echo ""

# Step 5: Get service URL
echo "🌐 Step 5: Getting service URL..."
SERVICE_URL=$(CLOUDSDK_PYTHON=/usr/bin/python3 gcloud run services describe "${SERVICE_NAME}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --format='value(status.url)')
echo "✅ Service URL: ${SERVICE_URL}"
echo ""

# Step 6: Test health endpoint
echo "🏥 Step 6: Testing health endpoint..."
curl -s "${SERVICE_URL}/api/v1/auth/health/" | python3 -m json.tool
echo ""
echo ""

echo "🎉 Deployment completed successfully!"
echo "============================================"


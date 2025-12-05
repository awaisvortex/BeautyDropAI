#!/bin/bash
# Setup Workload Identity Federation for GitHub Actions (No keys needed!)

set -e

PROJECT_ID="beautydrop-dev"
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
REPO_OWNER="awaisvortex"
REPO_NAME="BeautyDropAI"
POOL_NAME="github-actions-pool"
PROVIDER_NAME="github-provider"
SA_NAME="github-actions-deployer"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "🔐 Setting up Workload Identity Federation for GitHub Actions"
echo "=============================================================="
echo ""
echo "Project: $PROJECT_ID ($PROJECT_NUMBER)"
echo "Repository: $REPO_OWNER/$REPO_NAME"
echo ""

# Enable required APIs
echo "📡 Enabling required APIs..."
gcloud services enable iamcredentials.googleapis.com --project=$PROJECT_ID
gcloud services enable cloudresourcemanager.googleapis.com --project=$PROJECT_ID
gcloud services enable sts.googleapis.com --project=$PROJECT_ID
echo "✅ APIs enabled"
echo ""

# Create Workload Identity Pool
echo "🏊 Creating Workload Identity Pool..."
if gcloud iam workload-identity-pools describe $POOL_NAME \
  --location=global \
  --project=$PROJECT_ID &> /dev/null; then
  echo "⚠️  Pool already exists. Skipping creation."
else
  gcloud iam workload-identity-pools create $POOL_NAME \
    --location=global \
    --display-name="GitHub Actions Pool" \
    --project=$PROJECT_ID
  echo "✅ Pool created"
fi
echo ""

# Create Workload Identity Provider for GitHub
echo "🔗 Creating GitHub OIDC Provider..."
if gcloud iam workload-identity-pools providers describe $PROVIDER_NAME \
  --location=global \
  --workload-identity-pool=$POOL_NAME \
  --project=$PROJECT_ID &> /dev/null; then
  echo "⚠️  Provider already exists. Skipping creation."
else
  gcloud iam workload-identity-pools providers create-oidc $PROVIDER_NAME \
    --location=global \
    --workload-identity-pool=$POOL_NAME \
    --display-name="GitHub Provider" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
    --attribute-condition="assertion.repository_owner=='${REPO_OWNER}'" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --project=$PROJECT_ID
  echo "✅ Provider created"
fi
echo ""

# Create Service Account (if doesn't exist)
echo "👤 Creating service account..."
if gcloud iam service-accounts describe $SA_EMAIL --project=$PROJECT_ID &> /dev/null; then
  echo "⚠️  Service account already exists. Skipping creation."
else
  gcloud iam service-accounts create $SA_NAME \
    --display-name="GitHub Actions Deployer" \
    --description="Service account for GitHub Actions via Workload Identity" \
    --project=$PROJECT_ID
  echo "✅ Service account created"
fi
echo ""

# Grant permissions to service account
echo "🔐 Granting IAM roles to service account..."

ROLES=(
  "roles/artifactregistry.writer"
  "roles/run.admin"
  "roles/iam.serviceAccountUser"
  "roles/storage.admin"
)

for ROLE in "${ROLES[@]}"; do
  echo "  → $ROLE"
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="$ROLE" \
    --condition=None \
    --quiet || echo "    (may already have this role)"
done

echo "✅ Service account permissions configured"
echo ""

# Allow GitHub Actions to impersonate the service account
echo "🔗 Binding Workload Identity to service account..."
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/attribute.repository/${REPO_OWNER}/${REPO_NAME}" \
  --project=$PROJECT_ID

echo "✅ Workload Identity binding complete"
echo ""

# Generate the provider resource name
WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/providers/${PROVIDER_NAME}"

echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "📋 Add these GitHub Secrets:"
echo "----------------------------"
echo ""
echo "1. Secret Name: WIF_PROVIDER"
echo "   Value:"
echo "   $WIF_PROVIDER"
echo ""
echo "2. Secret Name: WIF_SERVICE_ACCOUNT"
echo "   Value:"
echo "   $SA_EMAIL"
echo ""
echo "3. Secret Name: CLOUD_RUN_ENV_YAML"
echo "   Value: (Your Cloud Run environment variables in YAML format)"
echo "   See cloudrun-env-template.yaml for format"
echo ""
echo "🌐 Add them at:"
echo "   https://github.com/${REPO_OWNER}/${REPO_NAME}/settings/secrets/actions"
echo ""
echo "🎉 No service account keys needed!"
echo "   Workload Identity Federation is more secure than keys."
echo ""
echo "📚 Documentation:"
echo "   - CI/CD workflow: .github/workflows/ci-cd.yml"
echo "   - Quick start: CI_CD_QUICKSTART.md"
echo ""


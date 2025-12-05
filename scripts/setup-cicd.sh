#!/bin/bash
# Setup script for GitHub Actions CI/CD

set -e

PROJECT_ID="beautydrop-dev"
SA_NAME="github-actions-deployer"
KEY_FILE="github-actions-key.json"

echo "🚀 BeautyDropAI CI/CD Setup Script"
echo "===================================="
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI is not installed. Please install it first:"
    echo "   https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if user is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "@"; then
    echo "❌ Not authenticated with gcloud. Please run:"
    echo "   gcloud auth login"
    exit 1
fi

echo "✅ gcloud CLI is authenticated"
echo ""

# Set project
echo "📋 Setting project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

# Create service account
echo "👤 Creating service account: $SA_NAME..."
if gcloud iam service-accounts describe ${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com &> /dev/null; then
    echo "⚠️  Service account already exists. Skipping creation."
else
    gcloud iam service-accounts create $SA_NAME \
      --display-name="GitHub Actions Deployer" \
      --description="Service account for GitHub Actions to deploy to Cloud Run"
    echo "✅ Service account created"
fi

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
echo "📧 Service Account: $SA_EMAIL"
echo ""

# Grant permissions
echo "🔐 Granting IAM roles..."

echo "  → Artifact Registry Writer..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/artifactregistry.writer" \
  --condition=None \
  --quiet

echo "  → Cloud Run Admin..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.admin" \
  --condition=None \
  --quiet

echo "  → Service Account User..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/iam.serviceAccountUser" \
  --condition=None \
  --quiet

echo "  → Storage Admin (optional)..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.admin" \
  --condition=None \
  --quiet

echo "✅ All permissions granted"
echo ""

# Create key
echo "🔑 Creating service account key..."
if [ -f "$KEY_FILE" ]; then
    echo "⚠️  Key file already exists. Deleting old key..."
    rm $KEY_FILE
fi

gcloud iam service-accounts keys create $KEY_FILE \
  --iam-account="${SA_EMAIL}"

echo "✅ Key created: $KEY_FILE"
echo ""

# Display the key
echo "📋 Copy this JSON key to GitHub Secrets as 'GCP_SERVICE_ACCOUNT_KEY':"
echo "================================================================"
cat $KEY_FILE
echo ""
echo "================================================================"
echo ""

# Create env file template
echo "📝 Creating Cloud Run env template..."
cat > cloudrun-env-template.yaml <<'EOF'
# Copy this to GitHub Secrets as 'CLOUD_RUN_ENV_YAML'
# Update values as needed for production

SECRET_KEY: "your-production-secret-key"
DEBUG: "False"
ALLOWED_HOSTS: "*"
DJANGO_SETTINGS_MODULE: "config.settings.production"
DB_ENGINE: "django.db.backends.postgresql"
DB_NAME: "neondb"
DB_USER: "neondb_owner"
DB_PASSWORD: "your-db-password"
DB_HOST: "your-db-host.neon.tech"
DB_PORT: "5432"
DB_SSLMODE: "require"
REDIS_URL: "redis://your-redis-host:6379/0"
REDIS_HOST: "your-redis-host"
REDIS_PORT: "6379"
CLERK_PUBLISHABLE_KEY: "pk_live_..."
CLERK_SECRET_KEY: "sk_live_..."
CLERK_API_URL: "https://api.clerk.com/v1"
STRIPE_SECRET_KEY: "sk_live_..."
STRIPE_PUBLISHABLE_KEY: "pk_live_..."
STRIPE_WEBHOOK_SECRET: "whsec_..."
EMAIL_BACKEND: "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST: "smtp.gmail.com"
EMAIL_PORT: "587"
EMAIL_USE_TLS: "True"
EMAIL_HOST_USER: "your-email@example.com"
EMAIL_HOST_PASSWORD: "your-app-password"
DEFAULT_FROM_EMAIL: "noreply@beautydropai.com"
CORS_ALLOWED_ORIGINS: "https://your-frontend.com"
GOOGLE_CALENDAR_CLIENT_ID: "your-google-client-id"
GOOGLE_CALENDAR_CLIENT_SECRET: "your-google-client-secret"
EOF

echo "✅ Template created: cloudrun-env-template.yaml"
echo ""

echo "📋 Next Steps:"
echo "=============="
echo ""
echo "1. Add GitHub Secrets:"
echo "   → Go to: https://github.com/awaisvortex/BeautyDropAI/settings/secrets/actions"
echo "   → Add 'GCP_SERVICE_ACCOUNT_KEY' (contents of $KEY_FILE)"
echo "   → Add 'CLOUD_RUN_ENV_YAML' (contents of cloudrun-env-template.yaml, updated)"
echo ""
echo "2. Update cloudrun-env-template.yaml with production values"
echo ""
echo "3. Test the pipeline:"
echo "   → Create a PR and verify tests run"
echo "   → Merge to main and verify deployment"
echo ""
echo "4. Secure your key:"
echo "   → Delete $KEY_FILE after uploading to GitHub"
echo "   → Run: rm $KEY_FILE cloudrun-env-template.yaml"
echo ""
echo "🎉 Setup complete!"


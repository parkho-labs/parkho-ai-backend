#!/bin/bash

set -e

PROJECT_ID="nyayamind-dev"
SERVICE_NAME="nyayamind-backend"
REGION="asia-south2"
RAG_ENGINE_URL="https://rag-engine-api-722723826302.asia-south2.run.app/api/v1"

echo "🚀 Deploying to Cloud Run..."
gcloud config set project $PROJECT_ID

# Get project number and service account
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "📦 Building image..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME

echo "🔑 Setting up Secret Manager permissions..."
# Grant access to secrets
gcloud secrets add-iam-policy-binding OPENAI_API_KEY --member="serviceAccount:${SERVICE_ACCOUNT}" --role="roles/secretmanager.secretAccessor" --quiet
gcloud secrets add-iam-policy-binding GEMINI_API_KEY --member="serviceAccount:${SERVICE_ACCOUNT}" --role="roles/secretmanager.secretAccessor" --quiet
gcloud secrets add-iam-policy-binding DATABASE_URL --member="serviceAccount:${SERVICE_ACCOUNT}" --role="roles/secretmanager.secretAccessor" --quiet

echo "🚀 Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --timeout 900 \
  --set-env-vars RAG_ENGINE_URL="$RAG_ENGINE_URL",AUTHENTICATION_ENABLED=false \
  --set-secrets OPENAI_API_KEY=OPENAI_API_KEY:latest \
  --set-secrets GOOGLE_API_KEY=GEMINI_API_KEY:latest \
  --set-secrets DATABASE_URL=DATABASE_URL:latest
echo "✅ Deployment complete!"
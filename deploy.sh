#!/bin/bash

set -e

PROJECT_ID="nyayamind-dev"
SERVICE_NAME="nyayamind-backend"
REGION="asia-south2"

echo "🚀 Deploying to Cloud Run..."
gcloud config set project $PROJECT_ID
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME
gcloud run deploy $SERVICE_NAME --image gcr.io/$PROJECT_ID/$SERVICE_NAME --region $REGION --platform managed --allow-unauthenticated --memory 2Gi --timeout 900
echo "✅ Deployment complete!"
#!/bin/bash

# GCP Cloud Run Deployment Script for AI Content Tutor Backend
# Make sure you're logged in: gcloud auth login
# Make sure project is set: gcloud config set project parkhoai-864b2

set -e

PROJECT_ID="parkhoai-864b2"
SERVICE_NAME="ai-content-tutor"
REGION="us-central1"

# PROD DATABASE URL (Supabase)
# User requested to include this directly in the script.
# NOTE: Ensure the password is URL-encoded if it contains special chars.
# Verified Password: ParkhoAI@&098 -> ParkhoAI%40%26098
SUPABASE_DB_URL="postgresql://postgres:ParkhoAI%40%26098@db.kjliolcvhuzsuehnelfw.supabase.co:5432/postgres"

echo "🚀 Starting deployment to GCP Cloud Run..."

# Step 1: Enable required APIs
echo "📡 Enabling required APIs..."
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable secretmanager.googleapis.com

# Step 2: Build and deploy to Cloud Run
echo "🏗️ Building and deploying to Cloud Run..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME

echo "🚀 Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
    --region $REGION \
    --platform managed \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 1 \
    --timeout 3600 \
    --concurrency 10 \
    --max-instances 5 \
    --clear-env-vars \
    --clear-cloudsql-instances \
    --set-secrets="OPENAI_API_KEY=OPENAI_API_KEY:latest" \
    --set-env-vars="DATABASE_URL=$SUPABASE_DB_URL"

echo "✅ Deployment complete!"
echo "🌐 Your service URL:"
gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)"
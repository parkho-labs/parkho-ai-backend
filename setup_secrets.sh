#!/bin/bash

# AI Content Tutor Backend - GCP Secret Manager Setup
# This script creates secrets in GCP Secret Manager from your .env file

set -e

PROJECT_ID="parkhoai-864b2"
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   AI Content Tutor - Setting up GCP Secrets${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    echo "Please create a .env file with your configuration"
    exit 1
fi

# Load environment variables
source .env

# Set project
gcloud config set project ${PROJECT_ID}

# Enable Secret Manager API
echo -e "${YELLOW}🔧 Enabling Secret Manager API...${NC}"
gcloud services enable secretmanager.googleapis.com --quiet

# Function to create or update secret
create_or_update_secret() {
    local secret_name=$1
    local secret_value=$2

    if [ -z "$secret_value" ]; then
        echo -e "${YELLOW}⚠️  Skipping ${secret_name} (empty value)${NC}"
        return
    fi

    # Check if secret exists
    if gcloud secrets describe ${secret_name} --project=${PROJECT_ID} &>/dev/null; then
        echo -e "${BLUE}Updating secret: ${secret_name}${NC}"
        echo -n "${secret_value}" | gcloud secrets versions add ${secret_name} --data-file=-
    else
        echo -e "${BLUE}Creating secret: ${secret_name}${NC}"
        echo -n "${secret_value}" | gcloud secrets create ${secret_name} --data-file=- --replication-policy="automatic"
    fi

    echo -e "${GREEN}✅ ${secret_name} configured${NC}"
}

# Create secrets from .env variables
echo ""
echo -e "${YELLOW}Creating secrets...${NC}"
echo ""

# Only create secrets for what's actually in .env
create_or_update_secret "OPENAI_API_KEY" "${OPENAI_API_KEY}"
create_or_update_secret "DATABASE_URL" "${DATABASE_URL}"

# Grant Cloud Run access to secrets
echo ""
echo -e "${YELLOW}🔑 Granting Cloud Run access to secrets...${NC}"

# Get the correct Cloud Run service account (Compute Engine default)
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo -e "${BLUE}Using service account: ${SERVICE_ACCOUNT}${NC}"

# List of secrets to grant access to (only what we actually have)
SECRETS=(
    "OPENAI_API_KEY"
    "DATABASE_URL"
)

for secret in "${SECRETS[@]}"; do
    if gcloud secrets describe ${secret} --project=${PROJECT_ID} &>/dev/null; then
        echo -e "${YELLOW}Granting access to: ${secret}${NC}"
        gcloud secrets add-iam-policy-binding ${secret} \
            --member="serviceAccount:${SERVICE_ACCOUNT}" \
            --role="roles/secretmanager.secretAccessor" \
            --project=${PROJECT_ID} \
            --quiet
        echo -e "${GREEN}✅ ${secret} permissions set${NC}"
    fi
done

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   ✅ Secrets Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}📝 Configured Secrets:${NC}"
gcloud secrets list --format="table(name,createTime)" --filter="name~DATABASE_URL OR name~OPENAI_API_KEY"
echo ""
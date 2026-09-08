#!/usr/bin/env bash

# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# ==============================================================================
# Transaction Executor (Agent 2) - Deployment Script
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

readonly REGION="us-central1"
readonly GEMINI_LOCATION="global"
readonly DEFAULT_BROKER_KEY="apex-broker-secret-key-prod-2026"
readonly DEFAULT_BROKER_URL="https://apex-broker.piyasharma.demo.altostrat.com"

PROJECT_ID="${1:-${GOOGLE_CLOUD_PROJECT:-}}"
if [[ -z "$PROJECT_ID" ]]; then
  DETECTED_PROJECT=$(gcloud config get-value project 2>/dev/null || true)
  if [[ -n "$DETECTED_PROJECT" && "$DETECTED_PROJECT" != "(unset)" ]]; then
    read -rp "Enter GCP Project ID [default: ${DETECTED_PROJECT}]: " INPUT_PROJECT
    PROJECT_ID="${INPUT_PROJECT:-$DETECTED_PROJECT}"
  else
    read -rp "Enter GCP Project ID: " PROJECT_ID
  fi
fi

if [[ -z "$PROJECT_ID" ]]; then
  echo "Error: GCP Project ID is required." >&2
  exit 1
fi

echo "=== Deploying Transaction Executor to Cloud Run ==="
gcloud config set project "$PROJECT_ID" --quiet
export GOOGLE_CLOUD_PROJECT="$PROJECT_ID"

cat > .env <<EOF
GOOGLE_CLOUD_PROJECT=${PROJECT_ID}
GEMINI_LOCATION=${GEMINI_LOCATION}
BROKER_API_KEY=${DEFAULT_BROKER_KEY}
BROKER_API_URL=${DEFAULT_BROKER_URL}
EOF

# Generate unique tag for Artifact Registry tag immutability
BUILD_TAG="$(date +%Y%m%d-%H%M%S)"
IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/apex-wealth-agents/transaction-executor:${BUILD_TAG}"

echo "Step 1: Building container image with Cloud Build..."
gcloud builds submit \
  --tag "${IMAGE_TAG}" \
  --project "$PROJECT_ID"

echo "Step 2: Deploying container image to Cloud Run..."
gcloud run deploy transaction-executor \
  --image "${IMAGE_TAG}" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --no-invoker-iam-check \
  --min-instances 1 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GEMINI_LOCATION=${GEMINI_LOCATION},BROKER_API_KEY=${DEFAULT_BROKER_KEY},BROKER_API_URL=${DEFAULT_BROKER_URL}" \
  --quiet

TE_SERVICE_URL=$(gcloud run services describe transaction-executor \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --format="value(status.url)")

if [[ -z "$TE_SERVICE_URL" ]]; then
  echo "Error: Could not retrieve Transaction Executor URL." >&2
  exit 1
fi

echo "Transaction Executor: ${TE_SERVICE_URL}"

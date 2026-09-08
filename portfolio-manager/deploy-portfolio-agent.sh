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
# Portfolio Manager (Agent 3) - Deployment Script
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

readonly REGION="us-central1"
readonly GEMINI_LOCATION="global"

# 1. Project ID: from argument, env, or prompt
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

# 2. Financial Auditor URL & Transaction Executor URL
# Check arguments first, then existing .env if present, then auto-detect from project
FINANCIAL_AUDITOR_URL="${2:-${FINANCIAL_AUDITOR_URL:-}}"
TRANSACTION_EXECUTOR_URL="${3:-${TRANSACTION_EXECUTOR_URL:-}}"

if [[ -f .env ]]; then
  EXISTING_FA=$(grep "^FINANCIAL_AUDITOR_URL=" .env | cut -d= -f2- || true)
  EXISTING_TE=$(grep "^TRANSACTION_EXECUTOR_URL=" .env | cut -d= -f2- || true)
  FINANCIAL_AUDITOR_URL="${FINANCIAL_AUDITOR_URL:-$EXISTING_FA}"
  TRANSACTION_EXECUTOR_URL="${TRANSACTION_EXECUTOR_URL:-$EXISTING_TE}"
fi

# Auto-detect if still not set
if [[ -z "$FINANCIAL_AUDITOR_URL" ]]; then
  TOKEN=$(gcloud auth print-access-token 2>/dev/null || true)
  FINANCIAL_AUDITOR_URL=$(curl -s -H "Authorization: Bearer ${TOKEN}" \
    "https://${REGION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${REGION}/reasoningEngines" 2>/dev/null | \
    python3 -c "import sys, json; data=json.load(sys.stdin); res=[e['name'] for e in data.get('reasoningEngines', []) if 'financial' in e.get('displayName', '').lower()]; print(res[-1] if res else '')" 2>/dev/null || true)
fi

if [[ -z "$TRANSACTION_EXECUTOR_URL" ]]; then
  TRANSACTION_EXECUTOR_URL=$(gcloud run services describe transaction-executor \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --format="value(status.url)" 2>/dev/null || true)
fi

# Prompt CE with current parameters and dependencies before deploying
echo ""
echo "============================================================"
echo "  Portfolio Manager - Deployment Parameters"
echo "============================================================"
echo "  Project ID:               ${PROJECT_ID}"
echo "  Region:                   ${REGION}"
echo "  Gemini Location:          ${GEMINI_LOCATION}"
echo "  Financial Auditor URL:    ${FINANCIAL_AUDITOR_URL:-[not set]}"
echo "  Transaction Executor URL: ${TRANSACTION_EXECUTOR_URL:-[not set]}"
echo "============================================================"
echo ""

read -rp "Do you need to change any of these parameters? [y/N]: " CHANGE_PARAMS
if [[ "$CHANGE_PARAMS" =~ ^[yY] ]]; then
  read -rp "Enter GCP Project ID [default: ${PROJECT_ID}]: " INPUT_P
  PROJECT_ID="${INPUT_P:-$PROJECT_ID}"

  read -rp "Enter Financial Auditor URL [default: ${FINANCIAL_AUDITOR_URL}]: " INPUT_FA
  FINANCIAL_AUDITOR_URL="${INPUT_FA:-$FINANCIAL_AUDITOR_URL}"

  read -rp "Enter Transaction Executor URL [default: ${TRANSACTION_EXECUTOR_URL}]: " INPUT_TE
  TRANSACTION_EXECUTOR_URL="${INPUT_TE:-$TRANSACTION_EXECUTOR_URL}"
fi

if [[ -z "$FINANCIAL_AUDITOR_URL" ]]; then
  read -rp "Enter Financial Auditor URL: " FINANCIAL_AUDITOR_URL
fi

if [[ -z "$TRANSACTION_EXECUTOR_URL" ]]; then
  read -rp "Enter Transaction Executor URL: " TRANSACTION_EXECUTOR_URL
fi

if [[ -z "$FINANCIAL_AUDITOR_URL" || -z "$TRANSACTION_EXECUTOR_URL" ]]; then
  echo "Error: Both FINANCIAL_AUDITOR_URL and TRANSACTION_EXECUTOR_URL are required." >&2
  exit 1
fi

echo "=== Deploying Portfolio Manager to Vertex AI Agent Runtime ==="
gcloud config set project "$PROJECT_ID" --quiet
export GOOGLE_CLOUD_PROJECT="$PROJECT_ID"

cat > .env <<EOF
GOOGLE_CLOUD_PROJECT=${PROJECT_ID}
GEMINI_LOCATION=${GEMINI_LOCATION}
FINANCIAL_AUDITOR_URL=${FINANCIAL_AUDITOR_URL}
TRANSACTION_EXECUTOR_URL=${TRANSACTION_EXECUTOR_URL}
EOF

uv sync --quiet
agents-cli deploy --project "$PROJECT_ID" --min-instances 1

TOKEN=$(gcloud auth print-access-token 2>/dev/null)
PM_RESOURCE_NAME=$(curl -s -H "Authorization: Bearer ${TOKEN}" \
  "https://${REGION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${REGION}/reasoningEngines" | \
  python3 -c "import sys, json; data=json.load(sys.stdin); res=[e['name'] for e in data.get('reasoningEngines', []) if 'portfolio' in e.get('displayName', '').lower()]; print(res[-1] if res else '')")

if [[ -z "$PM_RESOURCE_NAME" ]]; then
  echo "Error: Could not retrieve Portfolio Manager resource name." >&2
  exit 1
fi

echo "Portfolio Manager: ${PM_RESOURCE_NAME}"

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
# Apex Wealth Management - Deploy All Agents
#
# Automates sequential deployment of the 3 lab agents:
#   1. Financial Auditor    -> Vertex AI Agent Engine (Reasoning Engine)
#   2. Transaction Executor -> Cloud Run (via gcloud run deploy)
#   3. Portfolio Manager    -> Vertex AI Agent Engine (wires Agents 1 & 2)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Hardcoded configurations as per lab specifications
readonly REGION="us-central1"
readonly GEMINI_LOCATION="global"

# 1. Project ID: from argument or prompt
PROJECT_ID="${1:-}"
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

echo "Deploying Apex Wealth agents to project: ${PROJECT_ID} (region: ${REGION})"
gcloud config set project "$PROJECT_ID" --quiet
export GOOGLE_CLOUD_PROJECT="$PROJECT_ID"

# ==============================================================================
# 1. Deploy Financial Auditor (Agent 1)
# ==============================================================================
echo ""
"${SCRIPT_DIR}/financial-auditor/deploy-financial-agent.sh" "$PROJECT_ID"

# ==============================================================================
# 2. Deploy Transaction Executor (Agent 2)
# ==============================================================================
echo ""
"${SCRIPT_DIR}/transaction-executor/deploy-transaction-agent.sh" "$PROJECT_ID"

# ==============================================================================
# 3. Deploy Portfolio Manager (Agent 3)
# ==============================================================================
echo ""
"${SCRIPT_DIR}/portfolio-manager/deploy-portfolio-agent.sh" "$PROJECT_ID"

# ==============================================================================
# Save Endpoints & Print Summary
# ==============================================================================
TOKEN=$(gcloud auth print-access-token 2>/dev/null)
FA_RESOURCE_NAME=$(curl -s -H "Authorization: Bearer ${TOKEN}" \
  "https://${REGION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${REGION}/reasoningEngines" | \
  python3 -c "import sys, json; data=json.load(sys.stdin); res=[e['name'] for e in data.get('reasoningEngines', []) if 'financial' in e.get('displayName', '').lower()]; print(res[-1] if res else '')")

TE_SERVICE_URL=$(gcloud run services describe transaction-executor \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --format="value(status.url)" 2>/dev/null || true)

PM_RESOURCE_NAME=$(curl -s -H "Authorization: Bearer ${TOKEN}" \
  "https://${REGION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${REGION}/reasoningEngines" | \
  python3 -c "import sys, json; data=json.load(sys.stdin); res=[e['name'] for e in data.get('reasoningEngines', []) if 'portfolio' in e.get('displayName', '').lower()]; print(res[-1] if res else '')")

ENV_FILE="${SCRIPT_DIR}/.deployment-info.env"
cat > "$ENV_FILE" <<EOF
export PROJECT_ID="${PROJECT_ID}"
export REGION="${REGION}"
export GEMINI_LOCATION="${GEMINI_LOCATION}"
export FINANCIAL_AUDITOR_URL="${FA_RESOURCE_NAME}"
export TRANSACTION_EXECUTOR_URL="${TE_SERVICE_URL}"
export PORTFOLIO_MANAGER_URL="${PM_RESOURCE_NAME}"
EOF
chmod 600 "$ENV_FILE"

echo ""
echo "============================================================"
echo "  All 3 Agents Deployed Successfully!"
echo "============================================================"
echo "  1. Financial Auditor:    ${FA_RESOURCE_NAME}"
echo "  2. Transaction Executor: ${TE_SERVICE_URL}"
echo "  3. Portfolio Manager:    ${PM_RESOURCE_NAME}"
echo ""
echo "  Endpoints saved to: $ENV_FILE"
echo "  Load into shell:    source $ENV_FILE"
echo ""
echo "  For verification and testing, see README.md."
echo "============================================================"

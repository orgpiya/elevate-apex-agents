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
# Financial Auditor (Agent 1) - Deployment Script
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

readonly REGION="us-central1"
readonly GEMINI_LOCATION="global"
readonly DATASET_ID="apex_wealth_dataset"

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

echo "=== Deploying Financial Auditor to Vertex AI Agent Runtime ==="
gcloud config set project "$PROJECT_ID" --quiet
export GOOGLE_CLOUD_PROJECT="$PROJECT_ID"

cat > .env <<EOF
GOOGLE_CLOUD_PROJECT=${PROJECT_ID}
GEMINI_LOCATION=${GEMINI_LOCATION}
DATASET_ID=${DATASET_ID}
EOF

uv sync --quiet
agents-cli deploy --project "$PROJECT_ID" --min-instances 1

TOKEN=$(gcloud auth print-access-token 2>/dev/null)
FA_RESOURCE_NAME=$(curl -s -H "Authorization: Bearer ${TOKEN}" \
  "https://${REGION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${REGION}/reasoningEngines" | \
  python3 -c "import sys, json; data=json.load(sys.stdin); res=[e['name'] for e in data.get('reasoningEngines', []) if 'financial' in e.get('displayName', '').lower()]; print(res[-1] if res else '')")

if [[ -z "$FA_RESOURCE_NAME" ]]; then
  echo "Error: Could not retrieve Financial Auditor resource name." >&2
  exit 1
fi

echo "Financial Auditor: ${FA_RESOURCE_NAME}"

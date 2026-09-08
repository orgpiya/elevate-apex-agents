# Apex Wealth Management - Agent Code

This repository contains the AI agent code for the Apex Wealth Management platform.

## System Overview

The system consists of three AI agents that work together to provide portfolio management services:

```
┌─────────────────────┐
│ Portfolio Manager   │  Orchestrates requests
│ (Agent Runtime)     │  
└──────────┬──────────┘
           │
           ├──────────────────────┬─────────────────────────┐
           │                      │                         │
           ▼                      ▼                         ▼
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│ Financial Auditor    │  │ Transaction Executor │  │ External Broker API  │
│ (Agent Runtime)      │  │ (Cloud Run)          │  │                      │
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘
           │                      │
           ▼                      ▼
    ┌──────────┐          ┌──────────┐
    │ BigQuery │          │  Broker  │
    └──────────┘          └──────────┘
```

### Agents

1. **Portfolio Manager** (`portfolio-manager/`)
   - Orchestrates customer requests
   - Coordinates between Financial Auditor and Transaction Executor
   - Has NO direct data or broker access (delegates to specialists)

2. **Financial Auditor** (`financial-auditor/`)
   - Queries customer account data from BigQuery
   - Analyzes transaction history
   - Calculates portfolio valuations
   - READ-ONLY access to financial data

3. **Transaction Executor** (`transaction-executor/`)
   - Executes trades with external broker API
   - Checks trade status
   - Cancels pending trades
   - WRITE access to broker API

## Prerequisites

Before deploying agents, ensure you have:

1. **GCP Project** with billing enabled
2. **APIs Enabled**:
   - Vertex AI API
   - Cloud Run API
   - BigQuery API
   - Cloud Storage API

3. **Infrastructure Deployed**:
   - BigQuery dataset: `apex_wealth_dataset`
   - Sample data loaded
   - Service accounts configured

   > **Note**: Infrastructure should already be deployed by your trainer. If not, contact them before proceeding.

4. **Local Tools Installed**:
   ```bash
   # Install uv (Python package manager)
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Install agents-cli
   uv tool install google-agents-cli
   
   # Verify installation
   agents-cli --version
   ```

## Deployment Instructions

### Automated Deployment (Recommended)

Deploy all three agents, automatically cross-wire their endpoints, and run unified verification in one command:

```bash
chmod +x deploy-all-agents.sh
./deploy-all-agents.sh
```

The script will:
1. Prompt for your GCP Project ID (auto-detecting your active `gcloud` project) and Broker API URL.
2. Deploy **Financial Auditor** to Vertex AI Agent Runtime and capture its Resource Name.
3. Deploy **Transaction Executor** to Cloud Run.
4. Auto-inject the endpoints into **Portfolio Manager**'s `.env` and deploy it to Vertex AI Agent Runtime.
5. Run a unified verification test across all three agents and print a summary table.
6. Export all URLs to `.deployment-info.env` so you can run `source .deployment-info.env` anytime.

---

### Individual Agent Deployment & Re-deployment (Alternative)

Each agent has its own dedicated deployment script in its folder. CEs can use these scripts to deploy or re-deploy each agent individually:

#### Financial Auditor (Agent 1)

```bash
cd financial-auditor/
./deploy-financial-agent.sh
```

- Synchronizes dependencies with `uv sync`.
- Deploys to Vertex AI Agent Runtime (Reasoning Engine).
- Captures the Reasoning Engine Resource Name and updates `.deployment-info.env`.

#### Transaction Executor (Agent 2)

```bash
cd transaction-executor/
./deploy-transaction-agent.sh
```

- Configures environment and broker API settings.
- Deploys to Cloud Run.
- Captures the Cloud Run Service URL and updates `.deployment-info.env`.

#### Portfolio Manager (Agent 3)

```bash
cd portfolio-manager/
./deploy-portfolio-agent.sh
```

- Automatically discovers or loads endpoints for Financial Auditor and Transaction Executor.
- Prompts the CE with all active parameters and dependency URLs for verification and edits before deployment.
- Deploys to Vertex AI Agent Runtime and updates `.deployment-info.env`.

## Testing the System

### Local Testing (Optional)

Test agents locally before deployment:

```bash
cd financial-auditor/
agents-cli run "Get account summary for account 12345"
```

### End-to-End Test

After all agents are deployed:

```bash
cd portfolio-manager/
agents-cli run "Get portfolio analysis for account 12345 and execute a buy order for 10 shares of GOOG"
```

**Expected flow**:
1. Portfolio Manager calls Financial Auditor for account data
2. Financial Auditor queries BigQuery
3. Portfolio Manager calls Transaction Executor to execute trade
4. Transaction Executor calls broker API
5. Trade confirmation returned

## Troubleshooting

### Deployment Fails with "Permission Denied"

**Cause**: Your user account doesn't have permission to deploy to Agent Runtime or Cloud Run.

**Fix**: Ensure you have the following IAM roles:
- `roles/aiplatform.user` (for Agent Runtime)
- `roles/run.developer` (for Cloud Run)

### Agent Can't Access BigQuery

**Cause**: Service account doesn't have BigQuery permissions.

**Fix**: The service account needs `roles/bigquery.dataViewer`. Contact your trainer or check IAM policies.

### Agent-to-Agent Calls Fail

**Cause**: Agent URLs are incorrect or services aren't deployed.

**Fix**: 
1. Verify all agents are deployed: `agents-cli info`
2. Check `.env` files have correct URLs
3. Redeploy Portfolio Manager after updating URLs

### "BROKER_API_KEY not set" Error

**Cause**: Transaction Executor needs broker API credentials.

**Fix**: Set `BROKER_API_KEY` and `BROKER_API_URL` in `transaction-executor/.env`

## Re-Deploying After Code Changes

When you modify an agent's code (e.g. applying fixes), re-deploy that individual agent using its dedicated script:

- **Financial Auditor**:
  ```bash
  cd financial-auditor && ./deploy-financial-agent.sh
  ```
- **Transaction Executor**:
  ```bash
  cd transaction-executor && ./deploy-transaction-agent.sh
  ```
- **Portfolio Manager**:
  ```bash
  cd portfolio-manager && ./deploy-portfolio-agent.sh
  ```

## Agent URLs

After deployment, you can find your agent URLs:

```bash
# List all agents
agents-cli info

# Get specific agent details
agents-cli info --agent portfolio-manager
```

## Security Notes

**This is a training environment.** The agents contain intentional security vulnerabilities for educational purposes. Do NOT use this code in production.

## Support

For lab-specific questions, contact your trainer.

For agents-cli issues, see: https://adk.dev

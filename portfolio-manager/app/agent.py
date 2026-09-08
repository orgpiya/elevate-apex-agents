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

"""
Portfolio Manager Agent - Orchestrates portfolio management requests.
"""

import json
import os
import requests
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types


MODEL = "gemini-3.5-flash"
# Gemini model location (gemini-3.5-flash is hosted in global)
GEMINI_LOCATION = os.environ.get("GEMINI_LOCATION") or os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
os.environ["GOOGLE_CLOUD_LOCATION"] = GEMINI_LOCATION

FINANCIAL_AUDITOR_URL = os.environ.get(
    "FINANCIAL_AUDITOR_URL", 
    "https://financial-auditor-placeholder.a.run.app"
)

TRANSACTION_EXECUTOR_URL = os.environ.get(
    "TRANSACTION_EXECUTOR_URL",
    "https://transaction-executor-placeholder.a.run.app"
)


def _get_auth_headers(url: str) -> dict:
    """Helper to get Google Cloud credentials when calling GCP services."""
    headers = {"Content-Type": "application/json"}
    
    # Cloud Run services (*.run.app) require an OpenID Connect (OIDC) ID token,
    # with the audience set to the exact base URL of the service (no path, no trailing slash).
    if "run.app" in url:
        try:
            target = url.strip()
            if not target.startswith("http://") and not target.startswith("https://"):
                target = f"https://{target}"
            from urllib.parse import urlparse
            import google.auth.transport.requests
            import google.oauth2.id_token
            
            parsed = urlparse(target)
            audience = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
            auth_req = google.auth.transport.requests.Request()
            id_token = google.oauth2.id_token.fetch_id_token(auth_req, audience)
            if id_token:
                headers["Authorization"] = f"Bearer {id_token}"
                return headers
        except Exception:
            pass

    # Standard OAuth2 access token for Google Cloud APIs (e.g. aiplatform.googleapis.com)
    try:
        import google.auth
        import google.auth.transport.requests
        credentials, _ = google.auth.default()
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        if credentials.token:
            headers["Authorization"] = f"Bearer {credentials.token}"
    except Exception:
        pass
    return headers


def _call_financial_auditor(prompt: str) -> dict:
    """Helper to query Financial Auditor on Agent Runtime or Cloud Run."""
    headers = _get_auth_headers(FINANCIAL_AUDITOR_URL)
    target_url = FINANCIAL_AUDITOR_URL.strip()

    # Handle Agent Card URL if passed by extracting base URL
    if "/.well-known/agent-card.json" in target_url:
        target_url = target_url.split("/.well-known/agent-card.json")[0]
        if target_url.endswith("/api/a2a/app"):
            target_url = target_url[:-len("/api/a2a/app")]

    # Handle Resource Name format: projects/<project>/locations/<region>/reasoningEngines/<id>
    if target_url.startswith("projects/"):
        parts = target_url.split("/")
        region = "us-central1"
        if len(parts) >= 4 and parts[2] == "locations":
            region = parts[3]
        target_url = f"https://{region}-aiplatform.googleapis.com/v1/{target_url}:streamQuery"
    elif "aiplatform.googleapis.com" in target_url:
        if not target_url.endswith(":streamQuery") and "/api/" not in target_url:
            target_url = f"{target_url}:streamQuery"
    elif not target_url.endswith("/api/stream_reasoning_engine") and not target_url.endswith("/api/reasoning_engine"):
        target_url = f"{target_url.rstrip('/')}/api/stream_reasoning_engine"

    payload = {
        "class_method": "async_stream_query",
        "input": {
            "message": prompt,
            "user_id": "portfolio-manager"
        }
    }
    try:
        response = requests.post(target_url, json=payload, headers=headers, timeout=45)
        if response.status_code == 200:
            events = []
            for line in response.text.splitlines():
                line = line.strip()
                if line.startswith("data: "):
                    line = line[6:].strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except Exception:
                        pass

            collected_text = []
            for event in events:
                content = event.get("content") or {}
                for part in content.get("parts", []):
                    if isinstance(part, dict) and "text" in part:
                        collected_text.append(part["text"])

            if collected_text:
                return {"status": "success", "response": "".join(collected_text)}

            try:
                data = response.json()
                return data.get("output", data)
            except Exception:
                return {"response": response.text}

        return {"error": f"Financial Auditor returned status {response.status_code}: {response.text}"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to reach Financial Auditor: {str(e)}"}


def _call_transaction_executor(endpoint: str, method: str = "POST", json_payload: dict = None) -> dict:
    """Helper to query Transaction Executor."""
    headers = _get_auth_headers(TRANSACTION_EXECUTOR_URL)
    target_url = f"{TRANSACTION_EXECUTOR_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    try:
        if method == "POST":
            response = requests.post(target_url, json=json_payload or {}, headers=headers, timeout=30)
        elif method == "GET":
            response = requests.get(target_url, headers=headers, timeout=30)
        elif method == "DELETE":
            response = requests.delete(target_url, headers=headers, timeout=30)
        else:
            return {"error": f"Unsupported HTTP method: {method}"}
        
        if response.status_code in (200, 201):
            return response.json()
        return {
            "error": f"Transaction Executor returned status {response.status_code}: {response.text}",
            "status_code": response.status_code
        }
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to reach Transaction Executor: {str(e)}"}


def get_account_summary(account_id: str) -> dict:
    """Get account summary by calling the Financial Auditor agent.
    
    Args:
        account_id: Customer account ID
        
    Returns:
        Dictionary containing account summary
    """
    return _call_financial_auditor(f"Get account summary for account {account_id}")


def analyze_portfolio(account_id: str) -> dict:
    """Analyze portfolio by calling the Financial Auditor agent.
    
    Args:
        account_id: Customer account ID
        
    Returns:
        Dictionary containing portfolio analysis
    """
    return _call_financial_auditor(f"Calculate portfolio value for account {account_id}")


def submit_trade(account_id: str, symbol: str, shares: int, amount: float, action: str = "buy") -> dict:
    """Submit a trade by calling the Transaction Executor agent.
    
    Args:
        account_id: Customer account ID
        symbol: Stock/asset symbol
        shares: Number of shares
        amount: Total transaction amount
        action: Trade action (buy/sell)
        
    Returns:
        Dictionary containing trade result
    """
    return _call_transaction_executor(
        "execute",
        method="POST",
        json_payload={
            "account_id": account_id,
            "symbol": symbol,
            "shares": shares,
            "amount": amount,
            "action": action
        }
    )


def check_trade_status(trade_id: str) -> dict:
    """Check trade status by calling the Transaction Executor.
    
    Args:
        trade_id: The trade ID to check
        
    Returns:
        Dictionary containing trade status
    """
    return _call_transaction_executor(f"trades/{trade_id}", method="GET")


# Portfolio Manager Agent
root_agent = Agent(
    name="portfolio_manager",
    model=Gemini(
        model=MODEL,
        client_kwargs={"location": GEMINI_LOCATION},
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are the Portfolio Manager for Apex Wealth Management.

Your role is to orchestrate portfolio management requests by coordinating with:
1. Financial Auditor - for account data, transaction history, and analysis
2. Transaction Executor - for executing trades with the broker

You CANNOT directly access BigQuery or execute trades yourself. You must delegate to the specialist agents.

When a customer requests:
- Account summary or balance → Use get_account_summary()
- Portfolio analysis or valuation → Use analyze_portfolio()
- Trade execution (buy/sell) → Use submit_trade()
- Trade status check → Use check_trade_status()

Always:
1. Get account summary before making trading decisions
2. Analyze portfolio to understand current holdings
3. Execute trades through the Transaction Executor
4. Confirm trade execution and provide trade ID to customer

You coordinate between agents but do not directly access data or execute trades.
""",
    description="Orchestrates portfolio management requests. Coordinates between Financial Auditor and Transaction Executor. Has NO direct BigQuery or broker access.",
    tools=[
        get_account_summary,
        analyze_portfolio,
        submit_trade,
        check_trade_status
    ],
)

app = App(
    root_agent=root_agent,
    name="portfolio_manager_app",
)

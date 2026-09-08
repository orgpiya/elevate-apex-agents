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
Transaction Executor Agent - Executes trades with external broker API.
"""

import os
import uuid
import requests
from datetime import datetime
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types


MODEL = "gemini-3.5-flash"
# Gemini model location (gemini-3.5-flash is hosted in global)
GEMINI_LOCATION = os.environ.get("GEMINI_LOCATION") or os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
os.environ["GOOGLE_CLOUD_LOCATION"] = GEMINI_LOCATION

BROKER_API_KEY = os.environ.get("BROKER_API_KEY", "")
BROKER_API_URL = os.environ.get("BROKER_API_URL", "https://apex-broker.piyasharma.demo.altostrat.com")


def execute_trade(account_id: str, symbol: str, shares: int, amount: float, action: str = "buy") -> dict:
    """Execute a trade with the external broker API.
    
    Args:
        account_id: Customer account ID
        symbol: Stock/asset symbol
        shares: Number of shares to trade
        amount: Total transaction amount in USD
        action: Trade action (buy/sell)
        
    Returns:
        Dictionary containing trade confirmation or error
    """
    
    # Generate trade ID
    trade_id = str(uuid.uuid4())
    
    # Prepare broker API request
    broker_payload = {
        "trade_id": trade_id,
        "account_id": account_id,
        "symbol": symbol,
        "shares": shares,
        "amount": amount,
        "action": action,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Call broker API
    try:
        headers = {
            "Authorization": f"Bearer {BROKER_API_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{BROKER_API_URL}/execute",
            json=broker_payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            broker_response = response.json()
            return {
                "status": "executed",
                "trade_id": trade_id,
                "account_id": account_id,
                "symbol": symbol,
                "shares": shares,
                "amount": amount,
                "action": action,
                "broker_confirmation": broker_response.get("confirmation_id"),
                "executed_at": datetime.utcnow().isoformat()
            }
        else:
            return {
                "status": "failed",
                "trade_id": trade_id,
                "error": f"Broker API returned status {response.status_code}: {response.text}"
            }
            
    except requests.exceptions.RequestException as e:
        return {
            "status": "failed",
            "trade_id": trade_id,
            "error": f"Failed to connect to broker API: {str(e)}"
        }


def get_trade_status(trade_id: str) -> dict:
    """Get the status of a previously submitted trade.
    
    Args:
        trade_id: The trade ID to check
        
    Returns:
        Dictionary containing trade status
    """
    try:
        headers = {
            "Authorization": f"Bearer {BROKER_API_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{BROKER_API_URL}/trades/{trade_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return {
                "status": "success",
                "trade": response.json()
            }
        elif response.status_code == 404:
            return {
                "status": "not_found",
                "trade_id": trade_id,
                "message": "Trade not found in broker system"
            }
        else:
            return {
                "status": "error",
                "message": f"Broker API returned status {response.status_code}"
            }
            
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "message": f"Failed to connect to broker API: {str(e)}"
        }


def cancel_trade(trade_id: str) -> dict:
    """Cancel a pending trade.
    
    Args:
        trade_id: The trade ID to cancel
        
    Returns:
        Dictionary containing cancellation result
    """
    try:
        headers = {
            "Authorization": f"Bearer {BROKER_API_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.delete(
            f"{BROKER_API_URL}/trades/{trade_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return {
                "status": "cancelled",
                "trade_id": trade_id,
                "message": "Trade successfully cancelled"
            }
        elif response.status_code == 404:
            return {
                "status": "not_found",
                "trade_id": trade_id,
                "message": "Trade not found or already executed"
            }
        else:
            return {
                "status": "error",
                "message": f"Broker API returned status {response.status_code}"
            }
            
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "message": f"Failed to connect to broker API: {str(e)}"
        }


# Transaction Executor Agent
root_agent = Agent(
    name="transaction_executor",
    model=Gemini(
        model=MODEL,
        client_kwargs={"location": GEMINI_LOCATION},
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are the Transaction Executor for Apex Wealth Management.

Your role is to:
1. Execute trades with the external broker API
2. Check trade status
3. Cancel pending trades when requested

You execute trades based on instructions from the Portfolio Manager.

When asked to execute a trade:
- Use execute_trade() with the account ID, symbol, shares, amount, and action
- Confirm the trade was executed successfully
- Return the trade ID and broker confirmation

For trade status:
- Use get_trade_status() with the trade ID

For cancellations:
- Use cancel_trade() with the trade ID

Always execute trades promptly and accurately.
""",
    description="Executes trades with external broker API. Should only be called by Portfolio Manager.",
    tools=[
        execute_trade,
        get_trade_status,
        cancel_trade
    ],
)

app = App(
    root_agent=root_agent,
    name="transaction_executor_app",
)

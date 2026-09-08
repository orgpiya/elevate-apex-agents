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
Financial Auditor Agent - Analyzes customer account data from BigQuery.
"""

import os
from google.cloud import bigquery
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types


MODEL = "gemini-3.5-flash"
# Gemini model location (gemini-3.5-flash is hosted in global)
GEMINI_LOCATION = os.environ.get("GEMINI_LOCATION") or os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
os.environ["GOOGLE_CLOUD_LOCATION"] = GEMINI_LOCATION
DATASET_ID = os.environ.get("DATASET_ID", "apex_wealth_dataset")


def query_account_data(account_id: str) -> dict:
    """Query BigQuery for customer account data.
    
    Args:
        account_id: The customer account ID to query
        
    Returns:
        Dictionary containing account information
    """
    client = bigquery.Client()
    
    query = f"""
        SELECT 
            account_id,
            customer_name,
            email,
            balance,
            risk_profile,
            created_at
        FROM `{DATASET_ID}.accounts`
        WHERE account_id = '{account_id}'
    """
    
    try:
        query_job = client.query(query)
        results = list(query_job.result())
        
        if not results:
            return {"error": f"No account found with ID: {account_id}"}
        
        # Convert BigQuery Row to dict
        account = dict(results[0])
        return {
            "status": "success",
            "account_id": account.get("account_id"),
            "customer_name": account.get("customer_name"),
            "account_holder": account.get("customer_name"),
            "email": account.get("email"),
            "balance": float(account.get("balance", 0)),
            "risk_profile": account.get("risk_profile"),
            "created_at": str(account.get("created_at"))
        }
    except Exception as e:
        return {"error": f"Query failed: {str(e)}"}


def get_transaction_history(account_id: str, limit: int = 10) -> dict:
    """Get recent transaction history for an account.
    
    Args:
        account_id: The customer account ID
        limit: Maximum number of transactions to return
        
    Returns:
        Dictionary containing transaction history
    """
    client = bigquery.Client()
    
    query = f"""
        SELECT 
            transaction_id,
            account_id,
            symbol,
            shares,
            amount,
            transaction_type,
            timestamp,
            status
        FROM `{DATASET_ID}.transactions`
        WHERE account_id = '{account_id}'
        ORDER BY timestamp DESC
        LIMIT {limit}
    """
    
    try:
        query_job = client.query(query)
        results = list(query_job.result())
        
        transactions = []
        for row in results:
            transactions.append({
                "transaction_id": row.get("transaction_id"),
                "date": str(row.get("timestamp")),
                "symbol": row.get("symbol"),
                "shares": row.get("shares"),
                "type": row.get("transaction_type"),
                "amount": float(row.get("amount", 0)),
                "status": row.get("status")
            })
        
        return {
            "status": "success",
            "account_id": account_id,
            "transaction_count": len(transactions),
            "transactions": transactions
        }
    except Exception as e:
        return {"error": f"Query failed: {str(e)}"}


def calculate_portfolio_value(account_id: str) -> dict:
    """Calculate total portfolio value for an account.
    
    Args:
        account_id: The customer account ID
        
    Returns:
        Dictionary containing portfolio valuation
    """
    # Get account data
    account_data = query_account_data(account_id)
    
    if "error" in account_data:
        return account_data
    
    # Get transaction history
    transactions = get_transaction_history(account_id, limit=100)
    
    if "error" in transactions:
        return {"error": "Could not retrieve transaction history"}
    
    # Calculate total buy vs sell volume
    total_buys = sum(
        t["amount"] for t in transactions.get("transactions", [])
        if t.get("type") == "buy"
    )
    
    total_sells = sum(
        t["amount"] for t in transactions.get("transactions", [])
        if t.get("type") == "sell"
    )
    
    return {
        "status": "success",
        "account_id": account_id,
        "customer_name": account_data.get("customer_name"),
        "current_balance": account_data.get("balance", 0),
        "total_buys": total_buys,
        "total_sells": total_sells,
        "net_flow": total_sells - total_buys
    }


# Financial Auditor Agent
root_agent = Agent(
    name="financial_auditor",
    model=Gemini(
        model=MODEL,
        client_kwargs={"location": GEMINI_LOCATION},
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are the Financial Auditor for Apex Wealth Management.

Your role is to:
1. Query customer account data from BigQuery
2. Analyze transaction history
3. Calculate portfolio valuations
4. Generate compliance reports

You have READ-ONLY access to financial data. You cannot execute trades or modify accounts.

When queried about an account:
- Use query_account_data() to get account details
- Use get_transaction_history() to see recent activity
- Use calculate_portfolio_value() for valuation analysis

Always provide accurate financial data analysis based on the BigQuery records.
""",
    description="Analyzes customer financial data and generates compliance reports. Has read-only access to BigQuery account and transaction data.",
    tools=[
        query_account_data,
        get_transaction_history,
        calculate_portfolio_value
    ],
)

app = App(
    root_agent=root_agent,
    name="financial_auditor_app",
)

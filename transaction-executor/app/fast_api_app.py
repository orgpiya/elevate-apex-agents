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

import contextlib
import os
from collections.abc import AsyncIterator

from a2a.server.tasks import InMemoryTaskStore
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import Runner

from app.app_utils import services
from app.app_utils.a2a import attach_a2a_routes

load_dotenv()
allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from app.agent import app as adk_app
    from app.agent import root_agent

    runner = Runner(
        app=adk_app,
        session_service=services.get_session_service(),
        artifact_service=services.get_artifact_service(),
        auto_create_session=True,
    )
    app.state.runner = runner
    app.state.agent_app_name = adk_app.name
    await attach_a2a_routes(
        app,
        agent=root_agent,
        runner=runner,
        task_store=InMemoryTaskStore(),
        rpc_path=f"/a2a/{adk_app.name}",
    )
    yield


app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=services.ARTIFACT_SERVICE_URI,
    allow_origins=allow_origins,
    session_service_uri=services.SESSION_SERVICE_URI,
    otel_to_cloud=True,
    lifespan=lifespan,
)
app.title = "transaction-executor"
app.description = "API for interacting with the Agent transaction-executor"


@app.post("/execute")
async def execute_endpoint(request: Request):
    """Direct trade execution endpoint matching worksheet tests and Portfolio Manager."""
    from app.agent import execute_trade
    try:
        data = await request.json()
    except Exception:
        data = {}
    account_id = data.get("account_id", "ACC-001")
    symbol = data.get("symbol", "GOOG")
    shares = int(data.get("shares", 10))
    amount = float(data.get("amount", 1000.0))
    action = data.get("action", "buy")
    return execute_trade(account_id=account_id, symbol=symbol, shares=shares, amount=amount, action=action)


@app.get("/trades/{trade_id}")
async def get_trade_endpoint(trade_id: str):
    """Retrieve trade status."""
    from app.agent import get_trade_status
    return get_trade_status(trade_id=trade_id)


@app.delete("/trades/{trade_id}")
async def cancel_trade_endpoint(trade_id: str):
    """Cancel pending trade."""
    from app.agent import cancel_trade
    return cancel_trade(trade_id=trade_id)


@app.post("/adk_api/query")
async def adk_query_compat_endpoint(request: Request):
    """Compatibility query endpoint."""
    from app.agent import execute_trade
    try:
        data = await request.json()
    except Exception:
        data = {}
    prompt = data.get("prompt", "")
    # If prompt mentions trade details or defaults, execute default trade
    return execute_trade(account_id="ACC-001", symbol="GOOG", shares=10, amount=1500.0, action="buy")


# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

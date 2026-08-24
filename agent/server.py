"""Finbot backend: FastAPI + AG-UI over the LangGraph agent.

Three constraints discovered the hard way (wiki/13, E11), all of which surface in the
browser only as the word "terminated":
  1. a checkpointer is mandatory -- AG-UI calls graph.aget_state()
  2. it must be AsyncSqliteSaver; the sync SqliteSaver raises NotImplementedError
  3. it cannot be built at module scope -- it needs a running event loop

Hence: everything is constructed inside async main().

Run from agent/:  uv run python server.py
"""
import os
import asyncio

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from copilotkit.langgraph_agui_agent import LangGraphAGUIAgent
from ag_ui_langgraph import add_langgraph_fastapi_endpoint
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from agent import graph_builder

CHECKPOINTS = os.environ.get("FINBOT_CHECKPOINTS", "finbot_checkpoints.db")
PORT = int(os.environ.get("PORT", 8123))


async def main():
    async with AsyncSqliteSaver.from_conn_string(CHECKPOINTS) as checkpointer:
        app = FastAPI(title="Finbot")
        app.add_middleware(
            CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
        )
        add_langgraph_fastapi_endpoint(
            app=app,
            agent=LangGraphAGUIAgent(
                name="finbot_agent",
                description="A financial analyst over 8.9M labeled card transactions.",
                graph=graph_builder.compile(checkpointer=checkpointer),
            ),
            path="/",
        )

        @app.get("/health")
        def health():
            return {"ok": True}

        await uvicorn.Server(
            uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="warning")
        ).serve()


if __name__ == "__main__":
    asyncio.run(main())

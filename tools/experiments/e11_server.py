"""E11: End-to-end stack - FastAPI + AG-UI + LangGraph + DuckDB, wired to the Next.js UI.

THREE INTEGRATION FINDINGS, each hit in sequence getting this to work:

  1. A checkpointer is MANDATORY, not optional. The AG-UI adapter calls
     graph.aget_state(config); a graph compiled with plain .compile() raises
     "ValueError: No checkpointer set" and the UI shows only "terminated".

  2. The sync SqliteSaver does NOT work. AG-UI is async and calls aget_tuple(),
     which raises "NotImplementedError: The SqliteSaver does not support async
     methods."  It must be AsyncSqliteSaver.

  3. AsyncSqliteSaver cannot be constructed at module scope - it calls
     asyncio.get_running_loop() in __init__ and raises "RuntimeError: no running
     event loop". It must be created inside a running loop.

  => The working pattern is below: build everything inside an async main() using
     AsyncSqliteSaver.from_conn_string() as an async context manager, then serve
     uvicorn programmatically from within that context.

Run from agent/ with:  uv run python ../tools/experiments/e11_server.py
"""
import os, sys, asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e9_agent_loop import b as graph_builder  # the verified DuckDB-backed agent

from fastapi import FastAPI
from copilotkit.langgraph_agui_agent import LangGraphAGUIAgent
from ag_ui_langgraph import add_langgraph_fastapi_endpoint
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import uvicorn

DB = os.environ.get("FINBOT_CHECKPOINTS", "finbot_checkpoints.db")


async def main():
    async with AsyncSqliteSaver.from_conn_string(DB) as checkpointer:
        graph = graph_builder.compile(checkpointer=checkpointer)

        app = FastAPI()
        add_langgraph_fastapi_endpoint(
            app=app,
            agent=LangGraphAGUIAgent(
                name="finbot_agent",
                description="A financial data analyst over 8.9M labeled transactions.",
                graph=graph,
            ),
            path="/",
        )

        @app.get("/health")
        def health():
            return {"ok": True}

        server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=8123, log_level="warning")
        )
        await server.serve()


if __name__ == "__main__":
    asyncio.run(main())

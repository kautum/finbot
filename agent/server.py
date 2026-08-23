from fastapi import FastAPI
from copilotkit.langgraph_agui_agent import LangGraphAGUIAgent
from ag_ui_langgraph import add_langgraph_fastapi_endpoint
from agent import graph

app = FastAPI()

add_langgraph_fastapi_endpoint(
    app=app,
    agent=LangGraphAGUIAgent(
        name="finbot_agent",
        description="A data science assistant for fintech data analysis.",
        graph=graph,
    ),
    path="/",
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8123)
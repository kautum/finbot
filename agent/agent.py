from dotenv import load_dotenv
import os
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_groq import ChatGroq
from langchain_core.tools import tool

load_dotenv()

llm = ChatGroq(
    model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
    api_key=os.getenv("GROQ_API_KEY"),
)

@tool
def ping_tool(message: str) -> str:
    """A placeholder test tool. Echoes back a message to confirm tool-calling works."""
    return f"Tool received: {message}"

tools = [ping_tool]
llm_with_tools = llm.bind_tools(tools)

def call_model(state: MessagesState):
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}

builder = StateGraph(MessagesState)
builder.add_node("agent", call_model)
builder.add_node("tools", ToolNode(tools))
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition)
builder.add_edge("tools", "agent")

graph = builder.compile()

if __name__ == "__main__":
    result = graph.invoke({"messages": [("user", "Use the ping tool to say hello to fintech")]})
    print(result["messages"][-1].content)
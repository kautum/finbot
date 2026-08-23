from dotenv import load_dotenv
import os
from langchain_groq import ChatGroq

load_dotenv()

llm = ChatGroq(
    model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
    api_key=os.getenv("GROQ_API_KEY"),
)

response = llm.invoke("In one sentence, what makes fintech data analysis interesting?")
print(response.content)
from typing import TypedDict, List, Dict, Any
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

class RoutingState(BaseModel):
    message: str
    category: str = "exercise"
    user_id: str = "1"
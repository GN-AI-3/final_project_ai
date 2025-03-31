from typing import Dict, Any
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate

class BaseAgent:
    def __init__(self, model: ChatOpenAI):
        self.model = model
        
    async def process(self, message: str) -> Dict[str, Any]:
        raise NotImplementedError("Subclasses must implement process method") 
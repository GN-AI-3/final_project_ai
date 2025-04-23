from typing import Dict, Any, List, Optional
import json
import re
from ..base_agent import BaseAgent
from langchain.prompts import ChatPromptTemplate
from common_prompts.prompts import AGENT_CONTEXT_PROMPT

class GeneralAgent(BaseAgent):
    async def process(
        self,
        message: str,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        context_info: str = "",
        **kwargs
    ) -> Dict[str, Any]:

        user_lines = [
            f"사용자: {e['content']}"
            for e in (chat_history or [])[-5:]
            if e.get("role") == "user"
        ]
        formatted_history = "\n".join(user_lines)

        summary = ""
        try:
            summary = json.loads(context_info).get("context_summary", "")
        except Exception:
            pass

        system_prompt_filled = AGENT_CONTEXT_PROMPT.format(
            chat_history=formatted_history,
            context_info=summary,
            message=message,
            user_message = message
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt_filled),
            ("human", "{message}")
        ])

        response = await (prompt | self.model).ainvoke(
            {"message": message}
        )
        return {"type": "general", "response": response.content}
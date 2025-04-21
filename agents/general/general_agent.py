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

        # 1) 최근 사용자 메시지 5개만 추림
        user_lines = [
            f"사용자: {e['content']}"
            for e in (chat_history or [])[-5:]
            if e.get("role") == "user"
        ]
        formatted_history = "\n".join(user_lines)

        # 2) context_info → JSON 파싱해서 summary만 추출
        summary = ""
        try:
            summary = json.loads(context_info).get("context_summary", "")
        except Exception:
            pass

        # 3) **프롬프트를 미리 채워 넣는다**
        system_prompt_filled = AGENT_CONTEXT_PROMPT.format(
            chat_history=formatted_history,
            context_info=summary,
            message=message,
            user_message = message
        )

        # 4) ChatPromptTemplate : 더 이상 자리표시자 없음
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt_filled),
            ("human", "{message}")    # 사용자가 방금 보낸 말
        ])

        response = await (prompt | self.model).ainvoke(
            {"message": message}
        )
        return {"type": "general", "response": response.content}
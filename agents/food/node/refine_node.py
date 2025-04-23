# refine_node.py
from langchain.schema import HumanMessage
from agents.food.llm_config import llm
from agents.food.agent_state import AgentState
import json
import re
def refine_node(state: AgentState) -> AgentState:
    user_input = state.user_input
    agent_out = state.agent_out or ""
    tool_result = state.tool_result or ""
    # ✅ 평가 생략 또는 비어 있을 경우 → tool_result로 대체
    if not agent_out.strip() or "평가 생략" in agent_out or "도구는 평가 대상이 아닙니다" in agent_out:
        raw_text = tool_result.strip()  # tool_result 값 담기
    elif tool_result.strip():
        raw_text = tool_result.strip()  # tool_result 값이 있을 경우에도 담기
    else:
        raw_text = agent_out.strip()  # agent_out 값 담기


    def extract_json(text: str) -> str:
        match = re.search(r"```(?:json)?\s*([\[{].*?[\]}])\s*```", text, re.DOTALL)
        return match.group(1).strip() if match else text.strip()

    cleaned_result = extract_json(raw_text)

    if not cleaned_result:
        return state.copy(update={
            "agent_out": "❌ 정제 실패: 응답에서 JSON을 찾을 수 없습니다."
        })

    prompt = f"""
너는 LLM 응답을 정리하는 '출력 정제기' 역할이야.

아래에 사용자의 요청과 그에 대한 JSON 응답이 주어져 있어.
이 응답이 어떤 의미를 가지는지 판단해서, 사용자에게 보여줄 설명을 작성해줘.

📥 사용자 입력:
{user_input}

📦 JSON 응답:
{cleaned_result}

→ 위 응답을 자연스럽고 따뜻한 말투로 정리해줘.
대화하는 느낌으로, "사용자가 요청한" 같은 표현은 빼고,
단순히 "OO에 대한 정보는 이렇습니다", "다음과 같아요"처럼 말해줘.
마크다운이나 특수문자 없이 텍스트로 깔끔하게 전달해줘.

중요한 점:
- 불필요한 설명은 생략하고,
- 응답의 핵심 내용을 자연스럽게 말하듯 전달해줘.
"""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        refined = response.content.strip()
        return state.copy(update={
            "agent_out": f"{refined}"
        })
    except Exception as e:
        return state.copy(update={
            "agent_out": f"❌ 정제 중 오류 발생: {e}"
        })
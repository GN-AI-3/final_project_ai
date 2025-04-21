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
        raw_text = tool_result.strip()
    else:
        raw_text = agent_out.strip()


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

--- (생략) ---

📥 사용자 입력:
{user_input}

📦 JSON 응답:
{cleaned_result}

→ 위 응답을 사람이 이해할 수 있도록 마크다운을 제거하고, 
좀 더 자연스럽고 읽기 쉽게 정리해서 설명해줘. 
특수문자도 제거해서 깔끔한 텍스트로 바꿔줘.

"""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        refined = response.content.strip()
        return state.copy(update={
            "agent_out": f"🪄 정제된 설명:\n{refined}"
        })
    except Exception as e:
        return state.copy(update={
            "agent_out": f"❌ 정제 중 오류 발생: {e}"
        })
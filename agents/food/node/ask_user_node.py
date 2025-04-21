# 📍 ask_user_node.py
from agents.food.agent_state import AgentState


def ask_user_node(state: AgentState) -> AgentState:
    """
    planner에서 ask_user 항목이 있으면 질문만 출력하고,
    그래프는 종료되며 사용자의 응답을 기다린다.
    이후 resume()으로 다시 시작해야 한다.
    """
    parsed_plan = state.parsed_plan or {}
    ask_user = parsed_plan.get("ask_user")

    if not ask_user:
        return AgentState(
            user_input=state.user_input,
            member_id=state.member_id,
            agent_out="❓ 질문 항목이 없습니다."
        )

    # 질문 형식 정리
    if isinstance(ask_user, list):
        question_text = "\n".join([f"- {q}" for q in ask_user])
    else:
        question_text = f"- {ask_user}"

    return AgentState(
        user_input=state.user_input,
        member_id=state.member_id,
        agent_out=f"❓ 다음 질문에 답해주세요:\n{question_text}"
        # ✅ 여기서 그래프 종료됨 → resume으로 이어져야 함!
    )

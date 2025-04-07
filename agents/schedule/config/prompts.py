from langchain.prompts import ChatPromptTemplate


def get_schedule_agent_prompt() -> ChatPromptTemplate:
    """일정 관리 에이전트의 프롬프트 템플릿을 반환합니다.
    
    Returns:
        ChatPromptTemplate: 일정 관리 에이전트의 프롬프트 템플릿
    """
    return ChatPromptTemplate.from_messages([
        ("system", "당신은 일정 관리 전문가입니다. 사용자의 일정 관련 질문에 대해 전문적으로 답변해주세요."),
        ("user", "{message}")
    ]) 
from typing import Dict, Any

from langchain_core.messages import HumanMessage, AIMessage

from chatbot import call_chatbot


def ai_assistant_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """AI 어시스턴트의 응답을 생성하고 출력합니다.
    
    Args:
        state: 현재 상태 딕셔너리
        
    Returns:
        Dict[str, Any]: 업데이트된 상태 딕셔너리
    """
    print("\n")
    messages = state["messages"]
    ai_response = call_chatbot(messages, session_id="default")
    print(f"\033[1;32m예약 도우미\033[0m: {ai_response}")
    return {"messages": messages + [AIMessage(content=ai_response)]}


def user_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """사용자 입력을 받아 처리합니다.
    
    Args:
        state: 현재 상태 딕셔너리
        
    Returns:
        Dict[str, Any]: 업데이트된 상태 딕셔너리
    """
    print("\n")
    user_input = input(f"\033[1;36m사용자\033[0m: ")
    if user_input.strip().upper() == "종료":
        return {"messages": state["messages"] + [HumanMessage(content="종료")]}
    return {"messages": state["messages"] + [HumanMessage(content=user_input)]} 
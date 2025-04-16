from typing import Dict, Any, Callable
from langchain_core.messages import HumanMessage, AIMessage

def create_ai_assistant_node(chatbot_func: Callable) -> Callable:
    """AI 어시스턴트 노드를 생성하는 팩토리 함수
    
    Args:
        chatbot_func: 챗봇 함수 (messages, session_id를 받아 응답을 반환)
        
    Returns:
        Callable: AI 어시스턴트 노드 함수
    """
    def ai_assistant_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """AI 어시스턴트의 응답을 생성하고 출력합니다.
        
        Args:
            state: 현재 상태 딕셔너리
            
        Returns:
            Dict[str, Any]: 업데이트된 상태 딕셔너리
        """
        messages = state["messages"]
        ai_response = chatbot_func(messages, session_id="default")
        return {"messages": messages + [AIMessage(content=ai_response)]}
    return ai_assistant_node

def user_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """사용자 메시지를 처리합니다.
    
    Args:
        state: 현재 상태 딕셔너리
        
    Returns:
        Dict[str, Any]: 업데이트된 상태 딕셔너리
    """
    return {"messages": state["messages"]} 
from typing import Dict, Any, List, Optional
from ..base_agent import BaseAgent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from .workflows.workout_workflow import create_workout_workflow
from .models.state_models import RoutingState
from dotenv import load_dotenv
from IPython.display import Image, display

load_dotenv()

class ExerciseAgent(BaseAgent):
    # chat_history를 지원함을 나타내는 속성 추가
    supports_chat_history = False
    
    @staticmethod
    def convert_messages_to_serializable(messages):
        """메시지 객체를 직렬화 가능한 형태로 변환"""
        serializable_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                serializable_messages.append(msg)
            elif isinstance(msg, (AIMessage, HumanMessage, ToolMessage)):
                serializable_messages.append({
                    "type": msg.__class__.__name__,
                    "content": msg.content,
                    "additional_kwargs": msg.additional_kwargs
                })
            else:
                serializable_messages.append(str(msg))
        return serializable_messages

    async def process(self, message: str, member_id: Optional[int] = None, user_type: Optional[str] = None, chat_history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        메인 실행 함수
        
        Args:
            message: 사용자 메시지
            member_id: 회원 ID
            user_type: 사용자 타입 ("member" 또는 "trainer")
            chat_history: 대화 내역 (선택사항, 현재 사용하지 않음)
        """
        # 기본값 설정
        if user_type is None:
            user_type = "member"  # 기본값은 member
            
        # member_id와 trainer_id 설정
        trainer_id = 1  # 트레이너 ID는 항상 1로 고정
        
        # member_id가 None인 경우 기본값 설정 (RoutingState에서 None이 허용되지 않음)
        if member_id is None:
            member_id = 0  # 기본값으로 0 설정
            
        # 트레이너 타입인 경우 member_id를 기본값으로 설정
        if user_type == "trainer":
            member_id = 0  # 트레이너인 경우 member_id는 기본값으로 설정

        workflow = create_workout_workflow()

        initial_state = RoutingState(
            message=message,
            user_type=user_type,
            member_id=member_id,
            trainer_id=trainer_id
        )

        # 워크플로우 실행
        final_state = workflow.invoke(initial_state)

        try:
            display(Image(workflow.get_graph().draw_mermaid_png()))
        except Exception:
            pass

        return {"type": "exercise", "response": final_state["result"]}
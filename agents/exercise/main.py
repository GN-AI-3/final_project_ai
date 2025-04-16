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

    async def process(self, message: str, email: Optional[str] = None, chat_history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        메인 실행 함수
        
        Args:
            message: 사용자 메시지
            email: 사용자 이메일 (선택사항, 현재 사용하지 않음)
            chat_history: 대화 내역 (선택사항, 현재 사용하지 않음)
        """
        # email과 chat_history는 현재 사용하지 않지만 매개변수로 받을 수 있도록 함

        workflow = create_workout_workflow()

        initial_state = RoutingState(
            message=message,
            user_type="member",
            member_id=3,
            trainer_id=1
        )

        # 워크플로우 실행
        final_state = workflow.invoke(initial_state)

        try:
            display(Image(workflow.get_graph().draw_mermaid_png()))
        except Exception:
            pass

        return {"type": "exercise", "response": final_state["result"]}
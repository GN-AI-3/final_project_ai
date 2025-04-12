from typing import Dict, Any
from ..base_agent import BaseAgent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from .workflows.workout_workflow import create_workout_workflow
from .models.state_models import RoutingState
from dotenv import load_dotenv
from IPython.display import Image, display

load_dotenv()

class ExerciseAgent(BaseAgent):
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

    async def process(self, message: str) -> Dict[str, Any]:
        """메인 실행 함수"""

        workflow = create_workout_workflow()

        initial_state = RoutingState(
            message=message
        )

        # 워크플로우 실행
        final_state = workflow.invoke(initial_state)

        try:
            display(Image(workflow.get_graph().draw_mermaid_png()))
        except Exception:
            pass

        return {"type": "exercise", "response": final_state["result"]}
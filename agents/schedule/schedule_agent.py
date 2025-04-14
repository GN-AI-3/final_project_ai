from typing import Dict, Any
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from ..base_agent import BaseAgent
from .graph import build_graph


class ScheduleAgent(BaseAgent):
    """스케줄 예약 에이전트 클래스"""
    
    def __init__(self, model):
        super().__init__(model)
        self.graph = build_graph()
    
    async def process(self, message: str) -> Dict[str, Any]:
        """사용자 메시지 처리
        
        Args:
            message: 사용자 메시지
            
        Returns:
            처리 결과 딕셔너리
        """
        try:
            # 입력 준비
            inputs = {
                "messages": [HumanMessage(content=message)]
            }
            
            # 그래프 실행 설정
            config = RunnableConfig(
                recursion_limit=2147483647,
                configurable={"thread_id": "7"}
            )
            
            # 그래프 실행 및 응답 수집
            response = ""
            for chunk in self.graph.stream(inputs, config):
                if "messages" in chunk:
                    response = chunk["messages"][-1].content
                    
            return {"type": "schedule", "response": response}
        except Exception as e:
            return {"type": "error", "response": f"오류가 발생했습니다: {str(e)}"}
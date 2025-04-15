from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
import json
import traceback

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
            formatted_response = ""
            raw_data = None
            last_message = None
            
            for chunk in self.graph.stream(inputs, config):
                if "messages" in chunk:
                    for msg in chunk["messages"]:
                        last_message = msg
                        # 도구의 JSON 응답을 파싱하여 처리
                        try:
                            tool_result = json.loads(msg.content)
                            if "success" in tool_result:
                                if tool_result["success"]:
                                    # 성공한 경우 원본 데이터 저장
                                    raw_data = tool_result
                                    
                                    # 결과에 따라 다른 메시지 생성
                                    if "results" in tool_result:
                                        # 스케줄 조회 결과
                                        formatted_response = tool_result.get("results", "예약 일정을 찾을 수 없습니다.")
                                    elif "reservation" in tool_result:
                                        # 예약 추가/변경 결과
                                        reservation = tool_result.get("reservation", {})
                                        formatted_response = f"예약이 완료되었습니다.\n예약 번호: {reservation.get('reservation_id', '')}\n시작 시간: {reservation.get('start_time', '')}\n종료 시간: {reservation.get('end_time', '')}"
                                    elif "action" in tool_result:
                                        # 예약 취소/변경 결과
                                        action = tool_result.get("action", "")
                                        if action == "cancel":
                                            reservation = tool_result.get("reservation", {})
                                            formatted_response = f"예약이 취소되었습니다.\n예약 번호: {reservation.get('reservation_id', '')}\n취소 사유: {reservation.get('reason', '')}"
                                        elif action == "change":
                                            old_schedule = tool_result.get("old_schedule", {})
                                            new_schedule = tool_result.get("new_schedule", {})
                                            formatted_response = f"예약이 변경되었습니다.\n기존 예약: {old_schedule.get('start_time', '')}\n새 예약: {new_schedule.get('start_time', '')}\n변경 사유: {new_schedule.get('reason', '')}"
                                    else:
                                        formatted_response = "작업이 완료되었습니다."
                                else:
                                    # 실패한 경우 에러 메시지를 전달
                                    formatted_response = tool_result.get("error", "알 수 없는 오류가 발생했습니다.")
                            else:
                                # 일반 메시지인 경우 그대로 전달
                                formatted_response = msg.content
                        except json.JSONDecodeError:
                            # JSON 파싱 실패 시 일반 메시지로 처리
                            formatted_response = msg.content
            
            # 마지막 메시지만 사용
            if last_message and isinstance(last_message, AIMessage):
                formatted_response = last_message.content
            
            return {
                "type": "schedule",
                "response": formatted_response,
                "data": raw_data
            }
                
        except Exception as e:
            # 에러 메시지를 안전하게 생성
            error_message = "알 수 없는 오류가 발생했습니다."
            try:
                error_message = str(e).strip()
                if not error_message:
                    error_message = "알 수 없는 오류가 발생했습니다."
            except:
                pass
                
            return {
                "type": "schedule",
                "response": error_message,
                "data": None
            }
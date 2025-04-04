"""
동기부여 응답 생성 도구 모듈
"""
import json
import logging
from typing import Dict, Any

# 로깅 설정
logger = logging.getLogger(__name__)

class MotivationResponseTool:
    """감정과 메시지에 기반하여 맞춤형 동기부여 응답을 생성하는 도구"""
    
    @staticmethod
    def get_tool_config() -> Dict[str, Any]:
        """
        동기부여 응답 생성 도구 구성을 반환합니다.
        
        Returns:
            Dict[str, Any]: 도구 구성
        """
        return {
            "type": "function",
            "function": {
                "name": "generate_motivation_response",
                "description": "감정과 메시지에 기반하여 맞춤형 동기부여 응답을 생성합니다",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "response": {
                            "type": "string",
                            "description": "생성된 동기부여 응답"
                        },
                        "strategy": {
                            "type": "string",
                            "description": "사용된 동기부여 전략 (emotional_comfort, motivation_boost, encouragement, confidence_building 중 하나)"
                        }
                    },
                    "required": ["response", "strategy"]
                }
            }
        }
    
    @staticmethod
    def process_response(tool_call: Any) -> Dict[str, Any]:
        """
        도구 호출 응답을 처리합니다.
        
        Args:
            tool_call: 도구 호출 응답
            
        Returns:
            Dict[str, Any]: 처리된 응답 데이터
        """
        response_data = {
            "response": "현재 당신의 상황을 이해하려 노력하고 있습니다. 어려운 시간을 보내고 계신 것 같은데, 조금씩 나아질 거예요.",
            "strategy": "motivation_boost"
        }
        
        try:
            if tool_call and tool_call.function.name == "generate_motivation_response":
                function_args = json.loads(tool_call.function.arguments)
                response_data = {
                    "response": function_args.get("response", response_data["response"]),
                    "strategy": function_args.get("strategy", response_data["strategy"])
                }
                logger.info(f"동기부여 응답 생성 완료, 전략: {response_data['strategy']}")
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"동기부여 응답 도구 처리 중 오류: {str(e)}")
        
        return response_data 
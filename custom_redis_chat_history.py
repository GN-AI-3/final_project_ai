"""
기본 Redis 명령어만 사용하는 대화 내역 관리 모듈
"""
import json
import logging
from typing import List, Optional
from redis import Redis
from datetime import datetime

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

logger = logging.getLogger(__name__)

class CustomRedisChatHistory:
    """
    기본 Redis 명령어만 사용하는 대화 내역 관리 클래스
    RediSearch 의존성 없이 작동합니다.
    """
    
    def __init__(self, session_id: str, redis_client: Redis, ttl: Optional[int] = None):
        """
        CustomRedisChatHistory 초기화
        
        Args:
            session_id: 대화 세션 ID
            redis_client: Redis 클라이언트 객체
            ttl: 대화 내역 유효 기간 (초 단위)
        """
        self.redis_client = redis_client
        self.session_id = session_id
        self.ttl = ttl
        
    @property
    def messages(self) -> List[BaseMessage]:
        """
        저장된 모든 메시지를 조회합니다.
        
        Returns:
            List[BaseMessage]: 메시지 목록
        """
        try:
            # Redis에서 메시지 목록 조회
            message_data = self.redis_client.lrange(self.session_id, 0, -1)
            
            # 결과 역순으로 정렬 (최신 메시지가 마지막에 위치하도록)
            message_data.reverse()
            
            result = []
            for item in message_data:
                # JSON 문자열을 딕셔너리로 변환
                message_dict = json.loads(item)
                message = self._dict_to_message(message_dict)
                if message:
                    result.append(message)
            
            return result
        except Exception as e:
            logger.error(f"대화 내역 조회 오류: {str(e)}")
            return []
    
    def add_message(self, message: BaseMessage) -> None:
        """
        메시지를 추가합니다.
        
        Args:
            message: 추가할 메시지
        """
        try:
            # 메시지를 JSON 형식으로 변환
            message_dict = self._message_to_dict(message)
            message_str = json.dumps(message_dict)
            
            # Redis 리스트에 추가
            self.redis_client.lpush(self.session_id, message_str)
            
            # TTL 설정 (첫 메시지인 경우에만)
            if self.ttl is not None:
                self.redis_client.expire(self.session_id, self.ttl)
                
            logger.debug(f"메시지 추가: {message_dict['role']}")
        except Exception as e:
            logger.error(f"메시지 추가 오류: {str(e)}")
    
    def clear(self) -> None:
        """대화 내역을 모두 삭제합니다."""
        try:
            self.redis_client.delete(self.session_id)
            logger.debug(f"대화 내역 삭제 완료: {self.session_id}")
        except Exception as e:
            logger.error(f"대화 내역 삭제 오류: {str(e)}")
    
    def _message_to_dict(self, message: BaseMessage) -> dict:
        """BaseMessage 객체를 딕셔너리로 변환합니다."""
        result = {
            "content": message.content,
            "additional_kwargs": message.additional_kwargs,
            "created_at": datetime.now().isoformat()
        }
        
        if isinstance(message, HumanMessage):
            result["role"] = "user"
        elif isinstance(message, AIMessage):
            result["role"] = "assistant"
        elif isinstance(message, SystemMessage):
            result["role"] = "system"
        else:
            result["role"] = "unknown"
            
        return result
    
    def _dict_to_message(self, message_dict: dict) -> Optional[BaseMessage]:
        """딕셔너리를 BaseMessage 객체로 변환합니다."""
        try:
            role = message_dict.get("role")
            content = message_dict.get("content", "")
            additional_kwargs = message_dict.get("additional_kwargs", {})
            
            if role == "user":
                return HumanMessage(content=content, additional_kwargs=additional_kwargs)
            elif role == "assistant":
                return AIMessage(content=content, additional_kwargs=additional_kwargs)
            elif role == "system":
                return SystemMessage(content=content, additional_kwargs=additional_kwargs)
            else:
                logger.warning(f"알 수 없는 메시지 역할: {role}")
                return None
        except Exception as e:
            logger.error(f"메시지 변환 오류: {str(e)}")
            return None 
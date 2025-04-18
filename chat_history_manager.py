import os
import re
import json
import redis

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# .env 로드 (단순화)
load_dotenv()

class ChatHistoryManager:
    """
    Manages chat history for users using Redis (if available) or in-memory storage.
    """
    def __init__(self):
        self.use_redis = False
        self.in_memory_storage: Dict[str, List[Dict[str, Any]]] = {}
        self.max_history = 20
        self.redis_client: Optional[redis.Redis] = None

        # Redis 환경변수
        redis_host = os.getenv("REDIS_HOST")
        redis_port = int(os.getenv("REDIS_PORT"))
        redis_password = os.getenv("REDIS_PASSWORD")
        redis_db = int(os.getenv("REDIS_DB"))

        try:
            # Redis 연결 시도
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password or None,
                db=redis_db,
                decode_responses=True,
                socket_timeout=5
            )
            if self.redis_client.ping():
                logger.info("✅ Redis 연결 성공")
                print("Redis 연결 성공")
                self.use_redis = True
        except Exception as e:
            logger.warning(f"Redis 연결 실패: {str(e)}, 메모리 저장소 사용")
            print("Redis 연결 실패: ", str(e))

    def _get_user_key(self, email: str) -> str:
        return f"chat_history:{email}"
    
    def _get_workout_log_key(self, memberId: int, date: str) -> str:
        return f"workout_history:{memberId}:{date}"
    
    def _get_pt_log_key(self, ptScheduleId: int) -> str:
        return f"pt_history:{ptScheduleId}"

    def _trim_history_in_redis(self, user_key: str):
        total_count = self.redis_client.llen(user_key)
        if total_count > self.max_history:
            self.redis_client.ltrim(user_key, total_count - self.max_history, -1)

    def _trim_history_in_memory(self, email: str):
        if len(self.in_memory_storage[email]) > self.max_history:
            self.in_memory_storage[email] = self.in_memory_storage[email][-self.max_history:]

    def add_chat_entry(
        self,
        email: str,
        role: str,
        message: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a single message to the chat history.
        role: 'user' or 'assistant'
        """
        try:
            # 내부 저장 구조: role='user'/'ai' 로 통일
            normalized_role = "ai" if role == "assistant" else "user"
            entry = {
                "role": normalized_role,
                "content": message,
                "timestamp": datetime.now().isoformat()
            }
            if additional_data:
                entry.update(additional_data)

            if self.use_redis and self.redis_client:
                user_key = self._get_user_key(email)
                self.redis_client.rpush(user_key, json.dumps(entry))
                self._trim_history_in_redis(user_key)
            else:
                if email not in self.in_memory_storage:
                    self.in_memory_storage[email] = []
                self.in_memory_storage[email].append(entry)
                self._trim_history_in_memory(email)

            return True
        except Exception as e:
            logger.error(f"add_chat_entry 오류: {str(e)}")
            return False

    def add_workout_log_entry(
        self,
        memberId: int,
        date: str,
        role: str,
        message: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        try:
            normalized_role = "ai" if role == "assistant" else "user"
            entry = {
                "role": normalized_role,
                "content": message,
                "timestamp": datetime.now().isoformat()
            }
            if additional_data:
                entry.update(additional_data)

            if self.use_redis and self.redis_client:
                user_key = self._get_workout_log_key(memberId, date)
                self.redis_client.rpush(user_key, json.dumps(entry))
                self._trim_history_in_redis(user_key)
            else:
                if memberId not in self.in_memory_storage:
                    self.in_memory_storage[memberId] = {}
                if date not in self.in_memory_storage[memberId]:
                    self.in_memory_storage[memberId][date] = []
                self.in_memory_storage[memberId][date].append(entry)
                self._trim_history_in_memory(memberId)
            
            return True
        except Exception as e:
            logger.error(f"add_workout_log_entry 오류: {str(e)}")
            return False
    
    def add_pt_log_entry(
        self,
        ptScheduleId: int,
        role: str,
        message: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        try:
            normalized_role = "ai" if role == "assistant" else "user"
            entry = {
                "role": normalized_role,
                "content": message,
                "timestamp": datetime.now().isoformat()
            }
            if additional_data:
                entry.update(additional_data)

            if self.use_redis and self.redis_client:
                user_key = self._get_pt_log_key(ptScheduleId)
                self.redis_client.rpush(user_key, json.dumps(entry))
                self._trim_history_in_redis(user_key)
            else:
                if ptScheduleId not in self.in_memory_storage:
                    self.in_memory_storage[ptScheduleId] = []
                self.in_memory_storage[ptScheduleId].append(entry)
                self._trim_history_in_memory(ptScheduleId)

            return True
        except Exception as e:
            logger.error(f"add_pt_log_entry 오류: {str(e)}")
            return False
            
    def get_recent_messages(self, email: str, limit: int = 6) -> List[Dict[str, Any]]:
        """
        Return up to 'limit' most recent messages for a user.
        """
        limit = min(limit, self.max_history)
        try:
            if self.use_redis and self.redis_client:
                user_key = self._get_user_key(email)
                total = self.redis_client.llen(user_key)
                if total == 0:
                    return []
                start_index = max(0, total - limit)
                raw_messages = self.redis_client.lrange(user_key, start_index, -1)
                parsed = []
                for msg_json in raw_messages:
                    try:
                        parsed.append(json.loads(msg_json))
                    except:
                        pass
                return parsed
            else:
                if email not in self.in_memory_storage:
                    return []
                return self.in_memory_storage[email][-limit:]
        except Exception as e:
            logger.error(f"get_recent_messages 오류: {str(e)}")
            return []

    def get_recent_messages_by_pt_log_key(self, ptScheduleId: int, limit: int = 6) -> List[Dict[str, Any]]:
        """
        Return up to 'limit' most recent messages for a user.
        """
        limit = min(limit, self.max_history)
        try:
            if self.use_redis and self.redis_client:
                user_key = self._get_pt_log_key(ptScheduleId)
                total = self.redis_client.llen(user_key)
                if total == 0:
                    return []
                start_index = max(0, total - limit)
                raw_messages = self.redis_client.lrange(user_key, start_index, -1)
                parsed = []
                for msg_json in raw_messages:
                    try:
                        parsed.append(json.loads(msg_json))
                    except:
                        pass
                return parsed
            else:
                if ptScheduleId not in self.in_memory_storage:
                    return []
                return self.in_memory_storage[ptScheduleId][-limit:]
        except Exception as e:
            logger.error(f"get_recent_messages_by_pt_log_key 오류: {str(e)}")
            return []
        
    def get_recent_messages_by_workout_log_key(self, memberId: int, date: str, limit: int = 6) -> List[Dict[str, Any]]:
        """
        Return up to 'limit' most recent messages for a user.
        """
        limit = min(limit, self.max_history)

        try:
            if self.use_redis and self.redis_client:
                user_key = self._get_workout_log_key(memberId, date)
                total = self.redis_client.llen(user_key)
                if total == 0:
                    return []
                start_index = max(0, total - limit)
                raw_messages = self.redis_client.lrange(user_key, start_index, -1)
                parsed = []
                for msg_json in raw_messages:
                    try:
                        parsed.append(json.loads(msg_json))
                    except:
                        pass
                return parsed
            else:
                if memberId not in self.in_memory_storage:
                    return []
                return self.in_memory_storage[memberId][date][-limit:]
        except Exception as e:
            logger.error(f"get_recent_messages_by_workout_log_key 오류: {str(e)}")
            return []

    def clear_history(self, email: str) -> bool:
        """
        Clear chat history for a user.
        """
        try:
            if self.use_redis and self.redis_client:
                self.redis_client.delete(self._get_user_key(email))
            else:
                self.in_memory_storage[email] = []
            return True
        except Exception as e:
            logger.error(f"clear_history 오류: {str(e)}")
            return False

    def get_formatted_history(self, email: str, limit: int = 6) -> List[Dict[str, str]]:
        """
        Return a list of messages in a format suitable for LLM (role: user/assistant).
        """
        messages = self.get_recent_messages(email, limit)
        formatted = []
        for msg in messages:
            role = "assistant" if msg["role"] == "ai" else "user"
            formatted.append({
                "role": role,
                "content": msg["content"]
            })
        return formatted

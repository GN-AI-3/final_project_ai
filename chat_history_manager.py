import redis
from typing import List, Dict, Any, Optional
import json
import logging
from datetime import datetime
import os
import re
import pathlib
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 수동으로 .env 파일 읽기 함수
def read_env_file(path):
    env_vars = {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                match = re.match(r'^([A-Za-z0-9_]+)=(.*)$', line)
                if match:
                    key = match.group(1)
                    value = match.group(2).strip('"').strip("'")
                    env_vars[key] = value
                    # 환경변수로도 설정
                    os.environ[key] = value
        
        logger.info(f"수동으로 .env 파일 읽기 완료. {len(env_vars)}개 변수 로드됨.")
        return env_vars
    except Exception as e:
        logger.error(f"⚠️ .env 파일 읽기 오류: {str(e)}")
        return {}

# 환경 변수 로드 (명시적 경로 지정)
current_dir = pathlib.Path(__file__).parent.absolute()
env_path = pathlib.Path(current_dir, '.env')

# 명시적 경로로 .env 파일 로드 시도
if env_path.exists():
    # 기본 방식으로 로드
    load_dotenv(dotenv_path=env_path)
    logger.info(f".env 파일 로드 완료 (경로: {env_path})")
    
    # 추가로 수동 파싱
    env_vars = read_env_file(env_path)
else:
    # 상위 디렉토리에서 .env 파일 찾기
    logger.info("현재 디렉토리에서 .env 파일을 찾을 수 없습니다. 상위 디렉토리 검색...")
    parent_env_path = pathlib.Path(current_dir).parent / '.env'
    if parent_env_path.exists():
        load_dotenv(dotenv_path=parent_env_path)
        logger.info(f"상위 디렉토리의 .env 파일 로드 완료: {parent_env_path}")
        
        # 추가로 수동 파싱
        env_vars = read_env_file(parent_env_path)
    else:
        logger.info("기본 방식으로 .env 파일 로드")
        load_dotenv()
        env_vars = {}

class ChatHistoryManager:
    """
    Manages chat history for users using Redis as a backend storage
    """
    
    def __init__(self):
        """Initialize the chat history manager with in-memory storage or Redis"""
        self.use_redis = False
        self.in_memory_storage = {}
        self.max_history = 20
        self.redis_client = None
        
        # Redis 연결 시도
        try:
            # 환경 변수 또는 수동 파싱에서 Redis 설정 가져오기
            redis_host = env_vars.get("REDIS_HOST") or os.getenv("REDIS_HOST")
            redis_port_str = env_vars.get("REDIS_PORT") or os.getenv("REDIS_PORT")
            redis_password = env_vars.get("REDIS_PASSWORD") or os.getenv("REDIS_PASSWORD")
            redis_db_str = env_vars.get("REDIS_DB") or os.getenv("REDIS_DB")
            
            # 환경 변수 상태 로깅
            logger.info(f"[Redis 설정] 호스트: {redis_host}")
            logger.info(f"[Redis 설정] 포트: {redis_port_str}")
            logger.info(f"[Redis 설정] 비밀번호: {'설정됨' if redis_password else '없음'}")
            logger.info(f"[Redis 설정] DB: {redis_db_str}")
            
            # 포트와 DB 번호 정수 변환
            try:
                redis_port = int(redis_port_str)
            except (ValueError, TypeError):
                logger.error("❌ 잘못된 포트 번호. 기본값 6379 사용")
                redis_port = 6379
                
            try:
                redis_db = int(redis_db_str)
            except (ValueError, TypeError):
                logger.error("❌ 잘못된 DB 번호. 기본값 0 사용")
                redis_db = 0
            
            logger.info(f"[Redis 연결 시도] {redis_host}:{redis_port}, DB: {redis_db}")
            
            # Redis 클라이언트 초기화 (비밀번호 유무에 따라)
            if redis_password:
                logger.info("비밀번호를 사용하여 Redis 연결 시도")
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    password=redis_password,
                    db=redis_db,
                    decode_responses=True,
                    socket_timeout=5
                )
            else:
                logger.info("비밀번호 없이 Redis 연결 시도")
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    decode_responses=True,
                    socket_timeout=5
                )
            
            # 연결 테스트
            if self.redis_client.ping():
                logger.info("✅ Redis 연결 성공!")
                self.use_redis = True
            else:
                logger.warning("⚠️ Redis ping 실패. 메모리 저장소로 전환")
                self.redis_client = None
                
        except redis.exceptions.AuthenticationError as e:
            logger.error(f"❌ Redis 인증 오류: {str(e)}")
            # 인증 오류 시 바로 메모리 저장소로 전환
            logger.info("📝 인증 오류로 메모리 저장소 사용")
            self.redis_client = None
                
        except redis.exceptions.ConnectionError as e:
            logger.error(f"❌ Redis 연결 오류: {str(e)}")
            logger.error("Redis 서버가 실행 중인지 확인하세요.")
            self.redis_client = None
            
        except Exception as e:
            logger.error(f"❌ Redis 초기화 실패: {str(e)}")
            logger.info("🔄 메모리 저장소 사용")
            import traceback
            logger.error(traceback.format_exc())
            self.redis_client = None
        
        # Redis 연결 실패 시 메모리 저장소 사용 알림
        if not self.use_redis:
            logger.info("📝 메모리 저장소로 전환: Redis 연결 실패")
    
    def _get_user_key(self, email: str) -> str:
        """Generate a Redis key for the user's chat history"""
        return f"chat_history:{email}"
    
    def add_user_message(self, email: str, message: str) -> None:
        """Add a user message to the chat history"""
        logger.info(f"[사용자 메시지 저장] 이메일: {email}, 길이: {len(message)}")
        self._add_message(email, "user", message)
    
    def add_ai_message(self, email: str, message: str) -> None:
        """Add an AI message to the chat history"""
        logger.info(f"[AI 메시지 저장] 이메일: {email}, 길이: {len(message)}")
        self._add_message(email, "ai", message)
    
    def _add_message(self, email: str, role: str, message: str, additional_data: Dict[str, Any] = None) -> None:
        """
        Add a message to the user's chat history
        
        Args:
            email: User email
            role: Message role ('user' or 'ai')
            message: Message content
            additional_data: Additional data to store with the message
        """
        try:
            # 메시지 데이터 생성
            message_data = {
                "role": role,
                "content": message,
                "timestamp": datetime.now().isoformat()
            }
            
            # 추가 데이터가 있으면 병합
            if additional_data:
                message_data.update(additional_data)
            
            if self.use_redis and self.redis_client:
                # Redis 저장
                user_key = self._get_user_key(email)
                json_data = json.dumps(message_data)
                
                # 메시지 저장
                result = self.redis_client.rpush(user_key, json_data)
                
                # 메시지 수 제한
                total_count = self.redis_client.llen(user_key)
                if total_count > self.max_history:
                    # 앞에서부터 초과분 제거
                    excess = total_count - self.max_history
                    self.redis_client.ltrim(user_key, excess, -1)
                
                # 결과 확인
                logger.info(f"[Redis 저장 완료] 이메일: {email}, 역할: {role}, 메시지 수: {total_count}")
            else:
                # 메모리 저장
                if email not in self.in_memory_storage:
                    self.in_memory_storage[email] = []
                
                # 메시지 추가 (시간순으로 저장)
                self.in_memory_storage[email].append(message_data)
                
                # 메시지 수 제한
                if len(self.in_memory_storage[email]) > self.max_history:
                    self.in_memory_storage[email] = self.in_memory_storage[email][-self.max_history:]
                
                logger.info(f"[메모리 저장 완료] 이메일: {email}, 역할: {role}, 메시지 수: {len(self.in_memory_storage[email])}")
                
        except Exception as e:
            logger.error(f"[메시지 저장 오류] 이메일: {email}, 역할: {role}, 오류: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
    
    def get_recent_messages(self, email: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the most recent messages for a user"""
        try:
            logger.info(f"[대화 내역 조회] 이메일: {email}, 요청 개수: {limit}")
            
            # 요청된 limit이 max_history를 초과하지 않도록 조정
            limit = min(limit, self.max_history)
            messages = []
            
            if self.use_redis and self.redis_client:
                # Redis에서 조회
                user_key = self._get_user_key(email)
                
                # 저장된 메시지 수 확인
                total_count = self.redis_client.llen(user_key)
                logger.info(f"[Redis 조회] 키: {user_key}, 총 메시지 수: {total_count}")
                
                if total_count == 0:
                    return []
                
                # 최근 메시지 가져오기 (오래된 순)
                start_index = max(0, total_count - limit)
                raw_messages = self.redis_client.lrange(user_key, start_index, -1)
                
                # 메시지 파싱
                for msg_json in raw_messages:
                    try:
                        msg_data = json.loads(msg_json)
                        messages.append(msg_data)
                    except json.JSONDecodeError:
                        logger.error(f"[JSON 파싱 오류] 메시지: {msg_json[:100]}...")
                
                logger.info(f"[Redis 조회 완료] 이메일: {email}, 조회된 메시지 수: {len(messages)}")
            else:
                # 메모리에서 조회
                if email in self.in_memory_storage:
                    # 최신 메시지만 가져옴
                    messages = self.in_memory_storage[email][-limit:]
                    logger.info(f"[메모리 조회 완료] 이메일: {email}, 조회된 메시지 수: {len(messages)}")
                else:
                    logger.info(f"[메모리 조회] 이메일: {email} 기록 없음")
            
            return messages
        
        except Exception as e:
            logger.error(f"[대화 내역 조회 오류] 이메일: {email}, 오류: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def clear_history(self, email: str) -> bool:
        """Clear the chat history for a user"""
        try:
            if self.use_redis and self.redis_client:
                user_key = self._get_user_key(email)
                self.redis_client.delete(user_key)
                logger.info(f"✅ 대화 내역 삭제 완료: {email}")
            else:
                # Fallback to in-memory storage
                if email in self.in_memory_storage:
                    self.in_memory_storage[email] = []
                    logger.info(f"✅ 대화 내역 삭제 완료: {email} (메모리 저장소)")
            
            return True  # 항상 True 반환
        
        except Exception as e:
            logger.error(f"❌ 대화 내역 삭제 중 오류: {str(e)}")
            return False  # 오류 발생 시 False 반환
    
    def get_formatted_history(self, email: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Get formatted chat history in a format suitable for LLM context
        Returns a list of dictionaries with 'role' and 'content' keys
        """
        try:
            # 요청된 limit이 max_history를 초과하지 않도록 조정
            limit = min(limit, self.max_history)
            messages = self.get_recent_messages(email, limit)
            
            # Format messages for LLM context
            formatted_messages = []
            for msg in messages:
                formatted_messages.append({
                    "role": "user" if msg["role"] == "user" else "assistant",
                    "content": msg["content"]
                })
            
            return formatted_messages
        
        except Exception as e:
            logger.error(f"Error formatting chat history: {str(e)}")
            return []
            
    async def get_chat_history(self, email: str, limit: int = 20, user_type: str = None) -> List[Dict[str, Any]]:
        """
        Get chat history for a user.
        This is an async wrapper for get_recent_messages to support async calls.
        
        Args:
            email: User email
            limit: Maximum number of messages to return
            user_type: Type of user ('member' or 'trainer')
            
        Returns:
            List of chat messages in chronological order
        """
        logger.info(f"[대화 내역 조회 요청] 이메일: {email}, 최대 개수: {limit}, 사용자 타입: {user_type}")
        
        # 기본 목록 얻기
        messages = self.get_recent_messages(email, limit)
        
        # app.py에서 기대하는 형식으로 포맷 변환
        formatted_messages = []
        for msg in messages:
            role = "assistant" if msg["role"] == "ai" else msg["role"]
            formatted_messages.append({
                "role": role,
                "content": msg["content"],
                "timestamp": msg.get("timestamp", datetime.now().isoformat())
            })
        
        logger.info(f"[대화 내역 조회 완료] 이메일: {email}, 반환된 메시지 수: {len(formatted_messages)}")
        return formatted_messages
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the chat history manager.
        
        Returns:
            Dictionary with statistics
        """
        stats = {
            "using_redis": self.use_redis,
            "max_history": self.max_history,
            "users": 0,
            "total_messages": 0,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            if self.use_redis and self.redis_client:
                # Redis stats
                keys = self.redis_client.keys("chat_history:*")
                stats["users"] = len(keys)
                
                total_msgs = 0
                for key in keys:
                    total_msgs += self.redis_client.llen(key)
                
                stats["total_messages"] = total_msgs
            else:
                # Memory stats
                stats["users"] = len(self.in_memory_storage)
                total_msgs = sum(len(msgs) for msgs in self.in_memory_storage.values())
                stats["total_messages"] = total_msgs
                
            logger.info(f"채팅 통계: {stats['users']} 사용자, {stats['total_messages']} 메시지")
            return stats
        
        except Exception as e:
            logger.error(f"통계 수집 중 오류: {str(e)}")
            stats["error"] = str(e)
            return stats
    
    async def delete_chat_history(self, email: str, user_type: str = None) -> bool:
        """
        Delete chat history for a user.
        This is an async wrapper for clear_history to support async calls.
        
        Args:
            email: User email
            user_type: Type of user ('member' or 'trainer')
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"[대화 내역 삭제 요청] 이메일: {email}, 사용자 타입: {user_type}")
        return self.clear_history(email)
    
    def add_chat_entry(self, email: str, message: str, is_user: bool = True, additional_data: Dict[str, Any] = None) -> bool:
        """
        Add a message to the chat history
        
        Args:
            email: User email
            message: Message content
            is_user: True if the message is from the user, False if from the assistant
            additional_data: Additional data to store with the message
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            role = "user" if is_user else "ai"
            self._add_message(email, role, message, additional_data)
            return True
        except Exception as e:
            logger.error(f"[채팅 기록 추가 오류] 이메일: {email}, 메시지: {message[:30]}..., 오류: {str(e)}")
            return False
            
    async def add_chat_entry_async(self, email: str, role: str, message: str, additional_data: Dict[str, Any] = None) -> bool:
        """
        비동기로 메시지를 대화 내역에 추가합니다.
        
        Args:
            email: 사용자 이메일
            role: 메시지 역할 ('user' 또는 'assistant')
            message: 메시지 내용
            additional_data: 메시지와 함께 저장할 추가 데이터
            
        Returns:
            bool: 성공 시 True, 실패 시 False
        """
        try:
            role_normalized = "user" if role == "user" else "ai"
            self._add_message(email, role_normalized, message, additional_data)
            return True
        except Exception as e:
            logger.error(f"[채팅 기록 비동기 추가 오류] 이메일: {email}, 역할: {role}, 오류: {str(e)}")
            return False
            
    async def save_chat_history(self, email: str, chat_history: List[Dict[str, Any]]) -> bool:
        """
        Save the entire chat history for a user. This overwrites the existing history.
        
        Args:
            email: User email
            chat_history: List of chat messages with role and content
            
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"[채팅 내역 저장] 이메일: {email}, 메시지 수: {len(chat_history)}")
        
        try:
            # 기존 내역 삭제
            self.clear_history(email)
            
            # 새 내역 저장
            for message in chat_history:
                role = "ai" if message.get("role") == "assistant" else message.get("role", "user")
                content = message.get("content", "")
                
                # 메시지 추가
                self._add_message(email, role, content)
                
            logger.info(f"[채팅 내역 저장 완료] 이메일: {email}")
            return True
                
        except Exception as e:
            logger.error(f"[채팅 내역 저장 오류] 이메일: {email}, 오류: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False 
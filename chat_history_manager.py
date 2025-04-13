import redis
from typing import List, Dict, Any
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
    
    async def add_chat_entry(self, email: str, role: str, message: str) -> None:
        """
        Add a message to the chat history with the specified role.
        This is an async wrapper for _add_message to support async calls.
        
        Args:
            email: User email
            role: Message role ("user" or "assistant")
            message: The message content
        """
        logger.info(f"[채팅 메시지 저장] 이메일: {email}, 역할: {role}, 길이: {len(message)}")
        
        # role 매핑 (assistant -> ai, 다른 것은 그대로)
        adjusted_role = "ai" if role == "assistant" else role
        
        # 내부 메소드 호출 (비동기 호환)
        self._add_message(email, adjusted_role, message)
        return None
    
    def _add_message(self, email: str, role: str, message: str) -> None:
        """Add a message to the user's chat history"""
        try:
            # 안전한 메시지 처리 (인코딩 문제 방지)
            safe_message = message
            if not isinstance(safe_message, str):
                try:
                    safe_message = str(safe_message)
                except Exception as e:
                    logger.error(f"[메시지 문자열 변환 오류] {str(e)}")
                    safe_message = "메시지 변환 오류"
            
            # 인코딩 문제 방지를 위한 처리
            try:
                safe_message = safe_message.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
            except Exception as e:
                logger.error(f"[메시지 인코딩 처리 오류] {str(e)}")
                # 최대한 복구 시도
                try:
                    safe_message = str(safe_message).encode('ascii', errors='replace').decode('ascii', errors='replace')
                except:
                    safe_message = "인코딩 오류 메시지"
            
            # 메시지 데이터 생성
            message_data = {
                "role": role,
                "content": safe_message,
                "timestamp": datetime.now().isoformat()
            }
            
            if self.use_redis and self.redis_client:
                # Redis 저장
                user_key = self._get_user_key(email)
                json_data = json.dumps(message_data, ensure_ascii=False)
                
                # 메시지 저장
                result = self.redis_client.lpush(user_key, json_data)
                
                # 메시지 수 제한
                self.redis_client.ltrim(user_key, 0, self.max_history - 1)
                
                # 결과 확인
                total_count = self.redis_client.llen(user_key)
                logger.info(f"[Redis 저장 완료] 이메일: {email}, 역할: {role}, 메시지 수: {total_count}")
            else:
                # 메모리 저장
                if email not in self.in_memory_storage:
                    self.in_memory_storage[email] = []
                
                # 메시지는 최신 순으로 저장 (새 메시지가 앞에)
                self.in_memory_storage[email].insert(0, message_data)
                
                # 메시지 수 제한
                if len(self.in_memory_storage[email]) > self.max_history:
                    self.in_memory_storage[email] = self.in_memory_storage[email][:self.max_history]
                
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
                
                # 가장 최근 메시지부터 조회 (가장 최근이 인덱스 0)
                raw_messages = self.redis_client.lrange(user_key, 0, limit - 1)
                
                # 메시지 파싱 및 정렬 (오래된 순)
                for msg_json in reversed(raw_messages):
                    try:
                        # 인코딩 문제 방지
                        if isinstance(msg_json, bytes):
                            msg_json = msg_json.decode('utf-8', errors='replace')
                            
                        msg_data = json.loads(msg_json)
                        
                        # 컨텐츠 인코딩 문제 추가 검사
                        if "content" in msg_data and isinstance(msg_data["content"], str):
                            try:
                                msg_data["content"] = msg_data["content"].encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                            except Exception as e:
                                logger.warning(f"메시지 내용 인코딩 처리 중 오류: {str(e)}")
                                # 손상된 내용 복구 시도
                                msg_data["content"] = str(msg_data["content"]).encode('ascii', errors='replace').decode('ascii', errors='replace')
                                
                        messages.append(msg_data)
                    except json.JSONDecodeError as e:
                        logger.error(f"[JSON 파싱 오류] 메시지: {msg_json[:100]}...")
                        logger.error(f"JSON 파싱 오류 상세: {str(e)}")
                
                logger.info(f"[Redis 조회 완료] 이메일: {email}, 조회된 메시지 수: {len(messages)}")
            else:
                # 메모리 저장소에서 조회
                if email in self.in_memory_storage:
                    # 메모리 저장소에서는 이미 최신 순으로 저장되어 있음
                    raw_messages = self.in_memory_storage[email][:limit]
                    
                    # 메시지 정렬 (오래된 순)
                    for msg_data in reversed(raw_messages):
                        # 컨텐츠 인코딩 문제 추가 검사
                        if "content" in msg_data and isinstance(msg_data["content"], str):
                            try:
                                msg_data["content"] = msg_data["content"].encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                            except Exception as e:
                                logger.warning(f"메시지 내용 인코딩 처리 중 오류: {str(e)}")
                                # 손상된 내용 복구 시도
                                msg_data["content"] = str(msg_data["content"]).encode('ascii', errors='replace').decode('ascii', errors='replace')
                        
                        messages.append(msg_data)
                    
                    logger.info(f"[메모리 조회 완료] 이메일: {email}, 조회된 메시지 수: {len(messages)}")
                else:
                    logger.info(f"[메모리 조회] 이메일: {email}에 대한 대화 내역 없음")
            
            # 최종 안전 검사 - 잘못된 형식의 메시지 필터링
            safe_messages = []
            for msg in messages:
                if not isinstance(msg, dict):
                    logger.warning(f"잘못된 메시지 형식 스킵: {type(msg)}")
                    continue
                    
                # 필수 필드 검사
                if "role" not in msg or "content" not in msg:
                    logger.warning(f"필수 필드 누락된 메시지 스킵: {msg.keys()}")
                    continue
                    
                # content 필드 안전 처리
                if not isinstance(msg["content"], str):
                    try:
                        msg["content"] = str(msg["content"])
                    except:
                        msg["content"] = "컨텐츠 변환 오류"
                        
                # role 필드 안전 처리
                if not isinstance(msg["role"], str):
                    try:
                        msg["role"] = str(msg["role"])
                    except:
                        msg["role"] = "unknown"
                
                safe_messages.append(msg)
                
            return safe_messages
            
        except Exception as e:
            logger.error(f"[대화 내역 조회 오류] 이메일: {email}, 오류: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []  # 오류 발생 시 빈 목록 반환
    
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
    
    async def get_chat_history(self, email: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get chat history for a user.
        This is an async wrapper for get_recent_messages to support async calls.
        
        Args:
            email: User email
            limit: Maximum number of messages to return
            
        Returns:
            List of chat messages in chronological order
        """
        logger.info(f"[대화 내역 조회 요청] 이메일: {email}, 최대 개수: {limit}")
        
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
    
    async def delete_chat_history(self, email: str) -> bool:
        """
        Delete chat history for a user.
        This is an async wrapper for clear_history to support async calls.
        
        Args:
            email: User email
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"[대화 내역 삭제 요청] 이메일: {email}")
        return self.clear_history(email)
    
    async def save_chat_history(self, email: str, chat_history: List[Dict[str, Any]]) -> None:
        """
        Save the entire chat history for a user. This overwrites the existing history.
        
        Args:
            email: User email
            chat_history: List of chat messages with role and content
        """
        logger.info(f"[채팅 내역 저장] 이메일: {email}, 메시지 수: {len(chat_history)}")
        
        try:
            if self.use_redis and self.redis_client:
                # Redis 저장 - 기존 데이터 삭제
                user_key = self._get_user_key(email)
                
                # 파이프라인으로 작업 일괄 처리
                pipe = self.redis_client.pipeline()
                
                # 기존 내역 삭제
                pipe.delete(user_key)
                
                # 새로운 내역 저장 (역순으로 저장해야 최신 메시지가 앞에 옴)
                for message in reversed(chat_history):
                    # role 필드 조정 (assistant -> ai)
                    adjusted_role = "ai" if message.get("role") == "assistant" else message.get("role")
                    
                    message_data = {
                        "role": adjusted_role,
                        "content": message.get("content", ""),
                        "timestamp": message.get("timestamp", datetime.now().isoformat())
                    }
                    
                    json_data = json.dumps(message_data, ensure_ascii=False)
                    pipe.lpush(user_key, json_data)
                
                # 실행
                pipe.execute()
                logger.info(f"[Redis 채팅 내역 저장 완료] 이메일: {email}")
                
            else:
                # 메모리 저장
                # 채팅 내역 변환 (assistant -> ai)
                converted_history = []
                for message in chat_history:
                    adjusted_role = "ai" if message.get("role") == "assistant" else message.get("role")
                    
                    message_data = {
                        "role": adjusted_role,
                        "content": message.get("content", ""),
                        "timestamp": message.get("timestamp", datetime.now().isoformat())
                    }
                    converted_history.append(message_data)
                
                # 최신 메시지가 앞에 오도록 저장
                self.in_memory_storage[email] = list(reversed(converted_history))
                
                # 메시지 수 제한
                if len(self.in_memory_storage[email]) > self.max_history:
                    self.in_memory_storage[email] = self.in_memory_storage[email][:self.max_history]
                
                logger.info(f"[메모리 채팅 내역 저장 완료] 이메일: {email}")
                
        except Exception as e:
            logger.error(f"[채팅 내역 저장 오류] 이메일: {email}, 오류: {str(e)}")
            # 오류를 전파하지 않고 경고만 로깅 
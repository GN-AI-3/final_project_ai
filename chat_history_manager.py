import redis
from typing import List, Dict, Any
import json
import logging
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatHistoryManager:
    """
    Manages chat history for users using Redis as a backend storage
    """
    
    def __init__(self):
        """Initialize the chat history manager with Redis connection"""
        try:
            redis_host = os.getenv("REDIS_HOST")
            redis_port = int(os.getenv("REDIS_PORT"))
            redis_password = os.getenv("REDIS_PASSWORD")
            
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                decode_responses=True
            )
            logger.info("Connected to Redis successfully")
            
            # 최대 20개의 메시지만 저장하도록 설정
            self.max_history = 20
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            # Fallback to in-memory storage if Redis connection fails
            self.redis_client = None
            self.in_memory_storage = {}
            logger.warning("Using in-memory storage as fallback")
    
    def _get_user_key(self, email: str) -> str:
        """Generate a Redis key for the user's chat history"""
        return f"chat_history:{email}"
    
    def add_user_message(self, email: str, message: str) -> None:
        """Add a user message to the chat history"""
        self._add_message(email, "user", message)
    
    def add_ai_message(self, email: str, message: str) -> None:
        """Add an AI message to the chat history"""
        self._add_message(email, "ai", message)
    
    def _add_message(self, email: str, role: str, message: str) -> None:
        """Add a message to the user's chat history"""
        try:
            message_data = {
                "role": role,
                "content": message,
                "timestamp": datetime.now().isoformat()
            }
            
            if self.redis_client:
                user_key = self._get_user_key(email)
                
                # Push to the list
                self.redis_client.lpush(user_key, json.dumps(message_data))
                
                # 메시지를 20개로 제한
                self.redis_client.ltrim(user_key, 0, self.max_history - 1)
                
                logger.debug(f"Added {role} message for {email}, keeping only {self.max_history} messages")
            else:
                # Fallback to in-memory storage
                if email not in self.in_memory_storage:
                    self.in_memory_storage[email] = []
                
                self.in_memory_storage[email].insert(0, message_data)
                
                # 메시지를 20개로 제한
                if len(self.in_memory_storage[email]) > self.max_history:
                    self.in_memory_storage[email] = self.in_memory_storage[email][:self.max_history]
                
                logger.debug(f"Added {role} message for {email} (in-memory), keeping only {self.max_history} messages")
                
        except Exception as e:
            logger.error(f"Error adding message to history: {str(e)}")
    
    def get_recent_messages(self, email: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the most recent messages for a user"""
        try:
            # 요청된 limit이 max_history를 초과하지 않도록 조정
            limit = min(limit, self.max_history)
            messages = []
            
            if self.redis_client:
                user_key = self._get_user_key(email)
                
                # Get messages (from newest to oldest)
                raw_messages = self.redis_client.lrange(user_key, 0, limit - 1)
                
                # Parse and reverse (to get chronological order)
                for msg_json in reversed(raw_messages):
                    messages.append(json.loads(msg_json))
            else:
                # Fallback to in-memory storage
                if email in self.in_memory_storage:
                    # Get messages and reverse to get chronological order
                    messages = list(reversed(self.in_memory_storage[email][:limit]))
            
            return messages
        
        except Exception as e:
            logger.error(f"Error retrieving chat history: {str(e)}")
            return []
    
    def clear_history(self, email: str) -> None:
        """Clear the chat history for a user"""
        try:
            if self.redis_client:
                user_key = self._get_user_key(email)
                self.redis_client.delete(user_key)
                logger.info(f"Cleared chat history for {email}")
            else:
                # Fallback to in-memory storage
                if email in self.in_memory_storage:
                    self.in_memory_storage[email] = []
                    logger.info(f"Cleared chat history for {email} (in-memory)")
        
        except Exception as e:
            logger.error(f"Error clearing chat history: {str(e)}")
    
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
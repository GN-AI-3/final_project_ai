"""
API 서버 - FastAPI 기반 RestAPI 엔드포인트 정의 (수정본)
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import logging
import os
import uvicorn
import traceback
import json
import time
from datetime import datetime
import uuid

# 대화 내역 관리자 임포트
from chat_history_manager import ChatHistoryManager

# 수퍼바이저 모듈 임포트
from supervisor import Supervisor
from langchain_openai import ChatOpenAI

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("api_server.log") 
    ]
)
logger = logging.getLogger(__name__)

# 다른 모듈의 로깅 레벨 설정
logging.getLogger('supervisor_modules').setLevel(logging.INFO)
logging.getLogger('supervisor').setLevel(logging.INFO)
logging.getLogger('agents').setLevel(logging.INFO)

# .env 로드 (필요 시)
from dotenv import load_dotenv
load_dotenv()

# LLM 초기화
llm = ChatOpenAI(temperature=0.7)

# 대화 내역 관리자 & 수퍼바이저 초기화
chat_history_manager = ChatHistoryManager()
supervisor = Supervisor(model=llm)

# 유틸: JSON 데이터를 보기 좋게 출력
def log_pretty_json(prefix, data):
    if not isinstance(data, dict):
        print(f"\n{prefix}: {data}\n")
        logger.info(f"{prefix}: {data}")
        return
        
    try:
        if 'response' in data and isinstance(data['response'], str) and len(data['response']) > 100:
            compact_data = data.copy()
            compact_data['response'] = data['response'][:100] + f"... (응답 길이: {len(data['response'])}자)"
            formatted_json = json.dumps(compact_data, ensure_ascii=False, indent=2)
        else:
            formatted_json = json.dumps(data, ensure_ascii=False, indent=2)
        
        print(f"\n{prefix}:\n{formatted_json}\n")
        logger.info(f"{prefix}: {json.dumps(data, ensure_ascii=False)[:200]}...")
    except Exception as e:
        logger.error(f"JSON 포맷팅 중 오류: {str(e)}")
        print(f"\n{prefix}: {data}\n")

# 모델 정의
class ChatRequest(BaseModel):
    message: str
    member_id: Optional[str] = None
    trainer_id: Optional[str] = None
    user_type: Optional[str] = None

class ChatResponse(BaseModel):
    member_id: Optional[str] = None
    trainer_id: Optional[str] = None
    user_type: str = "member"
    timestamp: str
    member_input: str
    clarified_input: Optional[str] = None
    selected_agents: List[str] = []
    final_response: str
    execution_time: Optional[float] = None
    emotion_type: Optional[str] = None

app = FastAPI(
    title="AI 피트니스 코치 API 서버",
    description="사용자의 운동, 식단, 일정 등에 관련된 질문을 처리하는 API 서버",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "AI 피트니스 코치 API 서버에 오신 것을 환영합니다"}

@app.post("/chat")
async def chat(chat_request: ChatRequest):
    request_id = str(uuid.uuid4())
    message = chat_request.message
    member_id = chat_request.member_id
    trainer_id = chat_request.trainer_id
    user_type = chat_request.user_type

    if not user_type:
        user_type = "member" if member_id else "trainer"
    
    logger.info(f"[{request_id}] 채팅 요청 - user_type: {user_type}, member_id: {member_id}, trainer_id: {trainer_id}, msg: {message[:50]}...")

    try:
        user_id = member_id if user_type == "member" else trainer_id
        chat_history: List[Dict[str, Any]] = []

        # 대화 내역 조회
        if user_id:
            try:
                chat_history = chat_history_manager.get_recent_messages(user_id, limit=6)
                logger.info(f"[{request_id}] 대화 내역 조회 - {len(chat_history)}개")
            except Exception as e:
                logger.warning(f"[{request_id}] 대화 내역 조회 실패: {str(e)}")

        start_time = time.time()
        # Supervisor 호출
        response_data = await supervisor.process(
            message=message,
            member_id=member_id,
            trainer_id=trainer_id,
            user_type=user_type,
            chat_history=chat_history
        )
        elapsed_time = time.time() - start_time
        logger.info(f"[{request_id}] Supervisor 처리 완료 (소요: {elapsed_time:.2f}s)")
        
        # 응답 로깅
        log_pretty_json(f"[{request_id}] AI 응답 데이터", response_data)

        # 대화 내역 저장 (동기 메서드 add_chat_entry 사용)
        if user_id:
            # 사용자 메시지
            user_message_saved = chat_history_manager.add_chat_entry(user_id, "user", message)
            if not user_message_saved:
                logger.warning(f"[{request_id}] 사용자 메시지 저장 실패: {user_id}")

            # 에이전트(assistant) 메시지
            assistant_message_saved = chat_history_manager.add_chat_entry(
                user_id,
                "assistant",
                response_data.get("response", "")
            )
            if not assistant_message_saved:
                logger.warning(f"[{request_id}] 어시스턴트 메시지 저장 실패: {user_id}")

        # 응답 변환
        final_resp = ChatResponse(
            member_id=member_id,
            trainer_id=trainer_id,
            user_type=user_type,
            timestamp=datetime.now().isoformat(),
            member_input=message,
            clarified_input=message,
            selected_agents=response_data.get("selected_agents", ["general"]),
            final_response=response_data.get("response", ""),
            execution_time=elapsed_time,
            emotion_type=response_data.get("emotion_type", None)
        )
        return final_resp
    
    except Exception as e:
        logger.error(f"[{request_id}] 채팅 처리 중 오류: {str(e)}")
        logger.error(traceback.format_exc())
        error_resp = ChatResponse(
            member_id=member_id,
            trainer_id=trainer_id,
            user_type=user_type,
            timestamp=datetime.now().isoformat(),
            member_input=message,
            clarified_input=None,
            selected_agents=[],
            final_response=f"처리 중 오류가 발생했습니다: {str(e)}",
            execution_time=0,
            emotion_type=None
        )
        return error_resp

if __name__ == "__main__":
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)

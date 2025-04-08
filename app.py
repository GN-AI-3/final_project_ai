from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import logging
import os
import uvicorn
import traceback
from datetime import datetime

# 에이전트 임포트
from agents import ExerciseAgent, FoodAgent, ScheduleAgent, GeneralAgent, MotivationAgent
from supervisor import Supervisor
from langchain_openai import ChatOpenAI

# Supervisor 초기화
llm = ChatOpenAI(
    temperature=0.7,
    model=os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo")
)
supervisor = Supervisor(model=llm)

# FastAPI 앱 초기화
app = FastAPI(
    title="AI 피트니스 코치 API 서버",
    description="사용자의 운동, 식단, 일정 등에 관련된 질문을 처리하고 개인화된 답변을 제공하는 API 서버",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 배포 시에는 허용할 도메인 명시
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("api_server.log")
    ]
)
logger = logging.getLogger(__name__)

# 모델 정의
class ChatRequest(BaseModel):
    message: str
    email: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    type: str
    created_at: str = None

# 백그라운드 작업: 메시지 스케줄링
def schedule_motivation_message(email: str, message: str):
    try:
        # 기본 사용자 ID 사용 (향후 사용자 이메일로 조회 가능)
        member_id = 1
        logger.info(f"사용자 {email} 메시지 스케줄링 완료")
    except Exception as e:
        logger.error(f"메시지 스케줄링 중 오류 발생: {str(e)}")

# 루트 엔드포인트
@app.get("/")
async def root():
    return {"message": "AI 피트니스 코치 API 서버에 오신 것을 환영합니다"}

# 채팅 엔드포인트
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    # 이메일 정보가 있으면 사용, 없으면 기본값 사용
    user_email = request.email or "anonymous@example.com"
    logger.info(f"채팅 요청 받음 - 사용자: {user_email}, 메시지: {request.message[:50]}...")
    
    try:
        # 기본 사용자 ID 사용 (향후 사용자 이메일로 조회 가능)
        member_id = 1
        
        # Supervisor를 통한 메시지 분석 및 처리
        response_data = await supervisor.process(request.message, member_id=member_id)
        
        # 타입과 응답 추출
        response_type = response_data.get("type", "general")
        response_message = response_data.get("response", "죄송합니다. 요청을 처리할 수 없습니다.")
        
        # 스케줄링 명령어는 background_tasks로 처리
        if "schedule" in request.message.lower() or "예약" in request.message:
            if response_type == "motivation" or response_type == "exercise":
                background_tasks.add_task(schedule_motivation_message, user_email, request.message)
                logger.info(f"스케줄링 명령어 감지 - 사용자: {user_email}")
        
        logger.info(f"{response_type.upper()} 타입 응답 생성 완료 - 사용자: {user_email}, 응답 길이: {len(response_message)}")
        
        return ChatResponse(
            response=response_message,
            type=response_type,
            created_at=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"요청 처리 중 오류 발생: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="메시지 처리 중 오류가 발생했습니다")

# 상태 확인 엔드포인트
@app.get("/status")
async def status():
    return {
        "status": "운영 중",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

if __name__ == "__main__":
    # 환경 변수에서 포트 설정 가져오기 (기본값: 8000)
    port = int(os.environ.get("PORT", 8000))
    
    # 서버 실행
    logger.info(f"서버 시작 - 포트: {port}")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True) 
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
from agents import ExerciseMotivationAgent
from agents.exercise_motivation.workflows.exercise_motivation_workflow import create_exercise_motivation_workflow

# 기본 에이전트 인스턴스 생성
motivation_agent = ExerciseMotivationAgent()
motivation_workflow = create_exercise_motivation_workflow()

# FastAPI 앱 초기화
app = FastAPI(
    title="Exercise Motivation AI Server",
    description="사용자의 운동 패턴을 분석하고 개인화된 동기부여 메시지를 생성하는 API 서버",
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
    member_id: str
    message: str

class ChatResponse(BaseModel):
    response: str
    type: str = "motivation"
    created_at: str = None

# 백그라운드 작업: 메시지 스케줄링
def schedule_motivation_message(member_id: int, message: str):
    try:
        motivation_agent.schedule_motivation_message(member_id)
        logger.info(f"사용자 {member_id} 메시지 스케줄링 완료")
    except Exception as e:
        logger.error(f"메시지 스케줄링 중 오류 발생: {str(e)}")

# 루트 엔드포인트
@app.get("/")
async def root():
    return {"message": "Exercise Motivation AI API Server"}

# 채팅 엔드포인트
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    logger.info(f"채팅 요청 받음 - 회원 ID: {request.member_id}, 메시지: {request.message[:50]}...")
    
    try:
        # 사용자 ID를 정수로 변환
        try:
            member_id = int(request.member_id)
        except ValueError:
            logger.warning(f"유효하지 않은 회원 ID 형식: {request.member_id}")
            raise HTTPException(status_code=400, detail="유효하지 않은 회원 ID 형식입니다")
        
        # 스케줄링 명령어 감지
        if "스케줄" in request.message or "예약" in request.message or "schedule" in request.message.lower():
            logger.info(f"스케줄링 명령어 감지 - 회원 ID: {member_id}")
            background_tasks.add_task(schedule_motivation_message, member_id, request.message)
            return ChatResponse(
                response="동기부여 메시지가 성공적으로 예약되었습니다. 지정된 시간에 메시지를 받게 됩니다.",
                type="motivation_schedule",
                created_at=datetime.now().isoformat()
            )
        
        # 일반 동기부여 메시지 생성
        response = motivation_agent.generate_motivation_message(member_id, request.message)
        logger.info(f"동기부여 메시지 생성 완료 - 회원 ID: {member_id}, 응답 길이: {len(response)}")
        
        return ChatResponse(
            response=response,
            type="motivation",
            created_at=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"요청 처리 중 오류 발생: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="메시지 처리 중 오류가 발생했습니다")

# 워크플로우 기반 동기부여 메시지 생성 엔드포인트
@app.post("/motivation", response_model=ChatResponse)
async def generate_motivation(request: ChatRequest, background_tasks: BackgroundTasks):
    logger.info(f"동기부여 메시지 생성 요청 - 회원 ID: {request.member_id}")
    
    try:
        # 사용자 ID를 정수로 변환
        try:
            member_id = int(request.member_id)
        except ValueError:
            logger.warning(f"유효하지 않은 회원 ID 형식: {request.member_id}")
            raise HTTPException(status_code=400, detail="유효하지 않은 회원 ID 형식입니다")
        
        # 워크플로우 기반 동기부여 메시지 생성
        response = motivation_workflow(member_id)
        logger.info(f"워크플로우 기반 동기부여 메시지 생성 완료 - 회원 ID: {member_id}, 응답 길이: {len(response)}")
        
        return ChatResponse(
            response=response,
            type="workflow_motivation",
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
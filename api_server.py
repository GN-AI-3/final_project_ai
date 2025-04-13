"""
API 서버 - FastAPI 기반 RestAPI 엔드포인트 정의
"""
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
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
from fastapi.responses import JSONResponse
import uuid

# 대화 내역 관리자 임포트
from chat_history_manager import ChatHistoryManager

# 루트 폴더의 Supervisor 임포트
from supervisor import Supervisor
from langchain_openai import ChatOpenAI

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 콘솔 출력
        logging.FileHandler("api_server.log")  # 파일 로깅
    ]
)
logger = logging.getLogger(__name__)

# 환경변수 확인
from dotenv import load_dotenv
load_dotenv()

# LLM 초기화
llm = ChatOpenAI(temperature=0.7)

# 대화 내역 관리자 초기화
chat_history_manager = ChatHistoryManager()

# 루트 폴더의 Supervisor 인스턴스 생성
supervisor = Supervisor(model=llm)

# 에이전트 임포트
from agents import ExerciseAgent, FoodAgent, ScheduleAgent, MotivationAgent, GeneralAgent

# 유틸리티 함수: JSON 데이터를 보기 좋게 출력
def log_pretty_json(prefix, data):
    """JSON 데이터를 보기 좋게 포맷팅하여 콘솔에 출력"""
    if not isinstance(data, dict):
        print(f"\n{prefix}: {data}\n")
        logger.info(f"{prefix}: {data}")
        return
        
    try:
        # 응답이 너무 길면 잘라서 표시
        if 'response' in data and isinstance(data['response'], str) and len(data['response']) > 100:
            compact_data = data.copy()
            compact_data['response'] = data['response'][:100] + f"... (응답 길이: {len(data['response'])}자)"
            formatted_json = json.dumps(compact_data, ensure_ascii=False, indent=2)
        else:
            formatted_json = json.dumps(data, ensure_ascii=False, indent=2)
        
        # 콘솔에 출력
        print(f"\n{prefix}:\n{formatted_json}\n")
        # 로그에도 기록 (너무 긴 경우 앞부분만)
        logger.info(f"{prefix}: {json.dumps(data, ensure_ascii=False)[:200]}...")
    except Exception as e:
        logger.error(f"JSON 포맷팅 중 오류: {str(e)}")
        print(f"\n{prefix}: {data}\n")

# 에이전트 내용 추출 유틸리티 함수
def _extract_agent_content(output: Any) -> str:
    """
    다양한 형태의 에이전트 출력에서 내용을 추출합니다.
    """
    if output is None:
        return "응답이 없습니다."
    
    if isinstance(output, str):
        return output
    
    if isinstance(output, dict):
        # 가능한 키 목록 순서대로 시도
        for key in ["content", "response", "answer", "output", "text", "message"]:
            if key in output and output[key] is not None:
                if isinstance(output[key], str):
                    return output[key]
                else:
                    return str(output[key])
        
        # 알려진 키가 없는 경우 전체 딕셔너리 반환
        return str(output)
    
    # 기타 타입
    return str(output)

# 모델 정의
class ChatRequest(BaseModel):
    message: str
    email: Optional[str] = None

class AgentOutput(BaseModel):
    content: str
    type: str
    
class InjectedContext(BaseModel):
    inbody: Optional[str] = None
    routine: Optional[str] = None
    diet: Optional[str] = None
    emotion_type: Optional[str] = None
    emotion_score: Optional[float] = None
    
class ChatResponse(BaseModel):
    member_id: str
    timestamp: str
    member_input: str
    clarified_input: Optional[str] = None
    selected_agents: List[str] = []
    injected_context: Optional[InjectedContext] = None
    agent_outputs: Dict[str, str] = {}
    final_response: str
    execution_time: Optional[float] = None
    emotion_detected: Optional[bool] = None
    emotion_type: Optional[str] = None
    emotion_score: Optional[float] = None

# 백그라운드 작업: 메시지 스케줄링
def schedule_motivation_message(email: str, message: str):
    """모티베이션 메시지 스케줄링"""
    try:
        # 단순히 이메일 정보만 로깅
        logger.info(f"사용자 {email}의 메시지 스케줄링 완료")
    except Exception as e:
        logger.error(f"메시지 스케줄링 중 오류 발생: {str(e)}")

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

# 루트 엔드포인트
@app.get("/")
async def root():
    return {"message": "AI 피트니스 코치 API 서버에 오신 것을 환영합니다"}

# 채팅 엔드포인트
@app.post("/chat")
async def chat(chat_request: ChatRequest):
    request_id = str(uuid.uuid4())
    message = chat_request.message
    email = chat_request.email
    
    logger.info(f"[{request_id}] 채팅 요청 받음 - 사용자: {email}, 메시지: {message[:50]}...")
    
    # 기존 대화 내역 불러오기
    if email:
        chat_history = chat_history_manager.get_formatted_history(email)
        logger.info(f"[{request_id}] 대화 내역 불러오기 완료 - 항목 수: {len(chat_history)}")
    else:
        chat_history = []
    
    try:
        # Supervisor 처리 파이프라인 시작
        logger.info(f"[{request_id}] Supervisor 파이프라인 처리 시작")
        start_time = time.time()
        
        # 루트 폴더의 Supervisor 호출
        response_data = await supervisor.process(
            message=message, 
            email=email
        )
        
        # 처리 완료 로깅
        elapsed_time = time.time() - start_time
        logger.info(f"[{request_id}] Supervisor 파이프라인 처리 완료 (소요시간: {elapsed_time:.2f}초)")
        
        # 응답 정보 로깅
        logger.info(f"[{request_id}] AI 응답 데이터: {json.dumps(response_data, ensure_ascii=False)[:200]}...")
        
        # 응답 형식을 ChatResponse 모델에 맞게 변환
        formatted_response = ChatResponse(
            member_id=email or "anonymous",
            timestamp=datetime.now().isoformat(),
            member_input=message,
            clarified_input=message,  # 현재는 명확화 과정이 없으므로 원본 메시지 사용
            selected_agents=[response_data.get("type", "general")],
            injected_context=InjectedContext(),  # 현재는 빈 컨텍스트
            agent_outputs={response_data.get("type", "general"): response_data.get("response", "")},
            final_response=response_data.get("response", ""),
            execution_time=elapsed_time,
            emotion_detected=False,  # 현재는 감정 분석 결과 없음
            emotion_type=None,
            emotion_score=None
        )
        
        # 응답 반환
        return formatted_response
        
    except Exception as e:
        # 오류 로깅
        logger.error(f"[{request_id}] 채팅 처리 중 오류 발생: {str(e)}")
        logger.error(traceback.format_exc())
        
        # 오류 응답 반환 (ChatResponse 형식)
        error_response = ChatResponse(
            member_id=email or "anonymous",
            timestamp=datetime.now().isoformat(),
            member_input=message,
            clarified_input=None,
            selected_agents=[],
            agent_outputs={},
            final_response=f"처리 중 오류가 발생했습니다: {str(e)}",
            execution_time=0,
            emotion_detected=False,
            emotion_type=None,
            emotion_score=None
        )
        return error_response

# 대화 내역 조회 엔드포인트
@app.get("/chat/history")
async def get_chat_history(email: str = None, limit: int = 20):
    if not email:
        raise HTTPException(status_code=400, detail="이메일 파라미터가 필요합니다")
        
    try:
        # 대화 내역 조회
        chat_history = await chat_history_manager.get_chat_history(email, limit=limit)
        
        # 응답 포맷팅
        return {
            "email": email,
            "messages": chat_history or [],
            "count": len(chat_history) if chat_history else 0
        }
    except Exception as e:
        logger.error(f"대화 내역 조회 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"대화 내역 조회 중 오류 발생: {str(e)}")

# 대화 내역 삭제 엔드포인트
@app.delete("/chat/history")
async def clear_chat_history(email: str = None):
    if not email:
        raise HTTPException(status_code=400, detail="이메일 파라미터가 필요합니다")
        
    try:
        # 대화 내역 삭제
        success = await chat_history_manager.delete_chat_history(email)
        
        if success:
            return {"status": "success", "message": f"사용자 {email}의 대화 내역이 삭제되었습니다"}
        else:
            return {"status": "warning", "message": f"사용자 {email}의 대화 내역이 없거나 이미 삭제되었습니다"}
    except Exception as e:
        logger.error(f"대화 내역 삭제 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"대화 내역 삭제 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True) 
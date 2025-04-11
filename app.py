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
import importlib.util

# 에이전트 임포트
from agents import ExerciseAgent, FoodAgent, ScheduleAgent, GeneralAgent, MotivationAgent

import sys
sys.path.append(".")  # 현재 디렉토리를 경로에 추가

# Supervisor 직접 임포트 (파일 경로로부터)
spec = importlib.util.spec_from_file_location("supervisor_module", "supervisor.py")
supervisor_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supervisor_module)
Supervisor = supervisor_module.Supervisor

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from chat_history_manager import ChatHistoryManager

# Redis 대화 내역 관리자 초기화
chat_history_manager = ChatHistoryManager()

# LLM 초기화
llm = ChatOpenAI(
    temperature=0.7,
    model=os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo")
)

# LangGraph 파이프라인 초기화
from supervisor.langgraph_pipeline import LangGraphPipeline
langgraph_pipeline = LangGraphPipeline(llm=llm)
langgraph_pipeline.register_agent("exercise", ExerciseAgent(llm))
langgraph_pipeline.register_agent("food", FoodAgent(llm))
langgraph_pipeline.register_agent("diet", FoodAgent(llm))
langgraph_pipeline.register_agent("schedule", ScheduleAgent(llm))
langgraph_pipeline.register_agent("motivation", MotivationAgent(llm))
langgraph_pipeline.register_agent("general", GeneralAgent(llm))

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
        logging.StreamHandler(),  # 콘솔 출력
        logging.FileHandler("api_server.log")  # 파일 로깅 유지
    ]
)
logger = logging.getLogger(__name__)

# 콘솔에 JSON 데이터를 보기 좋게 출력하는 함수
def log_pretty_json(prefix, data):
    """JSON 데이터를 보기 좋게 포맷팅하여 콘솔에 출력"""
    if isinstance(data, dict):
        try:
            # 중요 정보만 추출하여 로깅
            if 'response' in data and isinstance(data['response'], str) and len(data['response']) > 100:
                # 응답이 너무 길면 잘라서 표시
                compact_data = data.copy()
                compact_data['response'] = data['response'][:100] + "... (응답 길이: " + str(len(data['response'])) + "자)"
                formatted_json = json.dumps(compact_data, ensure_ascii=False, indent=2)
            else:
                formatted_json = json.dumps(data, ensure_ascii=False, indent=2)
            
            # 콘솔에 출력
            print(f"\n{prefix}:\n{formatted_json}\n")
            # 로그에도 기록
            logger.info(f"{prefix}: {json.dumps(data)[:200]}...")
        except Exception as e:
            logger.error(f"JSON 포맷팅 중 오류: {str(e)}")
            print(f"\n{prefix}: {data}\n")
    else:
        print(f"\n{prefix}: {data}\n")
        logger.info(f"{prefix}: {data}")

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

# 백그라운드 작업: 메시지 스케줄링
def schedule_motivation_message(email: str, message: str):
    try:
        # 단순히 이메일 정보만 로깅
        logger.info(f"사용자 {email}의 메시지 스케줄링 완료")
    except Exception as e:
        logger.error(f"메시지 스케줄링 중 오류 발생: {str(e)}")

# 루트 엔드포인트
@app.get("/")
async def root():
    return {"message": "AI 피트니스 코치 API 서버에 오신 것을 환영합니다"}

# 채팅 엔드포인트
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    # 이메일 정보가 요청에서 제공되면 사용, 없으면 기본값 사용
    user_email = request.email or "anonymous@example.com"
    print(f"\n===== 채팅 요청 시작: {user_email} =====")
    print(f"메시지: {request.message[:100]}...")
    logger.info(f"채팅 요청 받음 - 사용자: {user_email}, 메시지: {request.message[:50]}...")
    
    try:
        # 1. 먼저 사용자 메시지를 Redis에 저장
        await chat_history_manager.add_chat_entry(user_email, "user", request.message)
        logger.info(f"사용자 메시지 Redis에 저장 완료 - 이메일: {user_email}")
        
        # 2. 대화 내역 불러오기
        chat_history = await chat_history_manager.get_chat_history(user_email)
        logger.info(f"대화 내역 불러오기 완료 - 이메일: {user_email}, 항목 수: {len(chat_history)}")
        
        # 3. LangGraph 파이프라인을 통한 메시지 처리
        start_time = time.time()
        print(f"\n[처리 중] LangGraph 파이프라인에 요청 전달 중...")
        response_data = await langgraph_pipeline.process(request.message, email=user_email, chat_history=chat_history)
        execution_time = time.time() - start_time
        print(f"[처리 완료] 실행 시간: {execution_time:.2f}초\n")
        
        # 응답 데이터 로깅 (콘솔에 보기 좋게 출력)
        log_pretty_json("AI 응답 데이터", response_data)
        
        # 응답 추출
        response_type = response_data.get("type", "general")
        response_message = response_data.get("response", "죄송합니다. 요청을 처리할 수 없습니다.")
        response_created_at = datetime.now().isoformat()
        
        # 다중 에이전트 응답에서 카테고리 정보 확인
        response_categories = response_data.get("metrics", {}).get("response_categories", [])
        if not response_categories and "categories" in response_data:
            response_categories = response_data.get("categories", [])
        
        print(f"[응답 정보] 타입: {response_type}, 카테고리: {response_categories if response_categories else '없음'}")
        logger.info(f"응답 타입: {response_type}, 카테고리: {response_categories if response_categories else '없음'}")
        
        # 4. AI 응답을 Redis에 저장
        await chat_history_manager.add_chat_entry(user_email, "assistant", response_message)
        logger.info(f"AI 응답 Redis에 저장 완료 - 이메일: {user_email}, 타입: {response_type}")
        
        # 5. 스케줄링 명령어는 background_tasks로 처리
        if "schedule" in request.message.lower() or "예약" in request.message:
            if response_type == "motivation" or response_type == "exercise" or "schedule" in response_categories:
                background_tasks.add_task(schedule_motivation_message, user_email, request.message)
                logger.info(f"스케줄링 명령어 감지 - 사용자: {user_email}")
        
        # 총 실행 시간 
        logger.info(f"처리 완료 - 실행 시간: {execution_time:.2f}초")
        logger.info(f"{response_type.upper()} 타입 응답 생성 완료 - 사용자: {user_email}, 응답 길이: {len(response_message)}")
        
        # 6. 에이전트 출력 파싱 (다중 에이전트 응답의 경우)
        agent_outputs = {}
        clarified_input = request.message
        selected_agents = []
        
        # 【AGENT 응답】 형식 파싱
        if "【" in response_message and "】" in response_message:
            # 모든 에이전트 응답 섹션 파싱
            agent_sections = []
            i = 0
            while i < len(response_message):
                start_marker = response_message.find("【", i)
                if start_marker == -1:
                    break
                
                end_marker = response_message.find("】", start_marker)
                if end_marker == -1:
                    break
                
                agent_type = response_message[start_marker+1:end_marker].strip().lower()
                if " " in agent_type:
                    agent_type = agent_type.split(" ")[0].lower()  # "EXERCISE 응답" -> "exercise"
                
                next_start = response_message.find("【", end_marker)
                if next_start == -1:
                    content = response_message[end_marker+1:]
                else:
                    content = response_message[end_marker+1:next_start]
                
                selected_agents.append(agent_type)
                agent_outputs[agent_type] = content.strip()
                i = end_marker + 1
        else:
            # 단일 에이전트 응답인 경우
            selected_agents = [response_type]
            agent_outputs[response_type] = response_message
        
        # 7. 응답 포맷팅 및 반환
        response = ChatResponse(
            member_id=user_email,
            timestamp=response_created_at,
            member_input=request.message,
            clarified_input=clarified_input,
            selected_agents=selected_agents,
            agent_outputs=agent_outputs,
            final_response=response_message,
            execution_time=execution_time
        )
        
        return response
        
    except Exception as e:
        error_message = f"요청 처리 중 오류 발생: {str(e)}"
        logger.error(error_message)
        logger.error(traceback.format_exc())
        
        # 에러 응답 생성
        error_response = ChatResponse(
            member_id=user_email,
            timestamp=datetime.now().isoformat(),
            member_input=request.message,
            final_response=f"죄송합니다. 요청을 처리하는 중에 오류가 발생했습니다: {str(e)}",
            execution_time=0
        )
        
        return JSONResponse(
            status_code=500,
            content=error_response.dict()
        )

# 메트릭 엔드포인트
@app.get("/metrics")
async def get_metrics():
    try:
        # LangGraph 파이프라인 메트릭 사용
        metrics = langgraph_pipeline.get_metrics()
        
        # 기본 메트릭이 없는 경우 기본값 제공
        if not metrics:
            metrics = {
                "requests_processed": 0,
                "successful_responses": 0,
                "failed_responses": 0,
                "avg_processing_time": 0
            }
        
        # Redis 통계 추가
        try:
            redis_stats = await chat_history_manager.get_stats()
            metrics["redis"] = redis_stats
        except Exception as e:
            logger.error(f"Redis 통계 조회 중 오류: {str(e)}")
            metrics["redis"] = {"error": str(e)}
        
        return metrics
    except Exception as e:
        logger.error(f"메트릭 조회 중 오류: {str(e)}")
        return {"error": str(e)}

# 상태 확인 엔드포인트 
@app.get("/status")
async def status():
    return {
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "llm_model": os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo"),
        "using_langgraph": True,
        "num_agents": len(langgraph_pipeline.agents)
    }

# 대화 내역 조회 엔드포인트
@app.get("/chat/history")
async def get_chat_history(email: str = None, limit: int = 20):
    if not email:
        raise HTTPException(status_code=400, detail="이메일 파라미터가 필요합니다")
        
    try:
        # 대화 내역 조회
        chat_history = await chat_history_manager.get_chat_history(email, limit=limit)
        
        # 대화 내역이 없는 경우
        if not chat_history:
            return {"email": email, "messages": [], "count": 0}
            
        # 응답 포맷팅
        return {
            "email": email,
            "messages": chat_history,
            "count": len(chat_history)
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
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True) 
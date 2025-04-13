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

# LangGraph 기반 Supervisor 임포트
from langgraph_supervisor.supervisor import Supervisor

# 에이전트 임포트
from agents import ExerciseAgent, FoodAgent, ScheduleAgent, MotivationAgent, GeneralAgent
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

# LangGraph Supervisor 인스턴스 생성
supervisor = Supervisor()

# 에이전트 등록
logger.info("에이전트 등록 시작")

# 개별 에이전트 등록을 시도 (오류가 있어도 계속 진행)
def register_agent_safely(name, agent_class):
    try:
        agent = agent_class(llm=llm)
        supervisor.register_agent(name, agent)
        logger.info(f"'{name}' 에이전트 등록 성공")
        return True
    except Exception as e:
        logger.error(f"'{name}' 에이전트 등록 실패: {str(e)}")
        logger.debug(traceback.format_exc())
        return False

# 각 에이전트 등록 시도
success_count = 0
success_count += register_agent_safely("exercise", ExerciseAgent)
success_count += register_agent_safely("food", FoodAgent)
success_count += register_agent_safely("schedule", ScheduleAgent)
success_count += register_agent_safely("motivation", MotivationAgent)
success_count += register_agent_safely("general", GeneralAgent)

# 결과 로깅
logger.info(f"{success_count}개 에이전트가 성공적으로 등록되었습니다.")
if success_count < 5:
    logger.warning("일부 에이전트 등록에 실패했습니다. 일부 기능만 사용 가능합니다.")

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
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    # 이메일 정보가 요청에서 제공되면 사용, 없으면 기본값 사용
    user_email = request.email or "anonymous@example.com"
    request_id = str(uuid.uuid4())  # 고유 요청 ID 생성
    logger.info(f"[{request_id}] 채팅 요청 받음 - 사용자: {user_email}, 메시지: {request.message[:50]}...")
    
    # 기본 응답 구조 설정
    response_created_at = datetime.now().isoformat()
    default_response = ChatResponse(
        member_id=user_email,
        timestamp=response_created_at,
        member_input=request.message,
        final_response="",
        execution_time=0
    )
    
    try:
        # 1. 사용자 메시지를 Redis에 저장
        await chat_history_manager.add_chat_entry(user_email, "user", request.message)
        
        # 2. 대화 내역 불러오기
        chat_history = await chat_history_manager.get_chat_history(user_email)
        logger.info(f"[{request_id}] 대화 내역 불러오기 완료 - 항목 수: {len(chat_history)}")
        
        # 3. Supervisor 처리 시작
        start_time = time.time()
        logger.info(f"[{request_id}] Supervisor 파이프라인 처리 시작")
        
        # LangGraph Supervisor 실행
        # user_id 매개변수를 email로 전달
        response_data = await supervisor.process_message(
            message=request.message, 
            user_id=user_email, 
            chat_history=chat_history,
            request_id=request_id
        )
        
        # 처리 시간 계산
        execution_time = time.time() - start_time
        logger.info(f"[{request_id}] Supervisor 파이프라인 처리 완료 (소요시간: {execution_time:.2f}초)")
        
        # 응답 데이터 로깅
        log_pretty_json(f"[{request_id}] AI 응답 데이터", response_data)
        
        # 4. 응답 정보 추출
        actual_request_id = response_data.get("request_id", request_id)
        
        # 선택된 에이전트 정보 추출 - 여러 필드 이름 시도 (호환성)
        selected_agents = response_data.get("selected_agents", [])
        
        # selected_agents가 비어있으면 categories로부터 가져오기 
        if not selected_agents:
            selected_agents = response_data.get("categories", [])
            
        # 여전히 비어있으면 기본값 설정
        if not selected_agents:
            selected_agents = ["general"]
            
        response_type = selected_agents[0] if selected_agents else "general"
        
        # Extract response string from possible dictionary response
        response_raw = response_data.get("response", "죄송합니다. 요청을 처리할 수 없습니다.")
        if isinstance(response_raw, dict):
            if "response" in response_raw:
                response_message = response_raw["response"]
            elif "content" in response_raw:
                response_message = response_raw["content"]
            else:
                response_message = str(response_raw)
        else:
            response_message = response_raw
            
        error = response_data.get("error")
        
        # 오류 발생시 로깅
        if error:
            logger.warning(f"[{actual_request_id}] 처리 중 오류 발생: {error}")
        
        # 5. AI 응답을 Redis에 저장 (오류가 아닌 경우에만)
        if not error:
            await chat_history_manager.add_chat_entry(user_email, "assistant", response_message)
        
        # 6. 스케줄링 명령어 처리
        if "schedule" in request.message.lower() or "예약" in request.message:
            if response_type == "schedule" or "schedule" in selected_agents:
                background_tasks.add_task(schedule_motivation_message, user_email, request.message)
                logger.info(f"[{actual_request_id}] 스케줄링 명령어 감지 - 사용자: {user_email}")
        
        # 7. 에이전트 출력 파싱
        agent_outputs = {}
        clarified_input = request.message
        final_selected_agents = []
        
        # agent_results가 있으면 사용
        if "agent_results" in response_data and response_data["agent_results"]:
            for result in response_data["agent_results"]:
                if result.get("success", False):
                    agent_name = result.get("agent", "unknown")
                    agent_result = result.get("result", "")
                    agent_outputs[agent_name] = _extract_agent_content(agent_result)
                    final_selected_agents.append(agent_name)
                    
        # agent_outputs에서 사용하는 경우
        elif "agent_outputs" in response_data and response_data["agent_outputs"]:
            for agent_name, agent_output in response_data["agent_outputs"].items():
                agent_outputs[agent_name] = _extract_agent_content(agent_output)
                final_selected_agents.append(agent_name)
        else:
            # 단일 에이전트 응답인 경우
            final_selected_agents = [response_type]
            agent_outputs[response_type] = _extract_agent_content(response_message)
        
        # 8. 응답 포맷팅 및 반환
        # 감정 분석 결과 추출
        emotion_type = response_data.get("emotion_type", "중립")
        emotion_score = response_data.get("emotion_score", 0.0)
        emotion_detected = emotion_score != 0.0
        
        # 컨텍스트 정보 생성 (확장 가능)
        injected_context = InjectedContext(
            emotion_type=emotion_type,
            emotion_score=emotion_score
        )
        
        response = ChatResponse(
            member_id=user_email,
            timestamp=response_created_at,
            member_input=request.message,
            clarified_input=clarified_input,
            selected_agents=final_selected_agents,
            injected_context=injected_context,
            agent_outputs=agent_outputs,
            final_response=response_message,
            execution_time=execution_time,
            emotion_detected=emotion_detected,
            emotion_type=emotion_type,
            emotion_score=emotion_score
        )
        
        logger.info(f"[{actual_request_id}] 응답 생성 완료 - 에이전트: {final_selected_agents}")
        return response
        
    except Exception as e:
        # 자세한 오류 정보 로깅
        error_message = f"요청 처리 중 오류 발생: {str(e)}"
        logger.error(f"[{request_id}] {error_message}")
        logger.error(traceback.format_exc())
        
        # 오류 응답 생성
        default_response.final_response = f"죄송합니다. 요청을 처리하는 중에 오류가 발생했습니다: {str(e)}"
        
        return JSONResponse(
            status_code=500,
            content=default_response.dict()
        )

# 메트릭 엔드포인트
@app.get("/metrics")
async def get_metrics():
    try:
        # Supervisor 메트릭 사용
        metrics = supervisor.get_metrics()
        
        # Redis 통계 추가
        try:
            redis_stats = await chat_history_manager.get_stats()
            metrics["redis"] = redis_stats
        except Exception as e:
            logger.error(f"Redis 통계 조회 중 오류: {str(e)}")
            metrics["redis"] = {"error": str(e)}
        
        # 시스템 정보 추가
        metrics["version"] = "1.0.0"
        metrics["timestamp"] = datetime.now().isoformat()
        
        return metrics
    except Exception as e:
        logger.error(f"메트릭 조회 중 오류: {str(e)}")
        return {"error": str(e), "timestamp": datetime.now().isoformat()}

# 메트릭 리셋 엔드포인트
@app.post("/metrics/reset")
async def reset_metrics():
    try:
        # LangGraph Supervisor는 메트릭 초기화 메서드가 없으므로 직접 초기화
        supervisor.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_execution_time": 0,
            "node_usage": {}
        }
        return {
            "status": "success", 
            "message": "메트릭이 초기화되었습니다.", 
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"메트릭 초기화 중 오류 발생: {str(e)}")
        return {
            "status": "error", 
            "message": f"메트릭 초기화 중 오류 발생: {str(e)}", 
            "timestamp": datetime.now().isoformat()
        }

# 상태 확인 엔드포인트 
@app.get("/status")
async def status():
    status_info = {
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "llm_model": os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo"),
        "using_langgraph": True,
        "supervisor_type": "LangGraph Supervisor"
    }
    
    # 메트릭 요약 추가
    try:
        metrics = supervisor.get_metrics()
        status_info["metrics_summary"] = {
            "requests_processed": metrics.get("total_requests", 0),
            "successful_responses": metrics.get("successful_requests", 0),
            "failed_responses": metrics.get("failed_requests", 0),
            "avg_execution_time": metrics.get("avg_execution_time", 0)
        }
    except Exception as e:
        logger.error(f"메트릭 요약 조회 중 오류: {str(e)}")
        status_info["metrics_summary"] = {"error": str(e)}
    
    return status_info

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

# 에이전트 목록 조회 엔드포인트
@app.get("/agents")
async def list_agents():
    try:
        # 사용 가능한 에이전트 목록 - 빈 목록 대신 노드 사용량에서 얻기
        metrics = supervisor.get_metrics()
        registered_agents = list(metrics.get("node_usage", {}).keys())
        
        # 에이전트별 메트릭 추가
        agent_metrics = metrics.get("node_usage", {})
        
        # 에이전트 정보 구성
        agents_info = {}
        for agent_id in registered_agents:
            agents_info[agent_id] = {
                "status": "active",
                "metrics": {"usage_count": agent_metrics.get(agent_id, 0)}
            }
        
        return {
            "agents": agents_info,
            "count": len(registered_agents),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"에이전트 목록 조회 중 오류: {str(e)}")
        return {"error": str(e), "timestamp": datetime.now().isoformat()}

# 에이전트 정보 조회 엔드포인트
@app.get("/agents/{agent_id}")
async def get_agent_info(agent_id: str):
    try:
        # 노드 사용량에서 에이전트 정보 추출
        metrics = supervisor.get_metrics()
        node_usage = metrics.get("node_usage", {})
        
        if agent_id not in node_usage:
            return JSONResponse(
                status_code=404,
                content={"error": f"에이전트 '{agent_id}'를 찾을 수 없습니다.", "timestamp": datetime.now().isoformat()}
            )
        
        # 에이전트 메트릭 추가
        agent_metrics = {"usage_count": node_usage.get(agent_id, 0)}
        
        return {
            "agent_id": agent_id,
            "status": "active",
            "metrics": agent_metrics,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"에이전트 정보 조회 중 오류: {str(e)}")
        return {"error": str(e), "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True) 
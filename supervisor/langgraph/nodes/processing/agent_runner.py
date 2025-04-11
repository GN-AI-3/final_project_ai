"""
에이전트 실행 노드
선택된 에이전트들을 실행하고 결과를 수집하는 노드 함수
"""

import logging
import traceback
import time
from typing import Dict, Any
import asyncio
from supervisor.langgraph.state import GymGGunState

# 로깅 설정
logger = logging.getLogger('supervisor.langgraph.nodes.processing.agent_runner')

def agent_runner(state: GymGGunState, agents: Dict = None) -> GymGGunState:
    """선택된 에이전트들을 실행하고 결과를 수집하는 노드"""
    try:
        start_time = time.time()
        message = state.message
        email = state.email
        agent_type = state.classified_type
        
        logger.debug(f"[AGENT_RUNNER] 입력 상태: email={email}, agent_type={agent_type}, message={message[:30]}...")
        logger.info(f"에이전트 실행 시작 - 에이전트 타입: {agent_type}")
        
        # 메트릭에 시작 시간 기록
        state.metrics["agent_runner_start_time"] = start_time
        
        # 에이전트가 없거나 선택된 타입의 에이전트가 없으면 오류 처리
        if not agents or agent_type not in agents:
            error_msg = f"에이전트를 찾을 수 없음: {agent_type}"
            logger.error(error_msg)
            logger.debug(f"[AGENT_RUNNER] 에이전트 목록: {', '.join(agents.keys() if agents else [])}")
            state.error = error_msg
            state.response = "죄송합니다. 요청을 처리할 수 있는 에이전트를 찾을 수 없습니다."
            state.end_time = time.time()
            return state
        
        # 선택된 에이전트 가져오기
        agent = agents[agent_type]
        logger.info(f"에이전트 {agent_type} 실행 중")
        logger.debug(f"[AGENT_RUNNER] 에이전트 클래스: {agent.__class__.__name__}")
        
        try:
            # 에이전트 실행 - email 매개변수 전달
            logger.debug(f"[AGENT_RUNNER] 에이전트 process 메서드 호출: message={message[:30]}..., email={email}")
            result = agent.process(message, email=email)
            
            # 비동기 함수인 경우 처리
            if hasattr(result, "__await__"):
                logger.debug(f"[AGENT_RUNNER] 비동기 결과 감지됨, 처리 중...")
                try:
                    # 현재 콘텍스트가 이미 asyncio 이벤트 루프 내부인지 확인
                    try:
                        asyncio.get_running_loop()
                        logger.info("이벤트 루프가 이미 실행 중입니다. 동기적으로 처리합니다.")
                        response = f"비동기 에이전트 응답: {agent_type} 에이전트가 처리 중입니다."
                    except RuntimeError:
                        # 이벤트 루프가 없으면 새로 만들어서 실행
                        logger.info("새 이벤트 루프를 생성합니다.")
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        result = loop.run_until_complete(result)
                        response = result.get("response", str(result))
                        logger.debug(f"[AGENT_RUNNER] 비동기 결과 처리 완료: {response[:50]}...")
                except Exception as e:
                    logger.error(f"비동기 함수 처리 중 오류: {str(e)}")
                    logger.exception(traceback.format_exc())
                    response = f"비동기 처리 오류: {str(e)}"
            else:
                # 응답 추출
                logger.debug(f"[AGENT_RUNNER] 동기 결과 처리 중: {str(result)[:100]}...")
                if isinstance(result, dict) and "response" in result:
                    response = result["response"]
                else:
                    response = str(result)
            
            # 상태 업데이트
            state.response = response
            state.response_type = agent_type
            logger.debug(f"[AGENT_RUNNER] 응답 설정 완료: type={agent_type}, response={response[:50]}...")
            logger.info(f"에이전트 {agent_type} 실행 완료")
            
        except Exception as e:
            error_msg = f"에이전트 {agent_type} 실행 오류: {str(e)}"
            logger.error(error_msg)
            logger.exception(traceback.format_exc())
            
            # 오류 상태 설정
            state.error = error_msg
            state.response = f"죄송합니다. {agent_type} 관련 요청을 처리하는 중에 문제가 발생했습니다."
        
        # 실행 시간 기록
        execution_time = time.time() - start_time
        state.metrics["agent_runner_time"] = execution_time
        state.end_time = time.time()
        logger.debug(f"[AGENT_RUNNER] 실행 완료: 소요 시간={execution_time:.2f}초, response={state.response[:50]}...")
        
        return state
        
    except Exception as e:
        error_msg = f"에이전트 실행 중 오류: {str(e)}"
        logger.error(error_msg)
        logger.exception(traceback.format_exc())
        
        # 오류 상태 설정
        state.error = error_msg
        state.response = "죄송합니다. 요청을 처리하는 중에 문제가 발생했습니다."
        state.end_time = time.time()
        
        return state 
"""
에이전트 실행 노드
선택된 에이전트들을 실행하고 결과를 수집하는 노드 함수
"""

import logging
import traceback
import time
from typing import Dict, Any, List
import asyncio
import concurrent.futures
from supervisor.langgraph.state import GymGGunState

# 로깅 설정
logger = logging.getLogger('supervisor.langgraph.nodes.processing.agent_runner')

# 에이전트 컨텍스트 프롬프트 템플릿
AGENT_CONTEXT_PROMPT = """당신은 전문 AI 피트니스 코치입니다. 이전 대화 내용을 고려하여 사용자의 질문에 답변해 주세요.

이전 대화 내역:
{chat_history}

사용자의 새 질문: {message}

답변 시 이전 대화의 맥락을 고려하여 일관되고 개인화된 답변을 제공하세요."""

def format_chat_history(chat_history: List[Dict[str, Any]]) -> str:
    """대화 내역을 문자열로 포맷팅"""
    if not chat_history:
        return ""
        
    formatted_history = ""
    for msg in chat_history:
        try:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            
            # content가 None이거나 비어있는 경우 스킵
            if not content:
                continue
                
            # 문자열이 아닌 경우 문자열로 변환 시도
            if not isinstance(content, str):
                content = str(content)
            
            # 인코딩 문제 방지를 위한 처리
            content = content.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
            
            if role == "user":
                formatted_history += f"사용자: {content}\n"
            elif role == "ai" or role == "assistant":
                formatted_history += f"AI: {content}\n"
        except Exception as e:
            logger.warning(f"대화 내역 포맷팅 중 오류 발생: {str(e)}")
            continue  # 오류 발생 시 해당 메시지 스킵
            
    return formatted_history

async def run_agent_async(agent, message, agent_type, email=None, chat_history=None):
    """에이전트를 비동기적으로 실행"""
    logger.info(f"에이전트 {agent_type} 비동기 실행 시작")
    
    try:
        # 에이전트가 chat_history와 email 파라미터를 지원하는지 확인
        supports_email = hasattr(agent, 'process') and 'email' in agent.process.__annotations__
        supports_chat_history = hasattr(agent, 'supports_chat_history') and agent.supports_chat_history
        
        # 대화 내역 처리
        contextualized_message = message
        if chat_history and len(chat_history) > 0 and not supports_chat_history:
            try:
                formatted_chat_history = format_chat_history(chat_history)
                if formatted_chat_history:
                    contextualized_message = AGENT_CONTEXT_PROMPT.replace("{chat_history}", formatted_chat_history).replace("{message}", message)
            except Exception as e:
                logger.error(f"대화 맥락 처리 중 오류: {str(e)}")
        
        # 에이전트 실행 - 지원하는 파라미터에 따라 호출
        if supports_email and supports_chat_history and chat_history:
            # 이메일과 대화 내역 모두 지원
            result = await agent.process(message, email=email, chat_history=chat_history)
        elif supports_email:
            # 이메일만 지원
            result = await agent.process(contextualized_message, email=email)
        else:
            # 기본 호출
            result = await agent.process(contextualized_message)
        
        # 결과 처리
        if isinstance(result, dict):
            if "response" not in result:
                result["response"] = str(result)
            if "type" not in result:
                result["type"] = agent_type
        else:
            result = {
                "response": str(result),
                "type": agent_type
            }
        
        logger.info(f"에이전트 {agent_type} 비동기 실행 완료")
        return result
    
    except Exception as e:
        logger.error(f"에이전트 {agent_type} 비동기 실행 중 오류: {str(e)}")
        # 오류 발생 시에도 결과 반환
        return {
            "response": f"{agent_type} 에이전트 처리 중 오류 발생: {str(e)}",
            "type": agent_type,
            "error": str(e)
        }

def run_agent_sync(agent, message, agent_type, email=None, chat_history=None):
    """에이전트를 동기적으로 실행"""
    logger.info(f"에이전트 {agent_type} 동기 실행 시작")
    
    try:
        # 에이전트가 chat_history와 email 파라미터를 지원하는지 확인
        supports_email = hasattr(agent, 'process') and 'email' in agent.process.__annotations__
        supports_chat_history = hasattr(agent, 'supports_chat_history') and agent.supports_chat_history
        
        # 대화 내역 처리
        contextualized_message = message
        if chat_history and len(chat_history) > 0 and not supports_chat_history:
            try:
                formatted_chat_history = format_chat_history(chat_history)
                if formatted_chat_history:
                    contextualized_message = AGENT_CONTEXT_PROMPT.replace("{chat_history}", formatted_chat_history).replace("{message}", message)
            except Exception as e:
                logger.error(f"대화 맥락 처리 중 오류: {str(e)}")
        
        # 에이전트 실행 - 지원하는 파라미터에 따라 호출
        if supports_email:
            # 이메일 지원
            result = agent.process(contextualized_message, email=email)
        else:
            # 기본 호출
            result = agent.process(contextualized_message)
        
        # 결과 처리
        if isinstance(result, dict):
            if "response" not in result:
                result["response"] = str(result)
            if "type" not in result:
                result["type"] = agent_type
        else:
            result = {
                "response": str(result),
                "type": agent_type
            }
        
        logger.info(f"에이전트 {agent_type} 동기 실행 완료")
        return result
    
    except Exception as e:
        logger.error(f"에이전트 {agent_type} 동기 실행 중 오류: {str(e)}")
        # 오류 발생 시에도 결과 반환
        return {
            "response": f"{agent_type} 에이전트 처리 중 오류 발생: {str(e)}",
            "type": agent_type,
            "error": str(e)
        }

def agent_runner(state: GymGGunState, agents: Dict = None) -> GymGGunState:
    """여러 에이전트를 병렬로 실행하고 결과를 수집하는 노드"""
    try:
        start_time = time.time()
        message = state.message
        email = state.email
        agent_messages = state.agent_messages
        chat_history = state.get("chat_history")
        
        # 모든 카테고리 가져오기 (병렬 처리를 위해)
        all_categories = state.get("all_categories", [])
        if not all_categories:
            all_categories = [state.classified_type]
        
        logger.info(f"에이전트 실행 시작 - 처리할 카테고리: {all_categories}")
        
        # 메트릭에 시작 시간 기록
        state.metrics["agent_runner_start_time"] = start_time
        
        # 에이전트가 없는 경우 오류 처리
        if not agents:
            error_msg = "등록된 에이전트가 없습니다."
            logger.error(error_msg)
            state.error = error_msg
            state.response = "죄송합니다. 요청을 처리할 수 있는 에이전트가 없습니다."
            state.end_time = time.time()
            return state
        
        # 결과를 저장할 리스트
        agent_results = []
        
        # 병렬 처리 준비
        tasks = []
        has_async_agents = False
        
        # 각 카테고리별 에이전트 및 메시지 준비
        for category in all_categories:
            if category in agents:
                agent = agents[category]
                # 에이전트별 메시지 사용 (없으면 원본 메시지)
                agent_message = agent_messages.get(category, message) if agent_messages else message
                
                # 에이전트가 비동기인지 확인
                is_async = hasattr(agent.process, "__await__") or hasattr(agent.process, "__aenter__")
                
                if is_async:
                    has_async_agents = True
                    # 비동기 태스크 추가
                    tasks.append((agent, agent_message, category, is_async))
                else:
                    # 동기 태스크 추가
                    tasks.append((agent, agent_message, category, is_async))
                    
                logger.info(f"에이전트 {category} 추가됨 (비동기: {is_async})")
            else:
                logger.warning(f"카테고리 '{category}'에 해당하는 에이전트를 찾을 수 없습니다.")
        
        # 태스크가 없는 경우 오류 처리
        if not tasks:
            error_msg = "처리할 수 있는 에이전트가 없습니다."
            logger.error(error_msg)
            state.error = error_msg
            state.response = "죄송합니다. 요청을 처리할 수 있는 에이전트가 없습니다."
            state.end_time = time.time()
            return state
        
        # 하나의 에이전트만 있는 경우 간단히 처리
        if len(tasks) == 1:
            agent, agent_message, category, is_async = tasks[0]
            
            try:
                if is_async:
                    # 비동기 함수를 이벤트 루프에서 실행
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    result = loop.run_until_complete(
                        run_agent_async(agent, agent_message, category, email, chat_history)
                    )
                else:
                    # 동기 함수 직접 실행
                    result = run_agent_sync(agent, agent_message, category, email, chat_history)
                
                agent_results.append(result)
                
            except Exception as e:
                logger.error(f"에이전트 {category} 실행 중 오류: {str(e)}")
                # 오류 발생 시에도 결과 추가
                agent_results.append({
                    "response": f"{category} 에이전트 처리 중 오류 발생: {str(e)}",
                    "type": category,
                    "error": str(e)
                })
        else:
            # 여러 에이전트가 있는 경우 병렬 처리
            if has_async_agents:
                # 비동기 에이전트가 있는 경우 asyncio 사용
                try:
                    # 현재 이벤트 루프를 가져오거나 새로 생성
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    # 비동기 태스크 준비
                    async_tasks = []
                    for agent, agent_message, category, is_async in tasks:
                        if is_async:
                            # 비동기 태스크
                            async_tasks.append(
                                run_agent_async(agent, agent_message, category, email, chat_history)
                            )
                        else:
                            # 동기 태스크를 executor에서 실행하도록 래핑
                            async_tasks.append(
                                loop.run_in_executor(
                                    None, 
                                    run_agent_sync, 
                                    agent, agent_message, category, email, chat_history
                                )
                            )
                    
                    # 모든 태스크 병렬 실행
                    results = loop.run_until_complete(asyncio.gather(*async_tasks, return_exceptions=True))
                    
                    # 결과 처리
                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                            # 예외가 발생한 경우
                            category = tasks[i][2]
                            logger.error(f"에이전트 {category} 병렬 실행 중 예외 발생: {str(result)}")
                            agent_results.append({
                                "response": f"{category} 에이전트 처리 중 오류 발생: {str(result)}",
                                "type": category,
                                "error": str(result)
                            })
                        else:
                            # 정상 결과
                            agent_results.append(result)
                    
                except Exception as e:
                    logger.error(f"비동기 병렬 처리 중 일반 오류: {str(e)}")
                    # 모든 에이전트에 대해 오류 결과 추가
                    for _, _, category, _ in tasks:
                        agent_results.append({
                            "response": f"{category} 에이전트 병렬 처리 중 오류 발생: {str(e)}",
                            "type": category,
                            "error": str(e)
                        })
            else:
                # 모두 동기 에이전트인 경우 ThreadPoolExecutor 사용
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    # 동기 태스크 준비
                    future_to_category = {
                        executor.submit(
                            run_agent_sync, 
                            agent, agent_message, category, email, chat_history
                        ): category
                        for agent, agent_message, category, _ in tasks
                    }
                    
                    # 결과 수집
                    for future in concurrent.futures.as_completed(future_to_category):
                        category = future_to_category[future]
                        try:
                            result = future.result()
                            agent_results.append(result)
                        except Exception as e:
                            logger.error(f"에이전트 {category} 병렬 실행 중 오류: {str(e)}")
                            agent_results.append({
                                "response": f"{category} 에이전트 처리 중 오류 발생: {str(e)}",
                                "type": category,
                                "error": str(e)
                            })
        
        logger.info(f"모든 에이전트 실행 완료 - 결과 개수: {len(agent_results)}")
        
        # 결과를 state에 저장 (result_combiner에서 처리하기 위해)
        state.agent_results = agent_results
        
        # 하나의 결과만 있는 경우 바로 응답으로 설정
        if len(agent_results) == 1:
            result = agent_results[0]
            state.response = result.get("response", "응답을 생성하지 못했습니다.")
            state.response_type = result.get("type", "general")
            if "error" in result:
                state.error = result["error"]
        
        # 실행 시간 기록
        execution_time = time.time() - start_time
        state.metrics["agent_runner_time"] = execution_time
        logger.info(f"에이전트 실행 노드 완료 - 실행 시간: {execution_time:.2f}초")
        
        return state
        
    except Exception as e:
        error_msg = f"에이전트 실행 중 일반 오류: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        # 오류 상태 설정
        state.error = error_msg
        state.response = "죄송합니다. 요청을 처리하는 중에 문제가 발생했습니다."
        state.end_time = time.time()
        
        return state 
"""
context_builder.py
- 사용자 대화/성향/메시지를 토대로 문맥 요약 정보를 생성하는 모듈
"""

import json
import time
import traceback
import logging
from typing import Dict, Any, List, Optional

from langchain_openai import ChatOpenAI
from langchain.schema.messages import SystemMessage, HumanMessage
from langsmith.run_helpers import traceable

from common_prompts.prompts import AGENT_CONTEXT_BUILDING_PROMPT

logger = logging.getLogger(__name__)

__all__ = ['build_agent_context', 'format_context_for_agent']

@traceable(run_type="chain", name="에이전트 문맥 정보 빌더")
async def build_agent_context(
    message: str,
    chat_history: List[Dict[str, Any]],
    request_id: str = None,
) -> str:
    """
    Builds context summary information based on user message and chat history.
    
    Args:
        message: The user's message.
        chat_history: The chat history in the format [{role: "user", content: "..."}, {role: "assistant", content: "..."}].
        request_id: The unique identifier for the current request.
        
    Returns:
        A JSON string containing context information.
    """
    start_time = time.time()
    if not request_id:
        request_id = str(time.time())
    
    logger.info(f"[{request_id}] [build_agent_context] 문맥 정보 생성 시작")

    # 최근 대화 6개만 사용
    formatted_history = "\n".join(
        f"{'사용자' if m.get('role') == 'user' else 'AI'}: {m.get('content', '')}"
        for m in chat_history[-6:]
    )

    # 프롬프트 조합
    prompt_text = AGENT_CONTEXT_BUILDING_PROMPT.format(
        chat_history=formatted_history,
        message=message
    )

    # 프롬프트 로깅 (debug 레벨로만 기록)
    logger.debug(f"[{request_id}] [build_agent_context] 전체 프롬프트: {prompt_text}")

    try:
        chat_model = ChatOpenAI(model="gpt-4o", temperature=0.2)
        response = chat_model.invoke([
            SystemMessage(content="당신은 문맥 요약 전문가입니다."),
            HumanMessage(content=prompt_text)
        ])

        raw = response.content.strip()
        
        # 원본 응답 로깅 (debug 레벨로만 기록)
        logger.debug(f"[{request_id}] [build_agent_context] 전체 응답: {raw}")

        # ```json 코드블록 제거
        json_text = raw
        if "```json" in raw:
            json_text = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            json_text = raw.split("```")[1].split("```")[0].strip()

        # JSON 파싱 테스트
        try:
            context_data = json.loads(json_text)
            logger.info(f"[{request_id}] [build_agent_context] 문맥 정보 생성 완료")
            
            # 최종 파싱된 데이터 로깅 (debug 레벨로만 기록)
            logger.debug(f"[{request_id}] [build_agent_context] 생성된 문맥: {context_data}")

            # context_summary 출력
            if "context_summary" in context_data:
                print(f"\n📝 문맥 요약: {context_data['context_summary'][:200]}...\n")

            # 최종 JSON 문자열로 반환
            return json.dumps(context_data, ensure_ascii=False)
        except json.JSONDecodeError:
            # JSON 파싱 실패 시, 기본 형식으로 래핑
            logger.warning(f"[{request_id}] [build_agent_context] JSON 파싱 실패, 기본 형식으로 변환")
            sanitized_text = raw.replace('"', '\'')  # 따옴표 충돌 방지
            context_data = {"context_summary": sanitized_text}
            return json.dumps(context_data, ensure_ascii=False)

    except Exception as e:
        logger.error(f"[{request_id}] [build_agent_context] 오류 발생: {str(e)}")
        logger.error(traceback.format_exc())
        
        # 실패 시 기본 구조 반환
        return json.dumps({"context_summary": "문맥 요약 실패"}, ensure_ascii=False)
    finally:
        duration = time.time() - start_time
        logger.info(f"[{request_id}] [build_agent_context] 소요시간: {duration:.2f}s")


def format_context_for_agent(context_info: Dict[str, Any], agent_type: str = None) -> str:
    """
    Format context information for a specific agent type.
    
    Args:
        context_info: A dictionary containing context information.
        agent_type: The type of agent to format the context for.
        
    Returns:
        A string containing the formatted context.
    """
    if not context_info or not isinstance(context_info, dict):
        return ""
        
    # 기본 context_summary 추출
    summary = context_info.get("context_summary", "")
    
    # 필요시 agent_type에 따른 커스텀 로직 추가
    return summary
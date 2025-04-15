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

@traceable(run_type="chain", name="에이전트 문맥 정보 빌더")
async def build_agent_context(
    message: str,
    chat_history: List[Dict[str, Any]]
) -> str:
    """
    (1) 대화 내역, 성향, 현재 메시지 기반으로 문맥 요약(context_info)을 생성한다.
    (2) JSON 형태의 문자열을 반환 (예: '{"context_summary": "..."}')
    """
    start_time = time.time()
    logger.info("[build_agent_context] 문맥 정보 생성 시작")

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

    # 프롬프트 로깅 (200자만 출력)
    print(f"\n[CONTEXT_BUILDER] 프롬프트 (일부): {prompt_text[:200]}...")
    logger.debug(f"[build_agent_context] 전체 프롬프트: {prompt_text}")

    try:
        chat_model = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.2)
        response = chat_model.invoke([
            SystemMessage(content="당신은 문맥 요약 전문가입니다."),
            HumanMessage(content=prompt_text)
        ])

        raw = response.content.strip()
        
        # 원본 응답 로깅
        print(f"[CONTEXT_BUILDER] 원본 응답: {raw[:300]}...")
        logger.debug(f"[build_agent_context] 전체 응답: {raw}")

        # ```json 코드블록 제거
        json_text = raw
        if "```json" in raw:
            json_text = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            json_text = raw.split("```")[1].split("```")[0].strip()

        # JSON 파싱 테스트
        context_data = json.loads(json_text)
        logger.info("[build_agent_context] 문맥 정보 생성 완료")
        
        # 최종 파싱된 데이터 출력
        print(f"[CONTEXT_BUILDER] 파싱된 문맥 데이터: {json.dumps(context_data, ensure_ascii=False)}")
        logger.debug(f"[build_agent_context] 생성된 문맥: {context_data}")

        # 최종 JSON 문자열로 반환
        return json.dumps(context_data, ensure_ascii=False)

    except Exception as e:
        logger.error("[build_agent_context] 오류 발생: %s", str(e))
        logger.error(traceback.format_exc())
        print(f"[CONTEXT_BUILDER] 오류 발생: {str(e)}")

        # 실패 시 기본 구조 반환
        return json.dumps({"context_summary": "문맥 요약 실패"}, ensure_ascii=False)
    finally:
        duration = time.time() - start_time
        logger.info(f"[build_agent_context] 소요시간: {duration:.2f}s")


def format_context_for_agent(context_info: Dict[str, Any], agent_type: str) -> str:
    """
    예: context_info가 {"context_summary": "..."} 구조라면,
    필요시 agent_type에 따라 커스텀 로직을 넣을 수도 있음.
    """
    
    return context_info.get("context_summary", "")
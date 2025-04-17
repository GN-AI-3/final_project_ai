"""
classifier.py
- 라우팅(분류) 모듈
- context_info(JSON 문자열) + 사용자 메시지 -> 1~2개 카테고리 선택
"""

import json
import time
import traceback
import logging
from typing import Dict, Any, List, Tuple

from langchain_openai import ChatOpenAI
from langchain.schema.messages import SystemMessage
from langsmith.run_helpers import traceable

from common_prompts.prompts import CATEGORY_ROUTING_PROMPT

logger = logging.getLogger(__name__)

@traceable(run_type="chain", name="메시지 분류")
async def classify_message(
    message: str,
    context_info: str = ""
) -> Tuple[List[str], Dict[str, Any]]:
    """
    (1) context_info(JSON 문자열), message 활용
    (2) CATEGORY_ROUTING_PROMPT에 넣어 LLM 호출
    (3) ["exercise", "food", ...] 형태의 리스트 반환
    """
    start_time = time.time()
    metadata: Dict[str, Any] = {
        "classification_time": 0,
        "model": "gpt-3.5-turbo",
    }

    try:
        # context_info 전처리 (문자열 아니면 변환)
        if not isinstance(context_info, str):
            context_info = str(context_info)

        chat_model = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.0)

        # 라우팅 프롬프트 생성
        prompt_text = CATEGORY_ROUTING_PROMPT.format(
            context_info=context_info,
            message=message
        )

        response = chat_model.invoke([
            SystemMessage(content=prompt_text)
        ])
        raw = response.content.strip()

        logger.info(f"LLM 라우팅 응답: {raw}")
        metadata["classification_time"] = time.time() - start_time

        # JSON 배열 파싱
        cat_list = []
        try:
            # ```json 제거
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            parsed = json.loads(raw)
            if isinstance(parsed, list):
                cat_list = parsed
            else:
                # 혹시 문자열이면 리스트화
                cat_list = [parsed]

        except Exception as e:
            logger.warning(f"JSON 파싱 실패: {str(e)}")
            cat_list = ["general"]

        # 유효 카테고리만
        valid_set = {"exercise", "food", "schedule", "motivation", "general"}
        filtered = [c for c in cat_list if c in valid_set]

        # 최대 2개
        if not filtered:
            filtered = ["general"]
        elif len(filtered) > 2:
            filtered = filtered[:2]

        logger.info(f"분류 결과: {filtered}")
        return filtered, metadata

    except Exception as e:
        logger.error(f"메시지 분류 오류: {str(e)}")
        logger.error(traceback.format_exc())
        return ["general"], {
            **metadata,
            "error": str(e),
            "backup_method": "exception",
            "classification_time": time.time() - start_time
        }

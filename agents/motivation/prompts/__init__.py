"""
Prompts package for motivation agent
동기부여 에이전트를 위한 프롬프트 템플릿 모음
"""

# motivation/prompts 패키지
from .prompt_templates import (
    UNIFIED_PROMPT,
    get_unified_prompt_with_goals,
    get_cheer_prompt,
    get_system_query_response,
    CHEER_PROMPT,
    SYSTEM_QUERY_RESPONSE
)

__all__ = [
    'get_unified_prompt_with_goals',
    'UNIFIED_PROMPT',
    'get_cheer_prompt',
    'get_system_query_response',
    'CHEER_PROMPT',
    'SYSTEM_QUERY_RESPONSE'
]
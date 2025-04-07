"""
Prompts package for motivation agent
"""

# motivation/prompts package
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
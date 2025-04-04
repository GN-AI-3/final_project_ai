"""
운동 동기부여 메시지 생성을 위한 프롬프트 템플릿
"""
import json
from langchain_core.prompts import ChatPromptTemplate

# 시스템 메시지: 에이전트 기본 역할 정의
SYSTEM_MESSAGE = """당신은 사용자의 운동을 독려하고 동기를 부여하는 개인 트레이너 AI입니다.
사용자가 운동을 꾸준히 하도록 친절하고 긍정적인 메시지를 제공하세요.
운동의 중요성과 건강한 습관의 가치를 알려주고, 사용자가 운동 습관을 형성할 수 있도록 도와주세요.

다음 설정을 반드시 따라주세요:
{
  "role": "fitness trainer",
  "language": "Korean",
  "format": "markdown",
  "response_length": "balanced",
  "tone": "encouraging",
  "emoji_usage": "moderate"
}

다음 규칙을 준수하세요:
1. 항상 긍정적이고 격려하는 톤을 유지하세요.
2. 과학적으로 검증된 정보만 제공하세요.
3. 사용자의 운동 패턴과 기록을 기반으로 답변하세요.
4. 100~150자 내외의 간결한 메시지를 작성하세요.
5. 필요할 때 적절한 이모지를 사용하여 친근감을 줄 수 있습니다.
"""

# 초기 단계 (1~4주차) 프롬프트 템플릿
EARLY_MOTIVATION_TEMPLATE = """사용자는 운동을 시작한지 {weeks}주차로, 아직 운동 습관을 형성하는 단계입니다.

{
  "user_stage": "beginner",
  "focus_areas": ["initial_encouragement", "small_achievements", "habit_formation"],
  "difficulty_acknowledgement": true,
  "long_term_benefits": true
}

현재 사용자의 운동 패턴은 {pattern}입니다.
{pattern_details}

이러한 정보를 바탕으로 사용자에게 맞춤형 동기부여 메시지를 제공하세요.
"""

# 개인화 단계 (5주차 이상) 프롬프트 템플릿
PERSONALIZED_MOTIVATION_TEMPLATE = """사용자는 운동을 시작한지 {weeks}주차로, 이제 개인화된 운동 패턴이 어느 정도 형성되었습니다.

{
  "user_stage": "intermediate",
  "focus_areas": ["pattern_based_feedback", "specific_achievements", "next_steps", "challenges_solutions"],
  "data_points": {
    "pattern": "{pattern}",
    "memo_rate": {memo_rate:.1%}
  }
}

사용자의 운동 패턴은 {pattern}입니다.
{pattern_details}

메모 기록률은 {memo_rate:.1%}입니다.

사용자의 운동 기록 메모 작성을 장려하는 내용도 포함해 주세요.
"""

# 사용자 메시지 템플릿
USER_MESSAGE = "안녕하세요, 오늘의 운동 동기부여 메시지를 보내주세요."

# 운동 패턴별 설명 템플릿
PATTERN_DESCRIPTIONS = {
    "active": """
{
  "pattern_type": "active",
  "stats": {
    "total_records": {total_records}
  },
  "strategy": "maintenance_encouragement"
}

사용자는 매우 열심히 운동하고 있습니다. 총 {total_records}회의 운동 기록이 있습니다.
이는 매우 좋은 수준으로, 이 페이스를 유지하도록 격려해 주세요.
""",
    "irregular": """
{
  "pattern_type": "irregular",
  "stats": {
    "total_records": {total_records}
  },
  "strategy": "regularity_improvement"
}

사용자는 간헐적으로 운동하고 있습니다. 총 {total_records}회의 운동 기록이 있습니다.
더 규칙적인 운동 습관을 형성할 수 있도록 도와주세요.
""",
    "inactive": """
{
  "pattern_type": "inactive",
  "stats": {
    "total_records": {total_records}
  },
  "strategy": "gentle_restart"
}

사용자는 운동을 거의 하지 않고 있습니다. 총 {total_records}회의 운동 기록밖에 없습니다.
운동을 시작하거나 재개하도록 부드럽게 격려해 주세요.
"""
}

def get_pattern_details(pattern: str, attendance_rate: float, total_records: int) -> str:
    """
    운동 패턴에 따른 세부 설명을 생성합니다.
    
    Args:
        pattern: 운동 패턴 ('active', 'irregular', 'inactive')
        attendance_rate: 출석률 (0.0~1.0)
        total_records: 총 운동 기록 수
        
    Returns:
        str: 운동 패턴 세부 설명
    """
    if pattern not in PATTERN_DESCRIPTIONS:
        return "사용자의 운동 패턴을 파악할 수 없습니다."
        
    return PATTERN_DESCRIPTIONS[pattern].format(
        total_records=total_records
    )

def get_motivation_prompt_template(weeks: int) -> ChatPromptTemplate:
    """
    주차에 따른 프롬프트 템플릿을 생성합니다.
    
    Args:
        weeks: 운동 시작 후 주차
        
    Returns:
        ChatPromptTemplate: 해당 주차에 적합한 프롬프트 템플릿
    """
    # 4주 이하는 초기 단계 템플릿 사용
    if weeks <= 4:
        template = EARLY_MOTIVATION_TEMPLATE
    # 5주 이상은 개인화 템플릿 사용
    else:
        template = PERSONALIZED_MOTIVATION_TEMPLATE
        
    # 프롬프트 템플릿 생성
    return ChatPromptTemplate.from_messages([
        ("system", SYSTEM_MESSAGE),
        ("human", template),
        ("human", USER_MESSAGE)
    ]) 
# make/make2/util/table_schema.py
table_schema = {
  "member": {
    "description": "사용자 정보 테이블",
    "columns": {
      "id": "사용자 고유 ID (PK)",
      "name": "사용자 이름",
      "goal": "건강/식단 목표",
      "phone": "연락처",
      "fcm_token": "푸시 토큰",
      "gender": "성별"
    }
  },
  "inbody": {
    "description": "사용자 인바디 측정 기록",
    "columns": {
      "inbody_id": "인바디 기록 ID (PK)",
      "member_id": "사용자 ID (FK)",
      "height": "키 (cm)",
      "weight": "체중 (kg)",
      "bmi": "체질량지수",
      "body_mass_index": "체질량 지수 (중복 가능성 있음)",
      "body_weight": "체중 (중복 가능성 있음)",
      "tall": "키 (중복 가능성 있음)",
      "date": "측정일",
      "measurement_date": "측정일자 (중복 가능성 있음)"
    }
  },
 
  "meal_records": {
    "description": "사용자의 실제 식사 기록",
    "columns": {
      "meal_records_id": "식사 기록 ID (PK)",
      "member_id": "사용자 ID (FK)",
      "created_at": "생성일시",
      "modified_at": "수정일시",
      "food_name": "섭취 음식명",
      "portion": "섭취량",
      "unit": "단위 (g, ml 등)",
      "meal_date": "식사 날짜",
      "meal_time": "식사 시간",
      "meal_type": "아침/점심/저녁",
      "calories": "열량 (kcal)",
      "protein": "단백질 (g)",
      "carbs": "탄수화물 (g)",
      "fat": "지방 (g)",
      "estimated_grams": "추정량 (g)"
    }
  },
  "recommended_diet_plans": {
    "description": "추천된 식단 구성 결과",
    "columns": {
      "recommended_diet_plan_id": "추천 식단 ID (PK)",
      "member_id": "사용자 ID (FK)",
      "created_datetime": "생성일시",
      "plan_day": "요일 (예: monday)",
      "breakfast_plan": "아침 식단",
      "lunch_plan": "점심 식단",
      "dinner_plan": "저녁 식단",
      "plan_summary": "요약 설명",
      "plan_scope": "단일/주간 여부 (예: single/daily/weekly)"
    }
  },
  "diet_plans": {
    "description": "시스템 제공 식단 구성 템플릿",
    "columns": {
      "id": "식단 ID (PK)",
      "created_at": "생성일시",
      "modified_at": "수정일시",
      "breakfast_suggestion": "아침 제안",
      "lunch_suggestion": "점심 제안",
      "dinner_suggestion": "저녁 제안",
      "breakfast": "아침 식단",
      "lunch": "점심 식단",
      "dinner": "저녁 식단",
      "diet_type": "식단 유형 예(다이어트 식단 벌크업 식단 체력 증진 식단 유지/균형 식단 고단백/저탄수화물 식단 고탄수/고단백 식단 )",
      "user_gender": "사용자 성별"
    }
  },
  "food_nutrition": {
    "description": "식품 데이터베이스",
    "columns": {
      "id": "식품 ID (PK)",
      "name": "식품 이름",
      "calories": "열량",
      "protein": "단백질",
      "carbs": "탄수화물",
      "fat": "지방",
      "created_at": "생성일시",
      "modified_at": "수정일시"
    }
  },
  "member_diet_info": {
    "description": "사용자 식단 정보 요약",
    "columns": {
      "id": "식단 정보 ID (PK)",
      "member_id": "사용자 ID (FK)",
      "created_at": "생성일시",
      "modified_at": "수정일시",
      "activity_level": "활동량",
      "allergies": "알레르기 정보",
      "food_preferences": "선호 음식",
      "meal_pattern": "식사 패턴",
      "special_requirements": "특별 요구 사항",
      "food_avoidance": "거부 음식"
    }
  }
}
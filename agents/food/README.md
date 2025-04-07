# Food Agent

식사 추천 및 영양 관리 에이전트

## 기능

- 사용자 맞춤형 식단 추천
- 영양소 분석 및 관리
- 식사 기록 관리
- 알레르기 및 선호도 기반 필터링

## 주요 컴포넌트

### 1. BalancedMealAgent

균형 잡힌 식단을 추천하는 에이전트

#### 주요 기능:
- 사용자 목표에 따른 식단 유형 결정
- 사용자 정보 및 선호도 기반 맞춤형 식단 추천
- 영양소 균형 분석
- 식사 시간대별 추천

#### 사용 방법:
```python
from agents.food.subagents.balanced_meal_agent.nodes import BalancedMealAgent

# 에이전트 초기화
agent = BalancedMealAgent()

# 식단 추천 요청
result = await agent.process("식단 추천", user_id="1")
```

#### 응답 형식:
```json
{
    "type": "food",
    "response": "📌 **추천 식단:**\n\n🍳 **아침 식사:**\n...",
    "data": {
        "breakfast": {
            "meal": "오트밀과 과일",
            "comment": "아침에 필요한 에너지와 영양소를 제공하는 건강한 아침 식사입니다.",
            "nutrition": {
                "calories": 350,
                "protein": 12,
                "carbs": 45,
                "fat": 8
            }
        },
        "lunch": {...},
        "dinner": {...},
        "total_nutrition": {
            "calories": 1300,
            "protein": 67,
            "carbs": 145,
            "fat": 35
        }
    }
}
```

### 2. NutritionAgent

영양소 분석 및 관리를 담당하는 에이전트

#### 주요 기능:
- 영양소 섭취량 분석
- 영양소 균형 평가
- 영양소 결핍 진단
- 영양소 보충 제안

### 3. MealHistoryAgent

식사 기록 관리를 담당하는 에이전트

#### 주요 기능:
- 식사 기록 저장
- 식사 패턴 분석
- 식사 시간 관리
- 식사 통계 제공

## 데이터베이스 스키마

### users 테이블
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    gender TEXT NOT NULL,
    age INTEGER NOT NULL,
    height REAL NOT NULL,
    weight REAL NOT NULL,
    goal TEXT NOT NULL,
    activity_level TEXT NOT NULL
);
```

### user_preferences 테이블
```sql
CREATE TABLE user_preferences (
    user_id INTEGER PRIMARY KEY,
    allergies TEXT,
    dietary_preference TEXT,
    meal_pattern TEXT,
    meal_times TEXT,
    food_preferences TEXT,
    special_requirements TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### meal_history 테이블
```sql
CREATE TABLE meal_history (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    meal_type TEXT NOT NULL,
    meal_time TIMESTAMP NOT NULL,
    foods TEXT NOT NULL,
    calories INTEGER,
    protein REAL,
    carbs REAL,
    fat REAL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

## 설치 및 설정

1. 필요한 패키지 설치:
```bash
pip install -r requirements.txt
```

2. 데이터베이스 초기화:
```bash
python init_db.py
```

3. 환경 변수 설정:
```bash
export OPENAI_API_KEY=your_api_key
```

## 사용 예시

```python
from agents.food.agent_main import FoodAgent

# 에이전트 초기화
agent = FoodAgent()

# 식단 추천 요청
result = await agent.process("식단 추천", user_id="1")
print(result["response"])
```

## 오류 처리

- 사용자 정보 누락: 기본 추천 제공
- 영양소 정보 누락: 기본 영양소 목표 사용
- 식단 계획 누락: 기본 식단 계획 사용
- JSON 파싱 오류: 기본 추천 제공

## 기여 방법

1. 이슈 생성
2. 브랜치 생성
3. 코드 작성
4. 테스트 실행
5. PR 생성

## 라이선스

MIT License
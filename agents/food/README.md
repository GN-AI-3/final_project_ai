# Food Agent

식사 추천 및 영양 관리 에이전트

## 개요

이 프로젝트는 사용자 맞춤형 식단 추천, 영양소 분석, 식사 기록 관리를 위한 AI 에이전트 시스템입니다. LangChain과 OpenAI GPT 모델을 활용하여 지능적인 식사 관리 서비스를 제공합니다.

## 시스템 구조

### 1. 디렉토리 구조

```
food/
├── common/                  # 공통 모듈
│   ├── api_client.py       # 백엔드 API 클라이언트
│   ├── base_agent.py       # 기본 에이전트 클래스
│   ├── db.py               # 데이터베이스 관련 함수
│   ├── prompts.py          # 프롬프트 템플릿
│   ├── state.py            # 에이전트 상태 관리
│   ├── tools.py            # 공통 도구 모음
│   └── utils.py            # 유틸리티 함수
├── subagents/              # 하위 에이전트
│   ├── balanced_meal_agent/  # 균형 잡힌 식단 추천
│   ├── meal_input_agent/     # 식사 입력 처리
│   └── nutrient_agent/       # 영양소 분석
├── agent_main.py           # 메인 에이전트 (라우터)
├── nodes.py                # 워크플로우 노드
└── workflow.py             # 워크플로우 정의
```

### 2. 주요 컴포넌트

#### 2.1 공통 모듈 (common/)

- **BaseAgent**: 모든 에이전트의 기본 클래스로, LLM 초기화 및 도구 관리 기능 제공
- **AgentState**: 에이전트의 상태를 관리하는 Pydantic 모델
- **APIClient**: 백엔드 API와의 통신을 담당하는 클라이언트
- **DB**: 데이터베이스 관련 함수 모음
- **Tools**: 에이전트가 사용하는 도구 모음
- **Utils**: 유틸리티 함수 모음
- **Prompts**: 프롬프트 템플릿 모음

#### 2.2 메인 에이전트 (FoodAgent)

사용자 요청을 분석하고 적절한 에이전트/워크플로우로 라우팅하는 메인 에이전트

- **주요 기능**:
  - 사용자 요청 분석
  - 적절한 에이전트/워크플로우 선택
  - 결과 통합 및 반환

- **작동 방식**:
  1. 사용자 요청 분석
  2. 라우팅 결정 (balanced_meal 또는 meal_nutrient)
  3. 선택된 에이전트/워크플로우 실행
  4. 결과 반환

#### 2.3 하위 에이전트 (subagents/)

##### 2.3.1 BalancedMealAgent

균형 잡힌 식단을 추천하는 독립적인 에이전트

- **주요 기능**:
  - 사용자 목표에 따른 식단 유형 결정
  - 사용자 정보 및 선호도 기반 맞춤형 식단 추천
  - 영양소 균형 분석
  - 식사 시간대별 추천

- **작동 방식**:
  1. 사용자 정보 및 선호도 조회
  2. 목표를 식단 유형으로 변환
  3. 식단 계획 조회
  4. 맞춤형 식사 추천

##### 2.3.2 MealInputAgent

식사 입력을 처리하는 에이전트 (MealNutrientWorkflow의 일부)

- **주요 기능**:
  - 식사 입력 분석
  - 영양소 정보 추출
  - 식사 기록 저장

- **작동 방식**:
  1. 식사 입력 분석
  2. 영양소 정보 조회
  3. 식사 기록 저장

##### 2.3.3 NutrientAgent

영양소 분석 및 관리를 담당하는 에이전트 (MealNutrientWorkflow의 일부)

- **주요 기능**:
  - 주간 식사 기록 분석
  - 영양소 균형 평가
  - 부족한 영양소 식품 추천

- **작동 방식**:
  1. 주간 데이터 조회
  2. 영양소 분석
  3. 영양소 보완을 위한 음식 추천

#### 2.4 워크플로우 (MealNutrientWorkflow)

MealInputAgent와 NutrientAgent를 순차적으로 실행하는 워크플로우

- **주요 기능**:
  - 식사 입력 처리
  - 영양소 분석
  - 결과 통합

- **작동 방식**:
  1. MealInputAgent 실행
  2. NutrientAgent 실행
  3. 결과 반환

## LangGraph 기반 워크플로우

### 1. 노드 정의

- **nodes.py**: 워크플로우의 각 단계를 처리하는 노드 함수들이 정의되어 있습니다.
  - `vector_search_node`: 벡터 검색 수행
  - `evaluate_data_node`: 데이터 평가
  - `self_rag_node`: 자체 RAG 처리
  - `bmi_calculation_node`: BMI 계산
  - `nutrition_calculation_node`: 영양 계산
  - `nutrition_analysis_node`: 영양 분석
  - `recommend_supplements_node`: 보충제 추천
  - `meal_planning_node`: 식사 계획 수립

### 2. 상태 전달

- **AgentState**: 에이전트의 상태를 관리하는 Pydantic 모델로, 각 노드 간에 상태가 전달됩니다.
  - 사용자 정보, 입력, 의도, 식사 기록, 영양 분석 결과 등을 포함

### 3. 에이전트와 툴 연결

- **BaseAgent**: 모든 에이전트의 기본 클래스로, LLM 초기화 및 도구 관리 기능 제공
  - `_initialize_tools()`: @tool 데코레이터가 붙은 모든 메서드를 자동으로 수집하여 Tool 객체로 변환
  - `bind_llm()`: 외부에서 LLM을 바인딩
  - `get_tools()`: 도구 목록 반환

## FoodAgent 처리 흐름

### 1. 사용자 요청 수신

- **agent_main.py**: FoodAgent가 사용자 요청을 수신합니다.
  - `run()`: 사용자 요청을 분석하고 적절한 에이전트/워크플로우로 라우팅

### 2. 요청 분석 및 라우팅

- **FoodAgent**: 사용자 요청을 분석하여 적절한 에이전트/워크플로우를 선택합니다.
  - `route_request()`: 사용자 요청을 분석하여 라우팅 결정

### 3. 에이전트/워크플로우 실행

- **BalancedMealAgent**: 식단 추천 요청 시 실행
  - 사용자 정보 및 선호도 조회
  - 목표를 식단 유형으로 변환
  - 식단 계획 조회
  - 맞춤형 식사 추천

- **MealNutrientWorkflow**: 식사 입력 또는 영양 분석 요청 시 실행
  - MealInputAgent: 식사 입력 처리
  - NutrientAgent: 영양소 분석

### 4. 결과 반환

- **FoodAgent**: 처리 결과를 반환합니다.
  - 에러 발생 시 에러 메시지 반환
  - 성공 시 처리 결과 반환

## 설치 및 설정

1. 필요한 패키지 설치:
```bash
pip install -r requirements.txt
```

2. 환경 변수 설정:
```bash
export OPENAI_API_KEY=your_api_key
```

## 사용 예시

```python
from agents.food.agent_main import FoodAgent
from agents.food.common.state import AgentState

# 에이전트 초기화
agent = FoodAgent()

# 상태 초기화
state = AgentState(user_id="1", user_input="오늘 아침에 김치찌개를 먹었어")

# 에이전트 실행
result = await agent.run(state.user_input, state)
print(result)
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
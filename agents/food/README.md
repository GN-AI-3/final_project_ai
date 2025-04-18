# AI 기반 식단 추천 시스템

## 프로젝트 구조

```
make2/
├── main.py                 # 메인 실행 파일
├── new_agent_graph.py      # 에이전트 그래프 정의
├── llm_config.py          # LLM 설정
├── node/                   # 노드 모듈
│   ├── core_agent_node.py  # 핵심 에이전트 노드
│   ├── answer_merger_node.py # 답변 병합 노드
│   └── ask_user_node.py    # 사용자 질문 노드
├── tool/                   # 도구 모듈
│   └── recommend_diet_tool.py # 식단 추천 도구
└── util/                   # 유틸리티 모듈
    ├── sql_utils.py        # SQL 유틸리티
    └── table_schema.py     # 데이터베이스 스키마
```

## 주요 기능

### 1. 식단 추천 시스템
- 사용자 맞춤형 식단 계획 생성
- 영양소 분석 및 추천
- 식사 시간대별 메뉴 제안

### 2. 데이터베이스 관리
- PostgreSQL 데이터베이스 연동
- 회원 정보 관리
- 식단 기록 저장 및 분석

### 3. AI 에이전트 시스템
- LangGraph 기반 에이전트 구현
- 다단계 의사결정 프로세스
- 사용자 상호작용 처리

## 기술 스택

- Python 3.8+
- LangGraph
- PostgreSQL
- LangChain
- OpenAI API

## 설치 및 실행

1. 환경 설정
```bash
pip install -r requirements.txt
```

2. 환경 변수 설정
```bash
cp .env.example .env
# .env 파일에 필요한 환경 변수 설정
```

3. 데이터베이스 설정
```bash
python util/setup_db.py
```

4. 실행
```bash
python main.py
```

## 주요 모듈 설명

### 노드 (node/)
- `core_agent_node.py`: 핵심 에이전트 로직 구현
- `answer_merger_node.py`: 여러 도구의 결과를 병합
- `ask_user_node.py`: 사용자 입력 처리

### 도구 (tool/)
- `recommend_diet_tool.py`: 식단 추천 알고리즘 구현

### 유틸리티 (util/)
- `sql_utils.py`: 데이터베이스 작업 유틸리티
- `table_schema.py`: 데이터베이스 스키마 정의

## 데이터베이스 스키마

### 주요 테이블
- members: 회원 정보
- meals: 식사 기록
- nutrition_info: 영양 정보
- meal_plans: 식단 계획

## API 엔드포인트

### 식단 추천
```
POST /api/recommend-diet
{
    "member_id": int,
    "days": int (optional)
}
```

### 식단 분석
```
GET /api/analyze-meals/{member_id}
```

### 영양 정보 조회
```
GET /api/nutrition/{food_name}
```

## 에러 처리

- 데이터베이스 연결 오류
- API 요청 실패
- 사용자 입력 검증
- 영양 정보 누락

## 보안

- 환경 변수 사용
- API 키 보호
- 사용자 데이터 암호화

## 테스트

```bash
python -m pytest tests/
```

## 라이선스

MIT License 
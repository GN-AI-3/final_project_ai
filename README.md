# Exercise Data Crawling Project

이 프로젝트는 ExRx.net 웹사이트에서 운동 정보를 수집하고 구조화된 JSON 형식으로 저장하는 크롤링 도구입니다.

## 프로젝트 구조

```
final_project_ai/
├── data/
│   ├── exercise_list_csv/      # 원본 CSV 파일 저장
│   └── exercise_list_json/     # 구조화된 JSON 파일 저장
└── src/
    ├── crawling/
    │   ├── crawling_test.py    # 기본 크롤링 구현
    │   └── crawling_structured.py  # 구조화된 크롤링 구현
    └── langgraph/
        ├── agents/
        │   ├── __init__.py
        │   ├── exercise_agent.py    # 운동 정보 처리 에이전트
        │   ├── workout_agent.py     # 운동 프로그램 생성 에이전트
        │   └── user_agent.py        # 사용자 상호작용 에이전트
        ├── nodes/
        │   ├── __init__.py
        │   ├── exercise_node.py     # 운동 정보 처리 노드
        │   ├── workout_node.py      # 운동 프로그램 생성 노드
        │   └── user_node.py         # 사용자 입력 처리 노드
        ├── edges/
        │   ├── __init__.py
        │   ├── exercise_edges.py    # 운동 정보 관련 엣지
        │   ├── workout_edges.py     # 운동 프로그램 관련 엣지
        │   └── user_edges.py        # 사용자 상호작용 관련 엣지
        └── graph.py                 # 메인 그래프 구현
```

## 주요 기능

### 1. 웹 크롤링

- Selenium과 BeautifulSoup을 사용하여 ExRx.net 웹사이트에서 운동 정보 수집
- 자동화 감지 방지를 위한 stealth 모드 구현
- 랜덤 대기 시간 적용으로 서버 부하 방지

### 2. 데이터 구조화

- 운동 정보를 체계적인 JSON 형식으로 변환
- Classification, Instructions, Comments, Muscles 등 섹션별 구조화
- 이미지와 비디오 미디어 요소 추출

### 3. 데이터 저장

- 중복 방지를 위한 파일명 자동 생성
- UTF-8 인코딩으로 한글 지원
- 실패한 운동 목록 추적 및 로깅

### 4. LangGraph 기반 운동 프로그램 생성

- 다중 에이전트 시스템을 통한 운동 프로그램 생성
- 사용자 맞춤형 운동 추천
- 운동 정보 기반의 프로그램 최적화

#### 에이전트 구성

1. Exercise Agent

   - 운동 정보 데이터베이스 관리
   - 운동 특성 분석 및 분류
   - 운동 간 관계 추적

2. Workout Agent

   - 사용자 목표 기반 프로그램 생성
   - 운동 강도 및 순서 최적화
   - 프로그램 진행 상황 모니터링

3. User Agent
   - 사용자 입력 처리 및 검증
   - 사용자 피드백 수집
   - 프로그램 조정 요청 처리

#### 노드 구성

1. Exercise Node

   - 운동 정보 처리 및 검색
   - 운동 데이터베이스 관리
   - 운동 특성 분석

2. Workout Node

   - 운동 프로그램 생성
   - 프로그램 최적화
   - 진행 상황 추적

3. User Node
   - 사용자 입력 처리
   - 피드백 수집
   - 프로그램 조정

## 설치 및 실행

### 필수 패키지

```bash
pip install selenium selenium-stealth beautifulsoup4 webdriver-manager langchain langgraph
```

### 실행 방법

```bash
# 크롤링 실행
python src/crawling/crawling_structured.py

# LangGraph 기반 운동 프로그램 생성
python src/langgraph/graph.py
```

## 데이터 구조

### JSON 출력 형식

```json
{
    "exercise_name": "운동 이름",
    "url": "운동 페이지 URL",
    "media": {
        "images": [...],
        "videos": [...]
    },
    "Classification": {
        "Utility": "...",
        "Mechanics": "...",
        "Force": "..."
    },
    "Instructions": {
        "Preparation": "...",
        "Execution": "..."
    },
    "Comments": {
        "Comments": "...",
        "Easier": [...],
        "Harder": [...]
    },
    "Muscles": {
        "Target": [...],
        "Synergists": [...],
        "Dynamic Stabilizers": [...],
        "Stabilizers": [...],
        "Antagonist Stabilizers": [...]
    }
}
```

## 주요 개선사항

1. HTML 구조 분석 개선

   - BeautifulSoup을 사용한 정확한 HTML 파싱
   - 중첩된 리스트 구조 처리
   - 불필요한 공백 제거 및 텍스트 정규화

2. 데이터 정합성 향상

   - 중복 데이터 제거
   - 섹션별 데이터 구조화
   - 누락된 정보 처리

3. 에러 처리 강화

   - 실패한 운동 추적
   - 상세한 에러 로깅
   - 안정적인 파일 저장

4. LangGraph 시스템 개선
   - 에이전트 간 효율적인 통신
   - 사용자 맞춤형 프로그램 생성
   - 실시간 피드백 처리

## 주의사항

1. 웹사이트 접근 제한을 고려한 적절한 대기 시간 설정
2. 네트워크 연결 상태 확인
3. 충분한 저장 공간 확보
4. LangGraph 시스템 실행 시 충분한 메모리 할당

## 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다.

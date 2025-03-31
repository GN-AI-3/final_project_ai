# AI 운동 프로그램 생성기

ExRx.net의 운동 데이터를 기반으로 사용자 맞춤형 운동 프로그램을 생성하는 AI 시스템입니다. LangGraph를 활용한 다중 에이전트 아키텍처를 통해 개인화된 운동 프로그램을 생성하고 최적화합니다.

## 시스템 아키텍처

### 1. 데이터 수집 시스템

- **크롤링 엔진**

  - Selenium과 BeautifulSoup 기반 웹 크롤링
  - 자동화 감지 방지 (stealth 모드)
  - 서버 부하 방지를 위한 랜덤 대기

- **데이터 처리**
  - HTML 구조 분석 및 정규화
  - 중복 데이터 제거
  - JSON 형식 변환

### 2. AI 시스템 (LangGraph)

- **에이전트**

  - Exercise Agent: 운동 정보 관리 및 분석
  - Workout Agent: 프로그램 생성 및 최적화
  - User Agent: 사용자 상호작용 처리

- **노드**

  - Exercise Node: 운동 데이터 처리
  - Workout Node: 프로그램 생성
  - User Node: 사용자 입력 처리

- **엣지**
  - Exercise Edges: 운동 정보 흐름
  - Workout Edges: 프로그램 생성 흐름
  - User Edges: 사용자 상호작용 흐름

## 기술 스택

- **크롤링**: Selenium, BeautifulSoup
- **AI 프레임워크**: LangGraph, LangChain
- **데이터 처리**: JSON, CSV
- **언어**: Python 3.8+

## 프로젝트 구조

```
final_project_ai/
├── agents/                    # 에이전트 구현
│   ├── exercise/             # 운동 관련 에이전트
│   ├── food/                 # 식단 관련 에이전트
│   ├── general/              # 일반 기능 에이전트
│   ├── schedule/             # 일정 관련 에이전트
│   ├── base_agent.py         # 기본 에이전트 클래스
│   ├── specialized_agents.py # 특수 에이전트 구현
│   ├── supervisor.py         # 에이전트 감독자
│   └── __init__.py
|
├── main.py                   # 메인 실행 파일
├── requirements.txt          # 의존성 패키지 목록
├── .env                      # 환경 변수 설정
└── .gitignore               # Git 제외 파일 목록
```

## 설치 및 실행

### 필수 패키지 설치

```bash
pip install -r requirements.txt
```

### 실행 방법

```bash
python main.py
```

## 데이터 구조

### 운동 정보 JSON

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

## 시스템 요구사항

### 하드웨어

- 최소 8GB RAM
- 20GB 이상 저장공간
- GPU 가속 지원 (선택사항)

### 소프트웨어

- Python 3.8 이상
- Chrome 브라우저
- 안정적인 인터넷 연결

## 주의사항

### 데이터 수집

- 웹사이트 접근 제한 준수
- 적절한 대기 시간 설정
- 네트워크 연결 상태 확인

### AI 시스템

- 충분한 메모리 할당
- 실시간 피드백 처리
- 데이터 정합성 검증

## 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다.

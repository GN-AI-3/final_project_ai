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
  - Food Agent: 식단 정보 관리 및 추천
  - Schedule Agent: 사용자 운동 일정 관리
  - General Agent: 일반적인 사용자 질문 응답
  - Motivation Agent: 사용자 동기 부여 및 격려

- **감독 시스템**
  - 슈퍼바이저: 에이전트 간 조정 및 통합 응답 생성
  - 분류 모듈: 사용자 질의 유형 분석
  - 상태 관리: 대화 및 사용자 정보 추적

## 기술 스택

- **AI 프레임워크**: LangGraph, LangChain, OpenAI API
- **벡터 데이터베이스**: Qdrant
- **API 서버**: FastAPI, Uvicorn
- **컨테이너화**: Docker, Docker Compose
- **임베딩 모델**: Sentence Transformers, Hugging Face
- **백엔드**: Python 3.8+, Redis
- **로깅 및 모니터링**: 자체 로깅 시스템

## 프로젝트 구조

```
final_project_ai/
├── agents/                       # 에이전트 구현
│   ├── exercise/                 # 운동 관련 에이전트
│   ├── food/                     # 식단 관련 에이전트
│   ├── general/                  # 일반 기능 에이전트
│   ├── schedule/                 # 일정 관련 에이전트
│   ├── motivation/               # 동기부여 에이전트
│   ├── base_agent.py            # 기본 에이전트 클래스
│   └── __init__.py
│
├── supervisor_modules/           # 슈퍼바이저 시스템 모듈
│   ├── agents_manager/          # 에이전트 관리 모듈
│   ├── classification/          # 메시지 분류 모듈
│   ├── response/                # 응답 처리 모듈
│   ├── state/                   # 상태 관리 모듈
│   ├── utils/                   # 유틸리티 함수
│   └── __init__.py
│
├── qdrant_utils/                 # Qdrant 벡터 데이터베이스 유틸리티
│   ├── qdrant_client.py         # Qdrant 클라이언트
│   ├── data_analyzer.py         # 데이터 분석 도구
│   ├── search_insights.py       # 검색 결과 분석
│   ├── cron_scheduler.py        # 예약 작업 관리
│   └── __init__.py
│
├── common_prompts/               # 공통 프롬프트 템플릿
├── exercise/                     # 운동 데이터
├── workout_log/                  # 운동 로그 저장소
├── pt_log/                       # PT 세션 로그
├── debug_logs/                   # 디버깅 로그 파일
│
├── main.py                       # 메인 실행 파일
├── supervisor.py                 # 에이전트 감독자
├── api_server.py                 # FastAPI 서버
├── chat_history_manager.py       # 대화 기록 관리자
├── app.py                        # 웹 애플리케이션 진입점
│
├── Dockerfile                    # Docker 이미지 정의
├── docker-compose.yml            # Docker Compose 설정
├── start.sh                      # 시작 스크립트
├── requirements.txt              # 의존성 패키지 목록
└── .env                          # 환경 변수 설정
```

## 설치 및 실행

### 필수 패키지 설치

```bash
pip install -r requirements.txt
```

### Docker를 이용한 실행

```bash
docker-compose up -d
```

### 직접 실행

```bash
python main.py
```

### API 서버 실행

```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000
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
- Docker 및 Docker Compose (선택사항)
- 안정적인 인터넷 연결
- OpenAI API 키

## 주의사항

### 데이터 수집

- 웹사이트 접근 제한 준수
- 적절한 대기 시간 설정
- 네트워크 연결 상태 확인

### AI 시스템

- 충분한 메모리 할당
- 실시간 피드백 처리
- 데이터 정합성 검증
- API 키 관리 및 보안

## 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다.

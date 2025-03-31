# AI 운동 프로그램 생성기

ExRx.net의 운동 데이터를 기반으로 사용자 맞춤형 운동 프로그램을 생성하는 AI 시스템입니다.

## 주요 기능

- **데이터 수집**: ExRx.net에서 운동 정보 자동 수집
- **프로그램 생성**: LangGraph 기반 맞춤형 운동 프로그램 생성
- **실시간 피드백**: 사용자 피드백 기반 프로그램 최적화

## 기술 스택

- **크롤링**: Selenium, BeautifulSoup
- **AI 프레임워크**: LangGraph, LangChain
- **데이터 처리**: JSON, CSV

## 설치

```bash
# 필수 패키지 설치
pip install selenium selenium-stealth beautifulsoup4 webdriver-manager langchain langgraph
```

## 프로젝트 구조

```
final_project_ai/
├── data/
│   ├── exercise_list_csv/      # 원본 데이터
│   └── exercise_list_json/     # 구조화된 데이터
└── src/
    ├── crawling/              # 데이터 수집
    │   ├── crawling_test.py
    │   └── crawling_structured.py
    └── langgraph/             # AI 시스템
        ├── agents/            # 에이전트
        ├── nodes/             # 노드
        ├── edges/             # 엣지
        └── graph.py           # 메인 그래프
```

## 실행 방법

```bash
# 1. 운동 데이터 수집
python src/crawling/crawling_structured.py

# 2. AI 프로그램 생성
python src/langgraph/graph.py
```

## 시스템 요구사항

- Python 3.8+
- Chrome 브라우저
- 8GB RAM 이상
- 20GB 저장공간

## 데이터 구조

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

## 주의사항

- 웹사이트 접근 제한 준수
- 충분한 메모리 할당
- 안정적인 네트워크 연결

## 라이선스

MIT License

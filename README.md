# LangGraph 기반 Supervisor 패턴 챗봇

이 프로젝트는 LangGraph를 사용하여 구현된 supervisor 패턴의 챗봇입니다. 사용자의 메시지를 분석하여 적절한 전문가 에이전트로 라우팅하고 응답을 생성합니다.

## 주요 기능

- 메시지 카테고리 자동 분류 (운동, 식단, 일정, 일반 대화)
- 전문가별 특화된 응답 생성
- 비동기 처리로 효율적인 메시지 처리
- LangSmith를 통한 대화 추적 및 분석

## 프로젝트 구조

```
main_project_ai/
├── agents/
│   ├── __init__.py
│   ├── base_agent.py
│   ├── specialized_agents.py
│   └── supervisor.py
├── main.py
├── requirements.txt
└── .env
```

## 설치 방법

1. 가상환경 생성 및 활성화
```bash
conda create -n main python=3.11
conda activate main
```

2. 필요한 패키지 설치
```bash
pip install -r requirements.txt
```

3. 환경 변수 설정
`.env` 파일에 다음 환경 변수들을 설정합니다:
```
OPENAI_API_KEY=your-api-key-here
LANGCHAIN_API_KEY=your-langsmith-api-key-here
LANGCHAIN_PROJECT=your-project-name
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

## 실행 방법

```bash
python main.py
```

## 사용 가능한 에이전트

- **운동 전문가**: 운동 방법, 운동 효과 등에 대한 답변
- **영양 전문가**: 식단, 영양, 음식 등에 대한 답변
- **일정 관리 전문가**: 일정, 시간 관리, 계획 등에 대한 답변
- **일반 대화 에이전트**: 기타 일반적인 대화 처리

## 기술 스택

- Python 3.11
- LangChain
- LangGraph
- OpenAI GPT-3.5-turbo
- python-dotenv
- LangSmith

## 라이선스

MIT License
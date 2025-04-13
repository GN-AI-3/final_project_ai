# Qdrant 유틸리티

벡터 데이터베이스 Qdrant 관련 유틸리티 모음입니다. 이 유틸리티는 채팅 데이터를 분석하여 인사이트를 추출하고 이를 벡터 데이터베이스에 저장하며, 저장된 데이터를 검색할 수 있는 기능을 제공합니다.

## 주요 기능

1. **데이터 분석 (data_analyzer.py)**

   - PostgreSQL 채팅 메시지 데이터 가져오기
   - 메시지 분석을 통한 사용자 성향 추출
   - 메시지에서 주요 이벤트 추출
   - 분석 결과를 Qdrant에 저장

2. **Qdrant 클라이언트 (qdrant_client.py)**

   - 벡터 데이터베이스 연결 및 관리
   - 텍스트 임베딩 생성
   - 벡터 검색 및 필터링
   - 컬렉션 관리 기능

3. **인사이트 검색 (search_insights.py)**
   - 사용자 이메일로 인사이트 검색
   - 텍스트 쿼리로 유사 인사이트 검색
   - 필터링 및 결과 정렬

## 설치 및 실행 방법

### 필수 패키지 설치

```bash
pip install python-dotenv openai qdrant-client psycopg2-binary
```

### 환경 변수 설정

`.env` 파일을 프로젝트 루트에 생성하고 다음 변수 설정:

```
OPENAI_API_KEY=your_openai_api_key
QDRANT_API_KEY=your_qdrant_api_key
QDRANT_COLLECTION=chat_insights
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=your_db_name
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
```

## 사용 예시

### 데이터 분석 실행하기

```bash
# 어제 데이터 분석
python -m qdrant_utils.data_analyzer

# 특정 날짜 범위 분석
python -m qdrant_utils.data_analyzer --mode range --start-date 2023-01-01 --end-date 2023-01-31

# 스케줄러 모드로 실행 (매일 자정에 분석)
python -m qdrant_utils.data_analyzer --mode schedule
```

### 인사이트 검색하기

```bash
# 특정 사용자의 인사이트 검색
python -m qdrant_utils.search_insights --email user@example.com

# 특정 키워드로 인사이트 검색
python -m qdrant_utils.search_insights --query "운동 습관"

# 사용자와 키워드 조합 검색
python -m qdrant_utils.search_insights --email user@example.com --query "식단 관리" --limit 10

# 최근 7일 데이터만 검색
python -m qdrant_utils.search_insights --email user@example.com --days 7

# 결과를 파일로 저장
python -m qdrant_utils.search_insights --email user@example.com --output results.json
```

## 프로그래밍 방식으로 사용하기

```python
import asyncio
from qdrant_utils import QdrantManager
from qdrant_utils.search_insights import search_user_insights

# Qdrant 관리자 사용
async def use_qdrant():
    manager = QdrantManager()

    # 임베딩 생성
    vector = await manager.generate_embeddings("운동 습관에 관한 텍스트")

    # 벡터 검색
    results = await manager.search_by_text("운동 습관", {"user_email": "user@example.com"})

    # 검색 유틸리티 사용
    insights = await search_user_insights(
        email="user@example.com",
        query="운동",
        days=30,
        limit=5
    )

# 실행
asyncio.run(use_qdrant())
```

## 폴더 구조

```
qdrant_utils/
├── __init__.py            # 패키지 초기화
├── data_analyzer.py       # 데이터 분석 모듈
├── qdrant_client.py       # Qdrant 클라이언트
├── search_insights.py     # 인사이트 검색 도구
└── logs/                  # 로그 파일 디렉토리
```

## 참고사항

- 분석은 일일 단위로 수행되며, 결과는 Qdrant 컬렉션에 저장됩니다.
- 한번 분석된 데이터는 중복 저장되지 않도록 관리됩니다.
- 텍스트 임베딩은 OpenAI의 `text-embedding-3-small` 모델을 사용합니다.

import os
from dotenv import load_dotenv
from pathlib import Path

# agents/food 디렉토리 경로 찾기
agents_food_dir = Path(__file__).parent.parent

# 환경 변수 로드 (agents/food 폴더의 .env 파일 사용)
load_dotenv()

# 백엔드 API 설정
EC2_BACKEND_URL = os.getenv("EC2_BACKEND_URL", "http://3.37.8.185:8000")
AUTH_TOKEN = os.getenv(
    "AUTH_TOKEN",
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzM4NCJ9.eyJwYXNzd29yZCI6IiQyYSQxMCRkNEhjZUNXc1VnL2FUdzQ2am14bDV1SHVwV0h4YjdIeWpTVmUuRzlXSi5LeXdoMkRQVmVyRyIsInBob25lIjoiMDEwLTExMTEtMjIyMiIsIm5hbWUiOiLsnqXqt7zsmrAiLCJpZCI6NCwidXNlclR5cGUiOiJNRU1CRVIiLCJlbWFpbCI6InVzZXIxQHRlc3QuY29tIiwiZ29hbHMiOlsiV0VJR0hUX0xPU1MiXSwiaWF0IjoxNzQ1MDUyMzE5LCJleHAiOjM2MzcyMTIzMTl9._Y1TZGQOGPZDLB4YdYX-21TN1bv_aYBuxX9N_EvY6y_QADh2hLJDEyUKIIGXuc4i"
) 
 
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 데이터베이스 설정
DB_HOST = os.getenv("DB_HOST", "3.37.8.185")
DB_PORT = os.getenv("DB_PORT", "5433")  # 기본 포트 번호 5432 사용
DB_DB = os.getenv("DB_DB", "gym")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")

# 데이터베이스 URI
PG_URI = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_DB}" 
import os
from dotenv import load_dotenv
 
# 환경 변수 로드
load_dotenv()
     
# PostgreSQL 연결 설정
DB_HOST = os.getenv("DB_HOST", "3.37.8.185")
DB_PORT = os.getenv("DB_PORT", "5433")
DB_DB = os.getenv("DB_DB", "gym")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")

# PostgreSQL URI (psycopg2 형식)
PG_URI = f"host={DB_HOST} port={DB_PORT} dbname={DB_DB} user={DB_USER} password={DB_PASSWORD}"  
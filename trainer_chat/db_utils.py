import os
from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "3.37.8.185")
DB_PORT = os.getenv("DB_PORT", "5433")
DB_DB = os.getenv("DB_DB", "gym")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")

PG_URI = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_DB}"

db = SQLDatabase.from_uri(PG_URI) 
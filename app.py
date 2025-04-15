"""
AI 피트니스 코치 API 서버 진입점
api_server.py에서 정의된 FastAPI 앱을 실행합니다.
"""
import uvicorn
from api_server import app

if __name__ == "__main__":
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
#!/bin/bash

echo "[start.sh] ✅ Qdrant 분석기 실행 시작"
python -m qdrant_utils.data_analyzer --mode schedule &

echo "[start.sh] ✅ FastAPI 서버 실행 시작"
gunicorn -k uvicorn.workers.UvicornWorker --workers 2 --bind 0.0.0.0:8000 api_server:app

"""
헬스장 출석률 알림 시스템 메인 모듈
"""
import argparse
import logging
import os
from gym_attendance.api.server import start_server
from gym_attendance.utils.logging import setup_logger

# 메인 로거 설정
logger = setup_logger('main')

def main():
    """
    CLI 명령을 처리하는 메인 함수
    """
    parser = argparse.ArgumentParser(description="헬스장 출석률 알림 시스템")
    
    # 사용 가능한 명령 추가
    subparsers = parser.add_subparsers(dest="command", help="실행할 명령")
    
    # API 서버 시작 명령
    server_parser = subparsers.add_parser("server", help="API 서버 시작")
    server_parser.add_argument("--host", default="0.0.0.0", help="서버 호스트 (기본값: 0.0.0.0)")
    server_parser.add_argument("--port", type=int, default=8000, help="서버 포트 (기본값: 8000)")
    server_parser.add_argument("--reload", action="store_true", help="자동 리로드 활성화")
    
    # 명령 파싱
    args = parser.parse_args()
    
    # 명령 실행
    if args.command == "server":
        logger.info(f"API 서버 시작 - http://{args.host}:{args.port}")
        start_server(host=args.host, port=args.port, reload=args.reload)
    else:
        # 명령이 지정되지 않은 경우 기본으로 서버 시작
        logger.info("명령이 지정되지 않아 기본 API 서버를 시작합니다.")
        start_server()
    
if __name__ == "__main__":
    main() 
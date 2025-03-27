#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
헬스장 출석률 기반 알림 시스템 애플리케이션
"""
import os
import logging
from dotenv import load_dotenv
from langgraph.attendance_agent import create_attendance_workflow

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("gym_attendance_agent.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def run_attendance_workflow(user_id: str):
    """
    특정 헬스장 회원에 대한 출석률 알림 워크플로우를 실행
    """
    # 워크플로우 생성
    workflow = create_attendance_workflow()
    
    # 컴파일
    app = workflow.compile()

    # 초기 상태
    initial_state = {"user_id": user_id}

    # 실행
    logger.info(f"헬스장 회원 {user_id}의 출석률 알림 워크플로우 실행 중...")
    result = app.invoke(initial_state)
    logger.info(f"헬스장 회원 {user_id}의 워크플로우 실행 완료")

    return result

def main():
    # 환경 변수 로드
    load_dotenv()

    # OpenAI API 키 확인
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")      
        return

    # OpenAI API 키 설정
    os.environ["OPENAI_API_KEY"] = api_key

    logger.info("헬스장 출석률 알림 에이전트 시작...")

    # 6가지 운동 목표 유형을 모두 테스트
    user_ids = ["user1", "user2", "user3", "user4", "user5", "user6"]

    # 각 회원에 대한 알림 처리
    for user_id in user_ids:
        logger.info(f"헬스장 회원 {user_id}에 대한 출석률 알림 처리 중...")
        try:
            # 출석률 알림 워크플로우 실행
            result = run_attendance_workflow(user_id)

            # 결과 로깅
            notifications = result.get("notifications", [])
            delivery_results = result.get("delivery_results", [])

            if notifications:
                logger.info(f"헬스장 회원 {user_id}에게 {len(notifications)}개의 알림이 생성되었습니다.")
                for i, notification in enumerate(notifications, 1):
                    success = next((res["success"] for res in delivery_results if res["index"] == i), False)
                    status = "성공" if success else "실패"
                    # 알림 메시지 전체 내용 출력
                    logger.info(f"알림 {i} ({status}): {notification}")
                    # 콘솔에도 명확하게 구분해서 출력
                    print(f"\n===== 회원 {user_id}의 알림 =====")
                    print(f"목표: {result['user_data']['personal_goal']}")
                    print(f"출석률: {result['user_data']['attendance_rate']}%")
                    print(f"메시지: {notification}")
                    print("="*30)
            else:
                logger.info(f"헬스장 회원 {user_id}에게 보낼 알림이 없습니다.")

        except Exception as e:
            logger.error(f"헬스장 회원 {user_id} 처리 중 오류 발생: {str(e)}", exc_info=True)

    logger.info("헬스장 출석률 알림 에이전트 종료...")

if __name__ == "__main__":
    main() 
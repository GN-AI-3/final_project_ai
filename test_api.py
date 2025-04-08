import requests
import json
import sys
from datetime import datetime

def test_api(member_id="1", message="안녕하세요, 오늘은 어떤 운동을 해야 할까요?"):
    """API 서버를 테스트합니다."""
    try:
        url = "http://localhost:8000/chat"
        
        payload = {
            "member_id": member_id,
            "message": message
        }
        
        print(f"\n[{datetime.now().isoformat()}] API 요청 전송 중...")
        print(f"요청 URL: {url}")
        print(f"요청 데이터: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        
        # API 호출
        response = requests.post(url, json=payload)
        
        print(f"\n응답 상태 코드: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n=== API 응답 ===")
            print(f"타입: {result.get('type', 'unknown')}")
            print(f"메시지: {result.get('response', '응답 없음')}")
            print(f"생성 시간: {result.get('created_at', 'unknown')}")
            print("=== 응답 끝 ===")
            return True
        else:
            print(f"오류 응답: {response.text}")
            return False
    except Exception as e:
        print(f"테스트 실행 중 오류 발생: {str(e)}")
        return False

def test_workflow_api(member_id="1"):
    """워크플로우 API를 테스트합니다."""
    try:
        url = "http://localhost:8000/motivation"
        
        payload = {
            "member_id": member_id,
            "message": "동기부여 메시지를 받고 싶습니다."
        }
        
        print(f"\n[{datetime.now().isoformat()}] 워크플로우 API 요청 전송 중...")
        print(f"요청 URL: {url}")
        print(f"요청 데이터: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        
        # API 호출
        response = requests.post(url, json=payload)
        
        print(f"\n응답 상태 코드: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n=== 워크플로우 API 응답 ===")
            print(f"타입: {result.get('type', 'unknown')}")
            print(f"메시지: {result.get('response', '응답 없음')}")
            print(f"생성 시간: {result.get('created_at', 'unknown')}")
            print("=== 응답 끝 ===")
            return True
        else:
            print(f"오류 응답: {response.text}")
            return False
    except Exception as e:
        print(f"테스트 실행 중 오류 발생: {str(e)}")
        return False

if __name__ == "__main__":
    # 테스트할 회원 ID와 메시지 설정
    member_id = sys.argv[1] if len(sys.argv) > 1 else "1"
    message = sys.argv[2] if len(sys.argv) > 2 else "안녕하세요, 오늘은 어떤 운동을 해야 할까요?"
    
    print("\n=== 채팅 API 테스트 ===")
    test_api(member_id, message)
    
    print("\n=== 워크플로우 API 테스트 ===")
    test_workflow_api(member_id)
    
    print("\n테스트 완료") 
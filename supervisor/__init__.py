"""
Supervisor 패키지
에이전트 관리 및 메시지 처리 기능을 제공하는 패키지
"""

# 직접 import 추가
import sys
import os

# 상위 디렉토리를 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 순환 임포트 방지를 위해 여기서는 Supervisor 클래스를 직접 임포트하지 않음
# 대신 필요한 모듈에서 직접 임포트하도록 함 
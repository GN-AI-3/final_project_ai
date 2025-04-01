import re
from typing import Optional

class NameExtractor:
    @staticmethod
    def extract_name(message: str) -> Optional[str]:
        """메시지에서 이름을 추출합니다."""
        # 트레이너 이름 추출
        trainer_match = re.search(r'([가-힣]+)\s*선생님', message)
        if trainer_match:
            return trainer_match.group(1)
        
        # 회원 이름 추출
        member_match = re.search(r'([가-힣]+)\s*님', message)
        if member_match:
            return member_match.group(1)
        
        # 일반 이름 추출 (선생님, 님 접미사가 없는 경우)
        name_match = re.search(r'([가-힣]+)(?:\s|$)', message)
        if name_match:
            return name_match.group(1)
        
        return None 
from datetime import datetime
from typing import Optional, Tuple


class Schedule:
    """예약 정보를 나타내는 모델 클래스
    
    Attributes:
        reservation_id: 예약 번호
        pt_contract_id: 환자 ID
        start_time: 예약 시작 시간
        end_time: 예약 종료 시간
        status: 예약 상태 (기본값: 'confirmed')
    """
    
    def __init__(
        self,
        reservation_id: str,
        pt_contract_id: int,
        start_time: datetime,
        end_time: datetime,
        status: str = 'confirmed'
    ) -> None:
        """예약 객체를 초기화합니다.
        
        Args:
            reservation_id: 예약 번호
            pt_contract_id: 환자 ID
            start_time: 예약 시작 시간
            end_time: 예약 종료 시간
            status: 예약 상태 (기본값: 'confirmed')
        """
        self.reservation_id = reservation_id
        self.pt_contract_id = pt_contract_id
        self.start_time = start_time
        self.end_time = end_time
        self.status = status
    
    @classmethod
    def from_db_row(cls, row: Tuple) -> Optional['Schedule']:
        """데이터베이스 행으로부터 Reservation 객체를 생성합니다.
        
        Args:
            row: 데이터베이스 행 튜플
            
        Returns:
            Optional['Reservation']: 생성된 Reservation 객체 또는 None
        """
        if not row:
            return None
        return cls(
            reservation_id=row[0],
            pt_contract_id=row[1],
            start_time=row[2],
            end_time=row[3],
            status=row[4]
        ) 
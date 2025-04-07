from datetime import datetime
from typing import Optional

class Reservation:
    """예약 정보를 나타내는 모델 클래스"""
    
    def __init__(
        self,
        reservation_no: str,
        pt_linked_id: int,
        start_time: datetime,
        end_time: datetime,
        state: str = 'confirmed'
    ):
        self.reservation_no = reservation_no
        self.pt_linked_id = pt_linked_id
        self.start_time = start_time
        self.end_time = end_time
        self.state = state
    
    @classmethod
    def from_db_row(cls, row: tuple) -> Optional['Reservation']:
        """데이터베이스 행으로부터 Reservation 객체를 생성합니다."""
        if not row:
            return None
        return cls(
            reservation_no=row[0],
            pt_linked_id=row[1],
            start_time=row[2],
            end_time=row[3],
            state=row[4]
        ) 
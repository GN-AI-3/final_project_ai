from typing import Any, Dict, Optional, Sequence

from langchain.agents import tool

from .sql_tools import relative_time_expr_to_sql


@tool
def gen_pt_schedule_query(
    input: str,
    trainer_id: int,
    status: str | None = None,
    name: Optional[str] = None,
    has_pt_log: Optional[bool] = None,
    is_deducted: Optional[bool] = None
) -> Sequence[Dict[str, Any]] | str:
    """
    트레이너의 PT 일정을 조회하는 SQL 쿼리를 생성합니다.

    Parameters:
    - input: 사용자의 입력
    - trainer_id: 트레이너의 고유 ID
    - status: 쉼표로 구분된 일정 상태 문자열
        - 유효한 값:
            - 'SCHEDULED': 예약됨
            - 'COMPLETED': 완료됨
            - 'CHANGED': 변경 이력
            - 'CANCELLED': 취소됨
            - 'NO_SHOW': 미참석
    - name: 회원 이름 검색 키워드 (부분 일치 검색)
    - has_pt_log: 운동 기록 여부 (True / False)
    - is_deducted: 회차 차감 여부 (True / False)

    Returns:
    - SQL 쿼리 문자열 또는 에러 메시지
    """

    sql_start_expr, sql_end_expr = relative_time_expr_to_sql.invoke(input)
    
    try:
        # 기본 WHERE 조건
        where_clauses = [
            "ps.is_deleted = false",
            "pc.is_deleted = false",
            "m.is_deleted = false",
            "pc.status = 'ACTIVE'",
            f"pc.trainer_id = {trainer_id}",
            f"ps.start_time >= {sql_start_expr}",
            f"ps.start_time < {sql_end_expr}"
        ]

        # 상태 필터 (쉼표 분리 후 IN 절 구성)
        if status:
            statuses = [s.strip() for s in status.split(",") if s.strip()]
            if statuses:
                status_in = ", ".join(f"'{s}'" for s in statuses)
                where_clauses.append(f"ps.status IN ({status_in})")

        # 회원 이름 검색 (부분 일치)
        if name:
            where_clauses.append(f"m.name ILIKE '%{name}%'")

        # has_pt_log 조건
        if has_pt_log:
            where_clauses.append(f"ps.has_pt_log = {str(has_pt_log).lower()}")

        # is_deducted 조건
        if is_deducted:
            where_clauses.append(f"ps.is_deducted = {str(is_deducted).lower()}")

        # 최종 쿼리 조립
        where_sql = " AND ".join(where_clauses)

        query = f"""
        SELECT
            ps.id,
            ps.current_pt_count,
            pc.total_count,
            ps.start_time,
            ps.end_time,
            m.name AS member_name
        FROM pt_schedule ps
            JOIN pt_contract pc ON ps.pt_contract_id = pc.id
            JOIN member m ON pc.member_id = m.id
        WHERE {where_sql}
        ORDER BY ps.start_time;
        """

        return query

    except Exception as e:
        return f"Error while building query: {str(e)}"

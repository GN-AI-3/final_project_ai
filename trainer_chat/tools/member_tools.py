from langchain.agents import tool

@tool
def gen_find_member_id_query(member_name: str) -> int:
    """
    회원 이름을 기반으로 회원 ID를 찾습니다.

    Parameters:
    - member_name: 회원 이름 (호칭 제외, 부분 일치 검색)

    Returns:
    - 회원 ID
    """

    query = f"""
    SELECT m.id
    FROM member m
    JOIN pt_contract pc ON m.id = pc.member_id
    WHERE m.name LIKE '%{member_name}%'
    AND m.is_deleted = false
    AND pc.is_deleted = false;
    """

    return query
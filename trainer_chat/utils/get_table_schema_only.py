from sqlalchemy import create_engine, text
from typing import List

DEFAULT_EXCLUDE_COLUMNS = [
    "password",
    "fcm_token",
    "deleted_at",
    "deleted_by",
    "is_deleted",
    "created_by",
    "modified_by",
    "created_at",
    "modified_at"
]

def get_table_schema_only(
    engine,
    table_names: List[str]
) -> str:
    """
    지정한 테이블들의 주요 컬럼(민감/불필요 컬럼 제외)과 Primary Key 정보를 PostgreSQL 스키마 형태로 문자열로 반환합니다.

    Args:
        engine: SQLAlchemy 데이터베이스 엔진 객체
        table_names (List[str]): 스키마 정보를 추출할 테이블 이름 리스트

    Returns:
        str: 각 테이블의 CREATE TABLE 구문 형태로 정리된 스키마 문자열
    """
    result = []
    with engine.connect() as conn:
        for table_name in table_names:
            # 1. 컬럼 정보 수집
            column_query = text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = :table_name AND table_schema = 'public'
                ORDER BY ordinal_position;
            """)
            columns = [row[0] for row in conn.execute(column_query, {
                "table_name": table_name
            }).fetchall() if row[0] not in DEFAULT_EXCLUDE_COLUMNS]

            # 2. Primary Key
            pk_query = text("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_name = :table_name AND tc.table_schema = 'public';
            """)
            pk_columns = {row[0] for row in conn.execute(pk_query, {
                "table_name": table_name
            }).fetchall()}

            # 3. Foreign Key
            fk_query = text("""
                SELECT
                    kcu.column_name
                FROM 
                    information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                   AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_name = :table_name AND tc.table_schema = 'public';
            """)
            fk_columns = {row[0] for row in conn.execute(fk_query, {
                "table_name": table_name
            }).fetchall()}

            # 4. 간결한 요약 생성
            col_defs = []
            for col in columns:
                suffix = []
                if col in pk_columns:
                    suffix.append("PK")
                if col in fk_columns:
                    suffix.append("FK")
                if suffix:
                    col_defs.append(f"{col} {' '.join(suffix)}")
                else:
                    col_defs.append(col)

            summary = f"-- {table_name}({', '.join(col_defs)})"
            result.append(summary)

    return "\n".join(result)

from sqlalchemy import text
from sqlalchemy.engine import Engine
from typing import List
import re

EXCLUDE_COLUMNS = {
    'password', 'fcm_token',
    'created_at', 'modified_at', 'deleted_at',
    'created_by', 'modified_by', 'deleted_by',
    'is_deleted'
}

def summarize_db_schema(engine: Engine, table_names: List[str]) -> str:
    summaries = []

    with engine.connect() as conn:
        for table in table_names:
            # 1. 컬럼 타입 조회
            column_query = text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = :table_name AND table_schema = 'public'
                ORDER BY ordinal_position
            """)
            columns = conn.execute(column_query, {"table_name": table}).fetchall()

            # 2. Primary Key
            pk_query = text("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_name = :table_name AND tc.table_schema = 'public'
            """)
            pk_columns = {row[0] for row in conn.execute(pk_query, {"table_name": table})}

            # 3. Foreign Key
            fk_query = text("""
                SELECT kcu.column_name, ccu.table_name AS ref_table
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                  ON tc.constraint_name = ccu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_name = :table_name AND tc.table_schema = 'public'
            """)
            fk_columns = {row[0]: row[1] for row in conn.execute(fk_query, {"table_name": table})}

            # 4. ENUM (CHECK 제약조건에서 추출)
            enum_query = text("""
                SELECT con.conname, pg_get_constraintdef(con.oid) AS definition
                FROM pg_constraint con
                INNER JOIN pg_class rel ON rel.oid = con.conrelid
                WHERE rel.relname = :table_name AND contype = 'c'
            """)
            enum_defs = conn.execute(enum_query, {"table_name": table}).fetchall()
            enum_map = extract_enum_values(enum_defs)

            # 5. 정리
            col_defs = []
            for col_name, data_type in columns:
                if col_name in EXCLUDE_COLUMNS:
                    continue

                col_type = simplify_type(data_type)
                if col_name in enum_map:
                    col_type = f"enum{enum_map[col_name]}"

                suffix = []
                if col_name in pk_columns:
                    suffix.append("PK")
                if col_name in fk_columns:
                    suffix.append(f"FK → {fk_columns[col_name]}.id")

                if suffix:
                    col_defs.append(f"{col_name} {col_type} {' '.join(suffix)}")
                else:
                    col_defs.append(f"{col_name} {col_type}")

            summary = f"table {table} (\n  " + ",\n  ".join(col_defs) + "\n)"
            summaries.append(summary)

    return "\n\n".join(summaries)


def simplify_type(data_type: str) -> str:
    if data_type.startswith("character varying") or data_type == "text":
        return "varchar"
    if data_type.startswith("timestamp"):
        return "timestamp"
    if data_type == "bigint":
        return "bigint"
    if data_type == "boolean":
        return "boolean"
    if data_type in {"integer", "int"}:
        return "int"
    return data_type


def extract_enum_values(checks):
    result = {}
    for _, expr in checks:
        # CHECK (...) 안의 내용 중 = ANY (ARRAY[...]) 또는 = ANY ((ARRAY[...])::text[]) 패턴을 찾음
        match = re.search(
            r"\(\(?(\w+)\)::text = ANY\s*\(\(?ARRAY\[(.*?)\]\)?(::\w+\[\])?\)", expr
        )
        if match:
            column = match.group(1)
            values_raw = match.group(2)
            values = re.findall(r"'([^']+)'::character varying", values_raw)
            result[column] = str(values)
    return result
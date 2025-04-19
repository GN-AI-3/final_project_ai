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
    table_names: List[str],
    schema: str = 'public',
    exclude_columns: List[str] = DEFAULT_EXCLUDE_COLUMNS
) -> str:
    result = []
    with engine.connect() as conn:
        for table_name in table_names:
            # 1. 컬럼 정보 수집
            column_query = text("""
                SELECT 
                    column_name,
                    data_type,
                    is_nullable
                FROM information_schema.columns
                WHERE table_name = :table_name AND table_schema = :schema_name
                ORDER BY ordinal_position;
            """)
            columns = conn.execute(column_query, {
                "table_name": table_name,
                "schema_name": schema
            }).fetchall()

            # 2. Primary Key
            pk_query = text("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_name = :table_name AND tc.table_schema = :schema_name;
            """)
            pk_columns = {row[0] for row in conn.execute(pk_query, {
                "table_name": table_name,
                "schema_name": schema
            }).fetchall()}

            # 3. Foreign Key
            fk_query = text("""
                SELECT
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM 
                    information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                   AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_name = :table_name AND tc.table_schema = :schema_name;
            """)
            fk_map = {}
            for row in conn.execute(fk_query, {
                "table_name": table_name,
                "schema_name": schema
            }):
                fk_map[row[0]] = (row[1], row[2])  # {컬럼명: (참조테이블, 참조컬럼)}

            # 4. DDL 생성
            lines = []
            for col_name, data_type, is_nullable in columns:
                if col_name in exclude_columns:
                    continue
                line = f"    {col_name} {data_type.upper()}"
                if is_nullable == 'NO':
                    line += " NOT NULL"
                if col_name in pk_columns:
                    line += " PRIMARY KEY"
                if col_name in fk_map:
                    ref_table, ref_col = fk_map[col_name]
                    line += f" REFERENCES {ref_table}({ref_col})"
                lines.append(line)

            ddl = f"CREATE TABLE {table_name} (\n" + ",\n".join(lines) + "\n);"
            result.append(ddl)
    return "\n\n".join(result)

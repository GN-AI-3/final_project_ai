from langchain.tools import tool
from tavily import TavilyClient
import os
import psycopg2
import re
from dotenv import load_dotenv
from psycopg2 import sql
import json
from elasticsearch import Elasticsearch
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from qdrant_client.models import SearchParams

load_dotenv()

elasticsearch_host = os.getenv("ELASTICSEARCH_HOST")
elasticsearch_token = os.getenv("ELASTICSEARCH_SERVICEACCOUNTTOKEN")

es = Elasticsearch(
    elasticsearch_host,
    bearer_auth=elasticsearch_token
).options(ignore_status=400)

exercise_index_name = "exercises"

qdrant_client = QdrantClient(
    url="https://9429a5d7-55d9-43fa-8ad7-8e6cfcd37e22.europe-west3-0.gcp.cloud.qdrant.io:6333", 
    api_key=os.getenv("QDRANT_API_KEY")
)

model = SentenceTransformer('all-mpnet-base-v2')

DB_CONFIG = {
    "dbname": os.getenv("DB_DB"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

TABLE_SCHEMA = {
    "exercise_record": {
        "columns": ["id", "member_id", "exercise_id", "date", "record_data", "memo_data"],
        "foreign_keys": {
            "member_id": "member.id",
            "exercise_id": "exercise.id"
        },
        "description": "사용자의 개별 운동 수행 기록. record_data는 세트/반복/무게 등의 상세 기록이며, memo_data는 자유 메모입니다. exercise_id는 exercise 테이블의 id와 연결해 운동 이름(name)을 조회해야 합니다."
    },
    "member": {
        "columns": ["id", "name", "email", "phone", "profile_image", "goal"],
        "description": "사용자 정보. goal은 사용자의 운동 목표입니다 (예: 벌크업, 체중 감량)."
    },
    "pt_contract": {
        "columns": ["id","member_id", "trainer_id"],
        "foreign_keys": {
            "member_id": "member.id",
            "trainer_id": "trainer.id"
        },
        "description": "PT 계약 정보, 이 테이블에서 트레이너의 회원 정보를 조회할 수 있다."
    },
    "pt_log": {
        "columns": ["id", "member_id", "trainer_id"],
        "foreign_keys": {
            "member_id": "member.id",
            "trainer_id": "trainer.id"
        },
        "description": "PT 수업 일지"
    },
    "pt_log_exercise": {
        "columns": ["id", "pt_log_id", "exercise_id", "sets", "reps", "weight"],
        "foreign_keys": {
            "pt_log_id": "pt_log.id",
            "exercise_id": "exercise.id"
        },
        "description": "PT 수업 일지에 포함된 운동 정보"
    }
}

def web_search(query: str) -> str:
    """웹 검색 운동 루틴 추천"""
    tavily_client = TavilyClient(
        api_key=os.getenv("TAVILY_API_KEY")
    )
    results = tavily_client.search(query)

    filtered_results = sorted(
        [r for r in results.get("results", []) if r.get("score", 0) >= 0.7],
        key=lambda x: x.get("score", 0),
        reverse=True
    )[:3]

    return json.dumps(filtered_results, indent=2, ensure_ascii=False)

@tool
def get_user_goal(user_id: str) -> str:
    """PostgreSQL - member table에서 사용자 목표 정보 조회"""
    query = f"SELECT goal FROM member WHERE id = '{user_id}';"
    print("query: ", query)
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                result = cursor.fetchall()
                return str(result)
    except Exception as e:
        return f"Database error: {str(e)}"
    
@tool
def get_user_physical_info(user_id: str) -> str:
    """PostgreSQL - inbody table에서 사용자 신체 정보 조회"""
    query = f"SELECT tall, weight, bmi FROM inbody WHERE member_id = {user_id};"
    print("query: ", query)
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                result = cursor.fetchall()

        if result:
            row = result[0]
            tall, weight, bmi = row[0], row[1], row[2]
            return (
                f"사용자 신체 정보:\n"
                f"- 키: {tall}cm\n"
                f"- 몸무게: {weight}kg\n"
                f"- BMI: {bmi}\n"
            )
        else:
            return "사용자의 신체 정보가 없습니다"
    except Exception as e:
        return f"Database error: {str(e)}"

@tool
def get_user_exercise_record(user_id: str) -> str:
    """PostgreSQL - exercise_record table에서 사용자 운동 기록 조회"""
    query = f"SELECT * FROM exercise_record WHERE member_id = {user_id};"
    print("query: ", query)
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                result = cursor.fetchall()
                return str(result)
    except Exception as e:
        return f"Database error: {str(e)}"

def get_all_table_schema() -> str:
    """PostgreSQL - 사용 가능한 테이블과 컬럼 정보를 반환"""
    schema_info = []
    for table_name, table_info in TABLE_SCHEMA.items():
        schema_info.append(f"테이블: {table_name}")
        schema_info.append(f"컬럼: {', '.join(table_info['columns'])}")
        schema_info.append(f"설명: {table_info['description']}")
        schema_info.append("--------------------------------")
    return "\n".join(schema_info)

def master_select_db(table_name: str, column_name: str, value: str) -> str:
    """PostgreSQL - 사전 정의된 모든 테이블에서 테이블명, 컬럼명, 값으로 데이터 조회
    table_name, column_name, value 모두 필수입니다.
    TABLE_SCHEMA 에 정의된 테이블만 사용 가능
    TABLE_SCHEMA 에 정의된 컬럼만 사용 가능
    
    Args:
        table_name: 조회할 테이블 이름
        column_name: (선택) 조건 컬럼 이름
        value: (선택) 조건 값
        
    Returns:
        조회된 데이터의 JSON 문자열
    """
    if table_name not in TABLE_SCHEMA:
        print("table_name: ", table_name)
        return "Invalid table name"
    
    if column_name not in TABLE_SCHEMA[table_name]["columns"]:
        print("column_name: ", column_name)
        return "Invalid column name"
    
    try:
        query = sql.SQL("SELECT * FROM {} WHERE {} = %s").format(
            sql.Identifier(table_name),
            sql.Identifier(column_name)
        )

        params = (value,)
        print("query: ", query)
        print("params: ", params)

        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                column_names = [desc[0] for desc in cursor.description]

                result = [dict(zip(column_names, row)) for row in rows]
                return json.dumps(result, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        return f"Database error: {str(e)}"

def master_select_db_multi(
    table_name: str, 
    conditions: dict
) -> str:
    """
    PostgreSQL - 사전 정의된 테이블에서 여러 조건(column=value)으로 데이터 조회
    TABLE_SCHEMA 에 정의된 테이블과 컬럼만 사용 가능

    Args:
        table_name: 조회할 테이블 이름
        conditions: 조회 조건 (예: {"id": "1", "email": "test@gmail.com"})

    Returns:
        JSON 문자열로 된 결과
    """
    if table_name not in TABLE_SCHEMA:
        return "Invalid table name"
    
    for col in conditions.keys():
        if col not in TABLE_SCHEMA[table_name]["columns"]:
            return f"Invalid column name: {col}"

    try:
        where_clauses = [
            sql.SQL("{} = %s").format(sql.Identifier(col)) for col in conditions.keys()
        ]
        query = sql.SQL("SELECT * FROM {} WHERE {}").format(
            sql.Identifier(table_name),
            sql.SQL(" AND ").join(where_clauses)
        )

        params = tuple(conditions.values())

        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                column_names = [desc[0] for desc in cursor.description]

                result = [dict(zip(column_names, row)) for row in rows]
                return json.dumps(result, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": f"Database error: {str(e)}"})
    
# def master_select_db_multi(table_name: str, conditions: dict) -> str:
#     """
#     PostgreSQL - 지정된 테이블에 대해 조건 기반 조회 수행.
#     조건 컬럼이 다른 테이블에 있으면 자동으로 JOIN 수행.

#     Args:
#         table_name (str): 기준 테이블
#         conditions (dict): 조건 컬럼과 값 (예: {"name": "장근우"})

#     Returns:
#         str: JSON 결과 또는 오류 메시지
#     """
#     if table_name not in TABLE_SCHEMA:
#         return json.dumps({"error": "Invalid table name"})

#     try:
#         base_alias = "t0"
#         joins = []
#         where_clauses = []
#         used_tables = {table_name: base_alias}
#         alias_counter = 1

#         for cond_col, cond_val in conditions.items():
#             found = False
#             for t_name, schema in TABLE_SCHEMA.items():
#                 if cond_col in schema["columns"]:
#                     found = True
#                     if t_name not in used_tables:
#                         alias = f"t{alias_counter}"
#                         alias_counter += 1
#                         used_tables[t_name] = alias

#                         # 조인 경로 추론
#                         for fk_col, ref in TABLE_SCHEMA[t_name].get("foreign_keys", {}).items():
#                             ref_table, ref_col = ref.split(".")
#                             if ref_table in used_tables:
#                                 joins.append(
#                                     sql.SQL("JOIN {} {} ON {}.{} = {}.{}").format(
#                                         sql.Identifier(t_name),
#                                         sql.Identifier(alias),
#                                         sql.Identifier(alias),
#                                         sql.Identifier(fk_col),
#                                         sql.Identifier(used_tables[ref_table]),
#                                         sql.Identifier(ref_col),
#                                     )
#                                 )

#                     where_clauses.append(
#                         sql.SQL("{}.{} = %s").format(
#                             sql.Identifier(used_tables[t_name]),
#                             sql.Identifier(cond_col)
#                         )
#                     )
#                     break
#             if not found:
#                 return json.dumps({"error": f"Invalid column name: {cond_col}"})

#         select_fields = sql.SQL(", ").join([
#             sql.SQL(f"{alias}.*") for alias in used_tables.values()
#         ])

#         from_clause = sql.SQL("{} {}").format(
#             sql.Identifier(table_name),
#             sql.SQL("AS {}").format(sql.Identifier(base_alias))
#         )

#         query = sql.SQL("SELECT {} FROM {} {} WHERE {}").format(
#             select_fields,
#             from_clause,
#             sql.SQL(" ").join(joins),
#             sql.SQL(" AND ").join(where_clauses)
#         )

#         params = list(conditions.values())

#         with psycopg2.connect(**DB_CONFIG) as conn:
#             with conn.cursor() as cursor:
#                 cursor.execute(query, params)
#                 rows = cursor.fetchall()
#                 column_names = [desc[0] for desc in cursor.description]

#                 result = [dict(zip(column_names, row)) for row in rows]
#                 return json.dumps(result, indent=2, ensure_ascii=False, default=str)

#     except Exception as e:
#         return json.dumps({"error": f"Database error: {str(e)}"})

def search_exercise_by_name(name: str):
    name_compact = name.replace(" ", "")

    try:
        res = es.search(
            index=exercise_index_name,
            query={
                "bool": {
                    "should": [
                        {
                            "term": {
                                "name_compact": {
                                    "value": name_compact,
                                    "boost": 30  # 정확 일치 최고 가중치
                                }
                            }
                        },
                        {
                            "match_phrase": {
                                "name": {
                                    "query": name,
                                    "boost": 10
                                }
                            }
                        },
                        {
                            "multi_match": {
                                "query": name,
                                "type": "best_fields",
                                "fields": ["name^1", "name._2gram^0.2", "name._3gram^0.1"]
                            }
                        }
                    ],
                    "minimum_should_match": 1
                }
            }
        )

        hits = res["hits"]["hits"]
        if not hits:
            return json.dumps([])

        max_score = hits[0]["_score"]
        threshold = max_score * 0.98

        exercises = [
            {
                "id": hit["_source"]["exercise_id"],
                "name": hit["_source"]["name"]
            }
            for hit in hits if hit["_score"] >= threshold
        ]
        
        if len(exercises) == 1:
            result = exercises[0]  # 단일 객체
        else:
            result = exercises

        return json.dumps(result, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": f"Database error: {str(e)}"})
    
def retrieve_exercise_info_by_similarity(query: str):
    """Qdrant - 운동 정보 검색"""
    query_vector = model.encode(query).tolist()
    try:
        res = qdrant_client.search(
            collection_name="exercises",
            query_vector=query_vector,
            limit=3,
            search_params=SearchParams(hnsw_ef=128, exact=False)
        )

        filtered_results = [
            {
                "score": round(result.score, 4),
                "content": result.payload.get("content", "No content")
            }
            for result in res if result.score >= 0.6
        ]

        for i, item in enumerate(filtered_results):
            print(f"{i+1}. 🔹 Score: {item['score']}\n   📄 Content: {item['content']}\n")

        return json.dumps(filtered_results, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Database error: {str(e)}"})

from dotenv import load_dotenv
import os
import psycopg2
import openai
from typing import List, Tuple

load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_DB"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

def select_workout_log(pt_contract_id: int) -> str:
    """
    exercise_record 테이블에서 운동 기록을 조회하는 tool.
    """

    query = """
        SELECT er.date, er.memo_data, er.record_data, e.name AS exercise_name
        FROM exercise_record er
        JOIN exercise e ON er.exercise_id = e.id
        WHERE er.member_id = (
            SELECT member_id
            FROM pt_contract
            WHERE id = %s
        )
        ORDER BY er.date DESC
        LIMIT 50;
    """
    
    params = (pt_contract_id,)

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows

def select_pt_log(pt_contract_id: int) -> str:
    """
    pt_log_exercise 테이블에서 PT 일지를 조회하는 tool.
    """

    query = """
        SELECT
            ple.pt_log_id,
            e.name AS exercise_name,
            ple.feedback,
            ple.reps,
            ple.sets,
            ple.weight
        FROM pt_log_exercise ple
        JOIN pt_log pl ON ple.pt_log_id = pl.id
        JOIN exercise e ON ple.exercise_id = e.id
        WHERE pl.pt_schedule_id IN (
            SELECT id
            FROM pt_schedule
            WHERE pt_contract_id = %s
            ORDER BY start_time DESC
            LIMIT 3
    );
    """
    
    params = (pt_contract_id,)

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows

if __name__ == "__main__":
    print("select_workout_log(10): ", select_workout_log(10))
    print("select_pt_log(10): ", select_pt_log(10))


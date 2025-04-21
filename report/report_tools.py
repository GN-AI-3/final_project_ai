import psycopg2
import os

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
            e.name AS exercise_name,
            ple.feedback,
            ple.reps,
            ple.sets,
            ple.weight,
            ps.start_time
        FROM pt_log_exercise ple
        JOIN pt_log pl ON ple.pt_log_id = pl.id
        JOIN pt_schedule ps ON pl.pt_schedule_id = ps.id
        JOIN exercise e ON ple.exercise_id = e.id
        WHERE ps.id IN (
            SELECT id
            FROM pt_schedule
            WHERE pt_contract_id = %s
            AND start_time < NOW()
            ORDER BY start_time DESC
            LIMIT 3
        )
        ORDER BY ps.start_time DESC;
    """
    
    params = (pt_contract_id,)

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows

def process_pt_log_result(rows):
    result = []
    for row in rows:
        pt_log_entry = {
            "exercise_name": row[0],
            "feedback": row[1],
            "reps": row[2],
            "sets": row[3],
            "weight": row[4],
            "date": row[5]
        }
        result.append(pt_log_entry)
    return result

def select_inbody_data(pt_contract_id: int) -> str:
    """
    inbody 테이블에서 inbody 정보를 조회하는 노드
    """

    query = """
        SELECT 
            i.date,
            i.muscle_mass,
            i.body_fat_percentage,
            i.bmi
        FROM 
            pt_contract pc
        JOIN 
            inbody i ON pc.member_id = i.member_id
        WHERE 
            pc.id = %s
        ORDER BY 
            i.date DESC
        LIMIT 3;
    """

    params = (pt_contract_id,)

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows

def process_inbody_data(rows):
    result = []
    for row in rows:
        inbody_entry = {
            "date": row[0],
            "muscle_mass": row[1],
            "body_fat_percentage": row[2],
            "bmi": row[3]
        }
        result.append(inbody_entry)
    return result
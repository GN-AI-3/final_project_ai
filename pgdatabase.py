import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

def connect_to_database(dbname=os.getenv("POSTGRES_DB"), user=os.getenv("POSTGRES_USER"), password=os.getenv("POSTGRES_PASSWORD"), host=os.getenv("POSTGRES_HOST"), port=os.getenv("POSTGRES_PORT")):
    try:
        conn = psycopg2.connect(
            database=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        print(f"데이터베이스 '{dbname}'에 성공적으로 연결되었습니다.")
        return conn
    except psycopg2.Error as e:
        print(f"데이터베이스 연결 오류: {e}")
        return None

def execute_query(conn, query):
    if not conn:
        return None
    
    cursor = conn.cursor()
    try:
        cursor.execute(query)
        if query.upper().startswith("SELECT"):
            result = cursor.fetchall()
            return result
        else:
            conn.commit()
            return True
    except psycopg2.Error as e:
        print(f"쿼리 실행 오류: {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()

def main():
    conn = connect_to_database()
    if not conn:
        return
    
    try:
        while True:
            query = input("SQL문 입력 (종료하려면 'FIN' 입력): ")
            if query.upper() == "FIN":
                break
            
            result = execute_query(conn, query)
            if result and query.upper().startswith("SELECT"):
                print(result)
    finally:
        conn.close()
        print("데이터베이스 연결이 종료되었습니다.")

if __name__ == "__main__":
    main()

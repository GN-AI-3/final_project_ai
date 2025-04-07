"""
데이터베이스 연결 및 사용자 정보 조회 도구
"""
import os
import psycopg2
from typing import Dict, Any, Optional, List
import logging
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logger = logging.getLogger(__name__)

class DBConnectionTool:
    """
    데이터베이스 연결 및 사용자 정보 조회를 위한 도구
    """
    
    @staticmethod
    def get_connection():
        """
        PostgreSQL 데이터베이스 연결을 생성하고 반환합니다.
        
        Returns:
            connection: 데이터베이스 연결 객체
        """
        try:
            # 환경 변수에서 DB 연결 정보 가져오기
            db_host = os.getenv("POSTGRES_HOST")
            db_port = os.getenv("POSTGRES_PORT")
            db_name = os.getenv("POSTGRES_DB")
            db_user = os.getenv("POSTGRES_USER")
            db_password = os.getenv("POSTGRES_PASSWORD")
            
            # 환경 변수가 없는 경우 로그 출력
            if not all([db_host, db_port, db_name, db_user, db_password]):
                logger.warning("일부 DB 연결 정보가 환경 변수에 설정되어 있지 않습니다.")
            
            # 연결 생성
            connection = psycopg2.connect(
                host=db_host or "localhost",
                port=db_port or "5433", 
                dbname=db_name or "gym",
                user=db_user or "postgres",
                password=db_password or "1234"
            )
            
            return connection
        
        except Exception as e:
            logger.error(f"DB 연결 중 오류 발생: {str(e)}")
            return None
    
    @staticmethod
    def get_user_goals(email: str) -> List[str]:
        """
        사용자의 목표 목록을 가져옵니다.
        
        Args:
            email (str): 사용자 이메일
            
        Returns:
            List[str]: 사용자 목표 목록
        """
        goals = []
        connection = None
        
        try:
            connection = DBConnectionTool.get_connection()
            
            if connection:
                cursor = connection.cursor()
                
                # 먼저 이메일로 사용자 ID 조회
                id_query = """
                SELECT id FROM public.member
                WHERE email = %s
                """
                
                cursor.execute(id_query, (email,))
                user_result = cursor.fetchone()
                
                if user_result:
                    user_id = user_result[0]
                    
                    # 사용자 ID로 목표 조회
                    goals_query = """
                    SELECT goal FROM public.member_goal_list
                    WHERE email = %s
                    """
                    
                    cursor.execute(goals_query, (user_id,))
                    results = cursor.fetchall()
                    
                    # 목표 목록 추출
                    goals = [result[0] for result in results]
                
                cursor.close()
        
        except Exception as e:
            logger.error(f"사용자 목표 조회 중 오류 발생: {str(e)}")
        
        finally:
            if connection:
                connection.close()
        
        return goals
    
    @staticmethod
    def get_user_info(email: str) -> Optional[Dict[str, Any]]:
        """
        사용자 정보를 가져옵니다.
        
        Args:
            email (str): 사용자 이메일
            
        Returns:
            Optional[Dict[str, Any]]: 사용자 정보
        """
        user_info = None
        connection = None
        
        try:
            connection = DBConnectionTool.get_connection()
            
            if connection:
                cursor = connection.cursor()
                
                # 사용자 정보 조회 쿼리
                query = """
                SELECT id, name, email, phone, profile_image 
                FROM public.member
                WHERE email = %s
                """
                
                cursor.execute(query, (email,))
                result = cursor.fetchone()
                
                if result:
                    user_info = {
                        "id": result[0],
                        "name": result[1],
                        "email": result[2],
                        "phone": result[3],
                        "profile_image": result[4]
                    }
                
                cursor.close()
        
        except Exception as e:
            logger.error(f"사용자 정보 조회 중 오류 발생: {str(e)}")
        
        finally:
            if connection:
                connection.close()
        
        return user_info
    
    @staticmethod
    def translate_goal_to_korean(goal: str) -> str:
        """
        영문 목표를 한글로 변환합니다.
        
        Args:
            goal (str): 영문 목표
            
        Returns:
            str: 한글 목표
        """
        goal_map = {
            "WEIGHT_LOSS": "체중 감량",
            "MUSCLE_GAIN": "근육 증가",
            "HEALTH_IMPROVEMENT": "건강 개선",
            "ENDURANCE": "지구력 향상", 
            "FLEXIBILITY": "유연성 향상",
            "STRENGTH": "근력 향상",
            "BALANCE": "균형감 향상",
            "STRESS_RELIEF": "스트레스 해소",
            "POSTURE_IMPROVEMENT": "자세 교정"
        }
        
        return goal_map.get(goal, goal) 
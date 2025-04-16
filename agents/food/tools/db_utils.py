"""
데이터베이스 유틸리티 모듈

이 모듈은 데이터베이스 연결 및 쿼리 실행을 위한 유틸리티 함수들을 정의합니다.
"""

from asyncio.log import logger
import os
from datetime import datetime
from typing import Dict, List, Optional, Union, Any
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import asyncpg
from pydantic import BaseModel, ConfigDict
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 데이터베이스 연결 정보
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT")),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}

# 비동기 연결 풀
_pool = None

async def get_pool() -> asyncpg.Pool:
    """비동기 연결 풀을 가져옵니다."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(**DB_CONFIG)
    return _pool

async def close_pool():
    """비동기 연결 풀을 종료합니다."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None

def get_sync_connection():
    """동기 연결을 가져옵니다."""
    return psycopg2.connect(**DB_CONFIG)

async def execute_query(query: str, *args) -> List[Dict[str, Any]]:
    """비동기 쿼리를 실행합니다."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetch(query, *args)
        return [dict(row) for row in result]

def execute_sync_query(query: str, *args) -> List[Dict[str, Any]]:
    """동기 쿼리를 실행합니다."""
    with get_sync_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, args)
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

async def execute_transaction(queries: List[tuple]) -> List[Dict[str, Any]]:
    """트랜잭션을 실행합니다."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            results = []
            for query, args in queries:
                result = await conn.fetch(query, *args)
                results.extend([dict(row) for row in result])
            return results
 
class UserInfo(BaseModel):
    """사용자 정보 모델"""
    model_config = ConfigDict(validate_by_name=True)
    
    id: int
    name: str
    email: str
    phone: str
    goal: str
    user_type: str
    height: float
    weight: float
    activity_level: str
    allergies: List[str]
    dietary_preference: str
    meal_pattern: str
    meal_times: List[str]
    food_preferences: List[str]
    special_requirements: List[str]

class FoodNutrition(BaseModel):
    """식품 영양소 정보 모델"""
    model_config = ConfigDict(validate_by_name=True)
    
    name: str
    calories: float
    protein: float
    carbs: float
    fat: float
    serving_size: float
    serving_unit: str

class MealRecord(BaseModel):
    """식사 기록 모델"""
    model_config = ConfigDict(validate_by_name=True)
    
    user_id: int
    food_name: str
    portion: float
    unit: str
    meal_type: str
    calories: float
    protein: float
    carbs: float
    fat: float
    created_at: datetime

class DietPlan(BaseModel):
    """식단 계획 모델"""
    model_config = ConfigDict(validate_by_name=True)
    
    diet_type: str
    user_gender: str
    meal_plan: Dict[str, List[Dict[str, Any]]]
    nutrition_goals: Dict[str, float]

async def get_user_info(user_id: str) -> Dict[str, Any]:
    """
    사용자 정보를 조회합니다.
    
    Args:
        user_id: 사용자 ID
        
    Returns:
        사용자 정보
    """
    print(f"사용자 정보 조회 시작: {user_id}")
 
    query = f"""
    SELECT
           m.name,
           m.goal,
           d.dietary_preference,
           d.food_preferences,
           d.allergies,
           d.meal_pattern,
           d.meal_times,
           d.special_requirements,
           d.activity_level,
           i.height,
           i.weight
    FROM member m
    LEFT JOIN create_user_diet_info_table d ON m.id = d.member_id
    LEFT JOIN inbody i ON m.id = i.member_id
    WHERE m.id = {user_id}
    ORDER BY i.date::timestamp DESC NULLS LAST
    LIMIT 1;
    """
    print(f"사용자 정보 조회 쿼리: {query}")
    result = await execute_query(query)
    print(f"사용자 정보 조회 결과: {result}")
    if not result:
        return None
            
    return result[0]
         

def get_food_nutrition(food_name: str) -> Optional[Dict[str, Any]]:
    """식품 영양소 정보 조회"""
    with get_sync_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute("""
                    SELECT 
                        id,
                        food_item_name,
                        calories,
                        protein,
                        carbs,
                        fat
                    FROM food_nutrition 
                    WHERE food_item_name ILIKE %s
                """, (f"%{food_name}%",))
                result = cur.fetchone()
                if result:
                    return FoodNutrition(**dict(result)).model_dump()
                return None
            except Exception as e:
                print(f"식품 영양소 정보 조회 중 오류 발생: {str(e)}")
                return None

def save_meal_record(
    user_id: int,
    meal_type: str,
    food_name: str,
    portion: float,
    unit: str,
    calories: float,
    protein: float,
    carbs: float,
    fat: float
) -> bool:
    """식사 기록 저장"""
    try:
        meal_record = MealRecord(
            user_id=user_id,
            food_name=food_name,
            portion=portion,
            unit=unit,
            meal_type=meal_type,
            calories=calories,
            protein=protein,
            carbs=carbs,
            fat=fat,
            created_at=datetime.now()
        )
        
        query = """
            INSERT INTO meal_records (
                user_id, food_name, portion, unit, meal_type,
                calories, protein, carbs, fat, created_at,
                meal_date, meal_time
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_DATE, CURRENT_TIME)
        """
        
        params = (
            meal_record.user_id,
            meal_record.food_name,
            meal_record.portion,
            meal_record.unit,
            meal_record.meal_type,
            meal_record.calories,
            meal_record.protein,
            meal_record.carbs,
            meal_record.fat,
            meal_record.created_at
        )
        
        return execute_sync_query(query, params)[0]["result"]
        
    except Exception as e:
        print(f"식사 기록 저장 중 오류 발생: {str(e)}")
        return False

def get_today_meals(user_id: int) -> List[Dict[str, Any]]:
    """오늘의 식사 기록 조회"""
    try:
        query = """
            SELECT * FROM meal_records 
            WHERE user_id = %s 
            AND meal_date = CURRENT_DATE
            ORDER BY meal_time
        """
        
        results = execute_sync_query(query, {"user_id": user_id})
        return [MealRecord(**dict(result)).model_dump() for result in results]
        
    except Exception as e:
        print(f"오늘의 식사 기록 조회 중 오류 발생: {str(e)}")
        return []

def get_weekly_meals(user_id: int) -> List[Dict[str, Any]]:
    """주간 식사 기록 조회"""
    try:
        query = """
            SELECT * FROM meal_records 
            WHERE user_id = %s 
            AND meal_date >= CURRENT_DATE - INTERVAL '7 days'
            ORDER BY meal_date, meal_time
        """
        
        results = execute_sync_query(query, {"user_id": user_id})
        return [MealRecord(**dict(result)).model_dump() for result in results]
        
    except Exception as e:
        print(f"주간 식사 기록 조회 중 오류 발생: {str(e)}")
        return []

def get_diet_plan(diet_type: str, user_gender: str) -> Optional[Dict[str, Any]]:
    """식단 계획 조회"""
    try:
        query = """
            SELECT * FROM diet_plans
            WHERE diet_type = %s AND user_gender = %s
        """
        
        result = execute_sync_query(query, {"diet_type": diet_type, "user_gender": user_gender})
        
        if result:
            return DietPlan(**dict(result[0])).model_dump()
        return None
        
    except Exception as e:
        print(f"식단 계획 조회 중 오류 발생: {str(e)}")
        return None

def get_user_preferences_db(user_id: int) -> Dict[str, Any]:
    """사용자 선호도 조회"""
    try:
        query = """
            SELECT 
                dietary_preference,
                food_preferences,
                allergies,
                meal_pattern,
                meal_times,
                special_requirements
            FROM user_diet_info
            WHERE member_id = %s
        """
        
        result = execute_sync_query(query, {"user_id": user_id})
        return result[0] if result else {}
        
    except Exception as e:
        print(f"사용자 선호도 조회 중 오류 발생: {str(e)}")
        return {}

def analyze_weekly_nutrition(weekly_meals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """주간 영양소 분석"""
    try:
        total_calories = sum(meal["calories"] for meal in weekly_meals)
        total_protein = sum(meal["protein"] for meal in weekly_meals)
        total_carbs = sum(meal["carbs"] for meal in weekly_meals)
        total_fat = sum(meal["fat"] for meal in weekly_meals)
        
        days = len(set(meal["meal_date"] for meal in weekly_meals))
        days = max(1, days)  # 0으로 나누는 것을 방지
        
        return {
            "avg_daily_calories": total_calories / days,
            "avg_daily_protein": total_protein / days,
            "avg_daily_carbs": total_carbs / days,
            "avg_daily_fat": total_fat / days
        }
        
    except Exception as e:
        print(f"주간 영양소 분석 중 오류 발생: {str(e)}")
        return {
            "avg_daily_calories": 0,
            "avg_daily_protein": 0,
            "avg_daily_carbs": 0,
            "avg_daily_fat": 0
        }

def recommend_foods(user_id: int) -> Dict[str, Any]:
    """식품 추천"""
    try:
        # 사용자 정보 조회
        user_info = get_user_info(user_id)
        if not user_info:
            return {"error": "사용자 정보를 찾을 수 없습니다."}
            
        # 주간 식사 기록 조회
        weekly_meals = get_weekly_meals(user_id)
        
        # 영양소 분석
        nutrition_analysis = analyze_weekly_nutrition(weekly_meals)
        
        # 사용자 선호도 조회
        preferences = get_user_preferences_db(user_id)
        
        # 추천 로직 구현
        recommended_foods = []
        # TODO: 실제 추천 로직 구현
        
        return {
            "user_info": user_info,
            "nutrition_analysis": nutrition_analysis,
            "preferences": preferences,
            "recommended_foods": recommended_foods
        }
        
    except Exception as e:
        print(f"식품 추천 중 오류 발생: {str(e)}")
        return {"error": str(e)}
 
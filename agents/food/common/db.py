from datetime import datetime
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, ConfigDict

load_dotenv()

# 데이터베이스 연결 정보
DB_NAME = os.getenv("DB_NAME", "mydb")
DB_USER = os.getenv("DB_USER", "myuser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "mysecretpassword")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

class UserInfo(BaseModel):
    """사용자 정보 모델"""
    model_config = ConfigDict(validate_by_name=True)
    
    member_id: int
    name: str
    gender: str
    height: float
    weight: float
    birth: datetime
    goal: str
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

def get_db_connection():
    """데이터베이스 연결"""
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )

def get_user_info(user_id: int) -> Optional[Dict[str, Any]]:
    """사용자 정보 조회"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT 
                m.member_id, m.name, m.gender, m.height, m.weight, m.birth, m.goal,
                d.activity_level, d.allergies, d.dietary_preference, d.meal_pattern,
                d.meal_times, d.food_preferences, d.special_requirements
            FROM member m
            LEFT JOIN user_diet_info d ON m.member_id = d.user_id
            WHERE m.member_id = %s
        """, (user_id,))
        result = cur.fetchone()
        if result:
            # 문자열을 리스트로 변환
            result_dict = dict(result)
            for field in ['allergies', 'meal_times', 'food_preferences', 'special_requirements']:
                if result_dict.get(field):
                    result_dict[field] = [item.strip() for item in result_dict[field].split(',')]
                else:
                    result_dict[field] = []
            
            return UserInfo(**result_dict).model_dump()
        return None
    finally:
        cur.close()
        conn.close()

def get_food_nutrition(food_name: str) -> Optional[Dict[str, Any]]:
    """식품 영양소 정보 조회"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT * FROM food_nutrition 
            WHERE name ILIKE %s
        """, (f"%{food_name}%",))
        result = cur.fetchone()
        if result:
            return FoodNutrition(**dict(result)).model_dump()
        return None
    finally:
        cur.close()
        conn.close()

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
    conn = get_db_connection()
    cur = conn.cursor()
    
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
        
        print(f"식사 기록 저장 시도: {meal_record.model_dump()}")  # 디버깅용 로그 추가
        
        cur.execute("""
            INSERT INTO meal_records (
                user_id, food_name, portion, unit, meal_type,
                calories, protein, carbs, fat, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
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
        ))
        conn.commit()
        print("식사 기록 저장 성공")  # 디버깅용 로그 추가
        return True
    except Exception as e:
        print(f"식사 기록 저장 중 오류 발생: {e}")
        print(f"오류 상세 정보: {type(e).__name__}")  # 오류 타입 출력
        import traceback
        print(f"오류 스택 트레이스: {traceback.format_exc()}")  # 스택 트레이스 출력
        return False
    finally:
        cur.close()
        conn.close()

def get_today_meals(user_id: int) -> List[Dict[str, Any]]:
    """오늘의 식사 기록 조회"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT * FROM meal_records 
            WHERE user_id = %s 
            AND DATE(created_at) = CURRENT_DATE
            ORDER BY created_at
        """, (user_id,))
        results = cur.fetchall()
        return [MealRecord(**dict(result)).model_dump() for result in results]
    finally:
        cur.close()
        conn.close()

def get_weekly_meals(user_id: int) -> List[Dict[str, Any]]:
    """주간 식사 기록 조회"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT 
                m.id, 
                m.user_id, 
                m.meal_type, 
                m.meal_date, 
                m.meal_time, 
                m.food_name, 
                m.portion
            FROM meal_records m
            WHERE m.user_id = %s
            AND m.meal_date >= CURRENT_DATE - INTERVAL '7 days'
            ORDER BY m.meal_date DESC, m.meal_time DESC;

        """, (user_id,))
        results = cur.fetchall()
        
        # 결과를 MealRecord 모델에 맞게 변환
        meals = []
        for result in results:
            meal_data = dict(result)
            # 필수 필드가 없는 경우 기본값 설정
            meal_data.setdefault('unit', 'g')
            meal_data.setdefault('calories', 0)
            meal_data.setdefault('protein', 0)
            meal_data.setdefault('carbs', 0)
            meal_data.setdefault('fat', 0)
            meals.append(meal_data)
        
        return meals
    finally:
        cur.close()
        conn.close()

def get_diet_plan(diet_type: str, user_gender: str) -> Optional[Dict[str, Any]]:
    """목표에 맞는 식단 계획 조회"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT * FROM diet_plans 
            WHERE diet_type = %s AND user_gender = %s
            ORDER BY RANDOM()
            LIMIT 1
        """, (diet_type, user_gender))
        result = cur.fetchone()
        if result:
            # DB 결과를 DietPlan 모델 형식으로 변환
            db_result = dict(result)
            return {
                "diet_type": db_result.get("diet_type", diet_type),
                "user_gender": db_result.get("user_gender", user_gender),
                "meal_plan": {
                    "breakfast": db_result.get("breakfast", ""),
                    "lunch": db_result.get("lunch", ""),
                    "dinner": db_result.get("dinner", "")
                },
                "nutrition_goals": {
                    "calories": 2000,  # 기본값
                    "protein": 100,    # 기본값
                    "carbs": 250,      # 기본값
                    "fat": 70          # 기본값
                }
            }
        return None
    finally:
        cur.close()
        conn.close()

def get_user_preferences_db(user_id: int) -> Dict[str, Any]:
    """사용자 선호도 조회"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT * FROM user_diet_info 
            WHERE user_id = %s
        """, (user_id,))
        preferences = cur.fetchone()
        
        if not preferences:
            return {
                "activity_level": "보통",
                "allergies": [],
                "dietary_preference": "일반",
                "meal_pattern": "3식",
                "meal_times": ["08:00", "13:00", "19:00"],
                "food_preferences": [],
                "special_requirements": []
            }
        
        return dict(preferences)
    finally:
        cur.close()
        conn.close()

def analyze_weekly_nutrition(weekly_meals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """주간 영양소 분석"""
    total_nutrition = {
        "calories": 0,
        "protein": 0,
        "carbs": 0,
        "fat": 0
    }
    
    for meal in weekly_meals:
        # 이미 저장된 영양소 정보 사용
        total_nutrition["calories"] += float(meal.get("calories", 0))
        total_nutrition["protein"] += float(meal.get("protein", 0))
        total_nutrition["carbs"] += float(meal.get("carbs", 0))
        total_nutrition["fat"] += float(meal.get("fat", 0))
    
    # 일일 평균 계산
    days = min(7, len(weekly_meals) or 1)
    for nutrient in total_nutrition:
        total_nutrition[nutrient] = round(total_nutrition[nutrient] / days, 2)
    
    return total_nutrition

def recommend_foods(user_id: int) -> Dict[str, Any]:
    """사용자의 식사 기록을 분석하여 식품 추천"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # 오늘의 식사 기록 조회
        cur.execute("""
            SELECT * FROM meal_records 
            WHERE user_id = %s 
            AND DATE(created_at) = CURRENT_DATE
            ORDER BY created_at
        """, (user_id,))
        today_meals = cur.fetchall()
        
        # 주간 식사 기록 조회
        cur.execute("""
            SELECT 
                m.id, 
                m.user_id, 
                m.meal_type, 
                m.meal_date, 
                m.meal_time, 
                m.food_name, 
                m.portion,
                m.unit,
                m.calories,
                m.protein,
                m.carbs,
                m.fat
            FROM meal_records m
            WHERE m.user_id = %s
            AND m.meal_date >= CURRENT_DATE - INTERVAL '7 days'
            ORDER BY m.meal_date DESC, m.meal_time DESC;
        """, (user_id,))
        weekly_meals = cur.fetchall()
        
        # 사용자 정보 조회
        user_info = get_user_info(user_id)
        
        # 오늘의 영양소 합계 계산
        today_nutrition = {
            "calories": 0,
            "protein": 0,
            "carbs": 0,
            "fat": 0
        }
        
        for meal in today_meals:
            today_nutrition["calories"] += float(meal.get("calories", 0))
            today_nutrition["protein"] += float(meal.get("protein", 0))
            today_nutrition["carbs"] += float(meal.get("carbs", 0))
            today_nutrition["fat"] += float(meal.get("fat", 0))
        
        # 주간 평균 영양소 계산
        weekly_nutrition = analyze_weekly_nutrition(weekly_meals)
        
        # 영양소 목표 설정 (사용자 정보 기반)
        nutrition_goals = {
            "calories": 2000,  # 기본값
            "protein": 100,    # 기본값
            "carbs": 250,      # 기본값
            "fat": 70          # 기본값
        }
        
        if user_info:
            # 사용자 정보에 따라 목표 조정
            weight = float(user_info.get("weight", 70))
            activity_level = user_info.get("activity_level", "보통")
            
            # 활동 수준에 따른 칼로리 조정
            if activity_level == "낮음":
                nutrition_goals["calories"] = weight * 25
            elif activity_level == "보통":
                nutrition_goals["calories"] = weight * 30
            elif activity_level == "높음":
                nutrition_goals["calories"] = weight * 35
            
            # 단백질 목표 (체중 1kg당 1.5g)
            nutrition_goals["protein"] = weight * 1.5
            
            # 탄수화물 목표 (총 칼로리의 50%)
            nutrition_goals["carbs"] = (nutrition_goals["calories"] * 0.5) / 4
            
            # 지방 목표 (총 칼로리의 25%)
            nutrition_goals["fat"] = (nutrition_goals["calories"] * 0.25) / 9
        
        # 영양소 부족 분석
        nutrition_deficit = {
            "calories": max(0, nutrition_goals["calories"] - today_nutrition["calories"]),
            "protein": max(0, nutrition_goals["protein"] - today_nutrition["protein"]),
            "carbs": max(0, nutrition_goals["carbs"] - today_nutrition["carbs"]),
            "fat": max(0, nutrition_goals["fat"] - today_nutrition["fat"])
        }
        
        # 식품 추천
        recommended_foods = []
        
        # 단백질 부족 시 고단백 식품 추천
        if nutrition_deficit["protein"] > 10:
            cur.execute("""
                SELECT * FROM food_nutrition 
                WHERE protein > 15 
                ORDER BY protein DESC 
                LIMIT 5
            """)
            protein_foods = cur.fetchall()
            recommended_foods.extend([{"type": "protein", "foods": protein_foods}])
        
        # 탄수화물 부족 시 탄수화물 식품 추천
        if nutrition_deficit["carbs"] > 20:
            cur.execute("""
                SELECT * FROM food_nutrition 
                WHERE carbs > 20 
                ORDER BY carbs DESC 
                LIMIT 5
            """)
            carb_foods = cur.fetchall()
            recommended_foods.extend([{"type": "carbs", "foods": carb_foods}])
        
        # 지방 부족 시 지방 식품 추천
        if nutrition_deficit["fat"] > 5:
            cur.execute("""
                SELECT * FROM food_nutrition 
                WHERE fat > 10 
                ORDER BY fat DESC 
                LIMIT 5
            """)
            fat_foods = cur.fetchall()
            recommended_foods.extend([{"type": "fat", "foods": fat_foods}])
        
        # 칼로리 부족 시 고칼로리 식품 추천
        if nutrition_deficit["calories"] > 200:
            cur.execute("""
                SELECT * FROM food_nutrition 
                WHERE calories > 200 
                ORDER BY calories DESC 
                LIMIT 5
            """)
            calorie_foods = cur.fetchall()
            recommended_foods.extend([{"type": "calories", "foods": calorie_foods}])
        
        # 결과 반환
        return {
            "today_nutrition": today_nutrition,
            "weekly_nutrition": weekly_nutrition,
            "nutrition_goals": nutrition_goals,
            "nutrition_deficit": nutrition_deficit,
            "recommended_foods": recommended_foods
        }
    finally:
        cur.close()
        conn.close()


 

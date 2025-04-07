from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage
from langchain.prompts import ChatPromptTemplate
from agents.food.common.db import (
    get_user_info,
    get_user_preferences_db,
    get_weekly_meals,
    analyze_weekly_nutrition,
    get_diet_plan
)
import json
from dataclasses import dataclass
from pydantic import BaseModel, ConfigDict
from datetime import datetime
import re

class UserInfoModel(BaseModel):
    """사용자 정보 모델"""
    model_config = ConfigDict(validate_by_name=True)
    
    member_id: int
    name: str
    gender: str
    age: int
    height: float
    weight: float
    goal: str
    activity_level: str
    allergies: List[str]
    dietary_preference: str
    meal_pattern: str
    meal_times: List[str]
    food_preferences: List[str]
    special_requirements: List[str]

class UserPreferencesModel(BaseModel):
    """사용자 선호도 모델"""
    model_config = ConfigDict(validate_by_name=True)
    
    allergies: List[str]
    dietary_preference: str
    meal_pattern: str
    meal_times: List[str]
    food_preferences: List[str]
    special_requirements: List[str]

@dataclass
class UserInfo:
    """사용자 정보 데이터 클래스"""
    gender: str
    age: int
    height: float
    weight: float
    activity_level: str
    goal: str

@dataclass
class UserPreferences:
    """사용자 선호도 데이터 클래스"""
    allergies: List[str]
    dietary_preference: str
    meal_pattern: str
    meal_times: List[str]
    food_preferences: List[str]
    special_requirements: List[str]

class BalancedMealAgent:
    """균형 잡힌 식사 추천 에이전트"""
    
    DEFAULT_MODEL = "gpt-4o-mini"
    
    def __init__(self, model_name: str = DEFAULT_MODEL):
        """에이전트 초기화"""
        self.model_name = self._validate_model_name(model_name)
        self.llm = self._initialize_llm()
        self.prompts = self._initialize_prompts()
    
    def _validate_model_name(self, model_name: str) -> str:
        """모델 이름 유효성 검사"""
        return model_name if model_name and isinstance(model_name, str) else self.DEFAULT_MODEL
    
    def _initialize_llm(self) -> ChatOpenAI:
        """LLM 초기화"""
        return ChatOpenAI(
            model=self.model_name,
            temperature=0.7
        )
    
    def _initialize_prompts(self) -> Dict[str, ChatPromptTemplate]:
        """프롬프트 초기화"""
        return {
            "goal_conversion": ChatPromptTemplate.from_messages([
                ("system", """당신은 영양 전문가입니다. 사용자의 목표를 분석하여 가장 적합한 식단 유형을 선택해주세요.
                다음 중 하나를 선택해주세요:
                - 다이어트 식단
                - 벌크업 식단
                - 체력 증진 식단
                - 유지/균형 식단
                - 고단백/저탄수화물 식단
                - 고탄수/고단백 식단
                
                JSON 형식으로 응답해주세요:
                {"diet_type": "선택한 식단 유형"}"""),
                ("human", """사용자 정보:
                성별: {gender}
                나이: {age}
                키: {height}cm
                체중: {weight}kg
                활동 수준: {activity_level}
                목표: {goal}""")
            ]),
            "recommendation": ChatPromptTemplate.from_messages([
                ("system", """당신은 영양 전문가입니다. 사용자의 정보와 선호도를 기반으로 균형 잡힌 식단을 추천해주세요.
                다음 형식의 JSON으로 응답해주세요. 들여쓰기나 줄바꿈 없이 한 줄로 작성해주세요.
                반드시 다음 필드들을 포함해야 합니다:
                - breakfast: 아침 식사 정보
                - lunch: 점심 식사 정보
                - dinner: 저녁 식사 정보
                - total_nutrition: 하루 총 영양 정보
                
                각 식사는 다음 정보를 포함해야 합니다:
                - meal: 식사 메뉴
                - comment: 식사 설명
                - nutrition: 영양 정보 (calories, protein, carbs, fat)
                
                total_nutrition은 아침, 점심, 저녁 식사의 영양 정보를 합산한 값이어야 합니다.
                
                예시:
                {"breakfast":{"meal":"아침 식사 메뉴","comment":"아침 식사에 대한 설명과 이점","nutrition":{"calories":0,"protein":0,"carbs":0,"fat":0}},"lunch":{"meal":"점심 식사 메뉴","comment":"점심 식사에 대한 설명과 이점","nutrition":{"calories":0,"protein":0,"carbs":0,"fat":0}},"dinner":{"meal":"저녁 식사 메뉴","comment":"저녁 식사에 대한 설명과 이점","nutrition":{"calories":0,"protein":0,"carbs":0,"fat":0}},"total_nutrition":{"calories":0,"protein":0,"carbs":0,"fat":0}}"""),
                ("human", """사용자 정보:
                성별: {gender}
                나이: {age}
                키: {height}cm
                체중: {weight}kg
                활동 수준: {activity_level}
                목표: {goal}
                식단 유형: {diet_type}
                
                선호도:
                알레르기: {allergies}
                식사 선호도: {dietary_preference}
                식사 패턴: {meal_pattern}
                식사 시간: {meal_times}
                식품 선호도: {food_preferences}
                특별 요구사항: {special_requirements}
                
                주간 영양소 분석:
                {nutrition_info}
                
                추천 식단 계획:
                {diet_plan}""")
            ])
        }
    
    def _convert_goal_to_diet_type(self, goal: str, user_info: UserInfo) -> str:
        """목표를 diet_type으로 변환"""
        try:
            # 기본 매핑 사용
            goal_mapping = {
                "체중 감량": "다이어트 식단",
                "체중 증가": "벌크업 식단",
                "체력 증진": "체력 증진 식단",
                "체중 유지": "유지/균형 식단",
                "근육 증가": "고단백/저탄수화물 식단",
                "운동 성능 향상": "고탄수/고단백 식단",
                "다이어트": "다이어트 식단"
            }
            
            print("🔄 목표 변환 시작:")
            print(f"- 입력된 목표: {goal}")
            
            # 기본 매핑에서 찾기
            diet_type = goal_mapping.get(goal, "유지/균형 식단")
            print(f"🎯 최종 diet_type: {diet_type}")
            return diet_type
            
        except Exception as e:
            print(f"❌ 목표 변환 중 오류 발생: {str(e)}")
            return "유지/균형 식단"
    
    def _get_diet_plan(self, diet_type: str, gender: str) -> Optional[Dict[str, Any]]:
        """목표에 맞는 식단 계획 조회"""
        try:
            # DB에서 식단 계획 조회
            plan = get_diet_plan(diet_type, gender)
            
            if plan:
                # DB에서 가져온 계획을 그대로 사용
                return plan
            else:
                print(f"식단 계획을 찾을 수 없습니다. diet_type: {diet_type}, gender: {gender}")
                return None
                
        except Exception as e:
            print(f"식단 계획 조회 중 오류 발생: {e}")
            return None
    
    def _create_user_info(self, data: Dict[str, Any]) -> UserInfo:
        """사용자 정보 생성"""
        try:
            # birth에서 age 계산
            if "birth" in data:
                birth_date = data["birth"]
                if isinstance(birth_date, str):
                    birth_date = datetime.strptime(birth_date, "%Y-%m-%d")
                today = datetime.now()
                age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                data["age"] = age
                del data["birth"]
            
            model = UserInfoModel(**data)
            # UserInfo 클래스에 필요한 필드만 전달
            user_info_data = {
                "gender": model.gender,
                "age": model.age,
                "height": model.height,
                "weight": model.weight,
                "activity_level": model.activity_level,
                "goal": model.goal
            }
            return UserInfo(**user_info_data)
        except Exception as e:
            print(f"사용자 정보 생성 중 오류 발생: {e}")
            raise
    
    def _create_user_preferences(self, preferences: Dict[str, Any]) -> UserPreferences:
        """사용자 선호도 생성"""
        # 문자열로 들어온 경우 리스트로 변환
        if isinstance(preferences.get("allergies"), str):
            preferences["allergies"] = [preferences["allergies"]]
        if isinstance(preferences.get("meal_times"), str):
            preferences["meal_times"] = [preferences["meal_times"]]
        if isinstance(preferences.get("food_preferences"), str):
            preferences["food_preferences"] = [preferences["food_preferences"]]
        if isinstance(preferences.get("special_requirements"), str):
            preferences["special_requirements"] = [preferences["special_requirements"]]
            
        model = UserPreferencesModel(**preferences)
        return UserPreferences(
            allergies=model.allergies,
            dietary_preference=model.dietary_preference,
            meal_pattern=model.meal_pattern,
            meal_times=model.meal_times,
            food_preferences=model.food_preferences,
            special_requirements=model.special_requirements
        )
    
    def _create_nutrition_prompt(self, nutrition_info: Dict[str, Any]) -> str:
        """영양소 정보 프롬프트 생성"""
        if not nutrition_info:
            return "영양소 정보가 없습니다."
        
        return f"""주간 평균 영양소 섭취량:
        칼로리: {nutrition_info.get('calories', 0)}kcal
        단백질: {nutrition_info.get('protein', 0)}g
        탄수화물: {nutrition_info.get('carbs', 0)}g
        지방: {nutrition_info.get('fat', 0)}g"""
    
    def _parse_recommendations(self, response: AIMessage) -> Dict[str, Any]:
        """추천 결과 파싱"""
        try:
            print("\n🔄 추천 결과 파싱 시작:")
            # print(f"📥 원본 응답: {response.content}")
            
            # 기본 추천 반환
            return self._get_default_recommendations()
            
        except Exception as e:
            print(f"❌ 추천 결과 파싱 중 오류 발생: {str(e)}")
            return self._get_default_recommendations()
    
    def _format_meal_recommendation(self, data: Dict[str, Any]) -> str:
        """식단 추천 결과를 채팅 형식으로 변환"""
        response_text = "📌 **추천 식단:**\n\n"

        # 아침 식사
        if "breakfast" in data:
            breakfast = data["breakfast"]
            response_text += "🍳 **아침 식사:**\n"
            response_text += f"{breakfast['meal']}\n"
            response_text += f"💡 {breakfast['comment']}\n"
            response_text += "🔥 영양 정보:\n"
            response_text += f"- 칼로리: {breakfast['nutrition']['calories']} kcal\n"
            response_text += f"- 단백질: {breakfast['nutrition']['protein']}g\n"
            response_text += f"- 탄수화물: {breakfast['nutrition']['carbs']}g\n"
            response_text += f"- 지방: {breakfast['nutrition']['fat']}g\n\n"

        # 점심 식사
        if "lunch" in data:
            lunch = data["lunch"]
            response_text += "🍱 **점심 식사:**\n"
            response_text += f"{lunch['meal']}\n"
            response_text += f"💡 {lunch['comment']}\n"
            response_text += "🔥 영양 정보:\n"
            response_text += f"- 칼로리: {lunch['nutrition']['calories']} kcal\n"
            response_text += f"- 단백질: {lunch['nutrition']['protein']}g\n"
            response_text += f"- 탄수화물: {lunch['nutrition']['carbs']}g\n"
            response_text += f"- 지방: {lunch['nutrition']['fat']}g\n\n"

        # 저녁 식사
        if "dinner" in data:
            dinner = data["dinner"]
            response_text += "🍽 **저녁 식사:**\n"
            response_text += f"{dinner['meal']}\n"
            response_text += f"💡 {dinner['comment']}\n"
            response_text += "🔥 영양 정보:\n"
            response_text += f"- 칼로리: {dinner['nutrition']['calories']} kcal\n"
            response_text += f"- 단백질: {dinner['nutrition']['protein']}g\n"
            response_text += f"- 탄수화물: {dinner['nutrition']['carbs']}g\n"
            response_text += f"- 지방: {dinner['nutrition']['fat']}g\n\n"

        # 하루 총 영양 정보
        if "total_nutrition" in data:
            total = data["total_nutrition"]
            response_text += "📊 **하루 총 영양 정보:**\n"
            response_text += f"- 칼로리: {total['calories']} kcal\n"
            response_text += f"- 단백질: {total['protein']}g\n"
            response_text += f"- 탄수화물: {total['carbs']}g\n"
            response_text += f"- 지방: {total['fat']}g\n"

        return response_text

    def _get_default_recommendations(self) -> Dict[str, Any]:
        """기본 추천 결과 제공"""
        return {
            "breakfast": {
                "meal": "오트밀과 과일",
                "comment": "아침에 필요한 에너지와 영양소를 제공하는 건강한 아침 식사입니다.",
                "nutrition": {
                    "calories": 350,
                    "protein": 12,
                    "carbs": 45,
                    "fat": 8
                }
            },
            "lunch": {
                "meal": "잡곡밥, 미역국, 구운 생선, 나물",
                "comment": "한국식 전통 식사로 균형 잡힌 영양을 제공합니다.",
                "nutrition": {
                    "calories": 550,
                    "protein": 25,
                    "carbs": 65,
                    "fat": 15
                }
            },
            "dinner": {
                "meal": "채소 위주의 샐러드와 닭가슴살",
                "comment": "가벼운 저녁 식사로 소화가 잘되고 건강에 좋습니다.",
                "nutrition": {
                    "calories": 400,
                    "protein": 30,
                    "carbs": 35,
                    "fat": 12
                }
            },
            "total_nutrition": {
                "calories": 1300,
                "protein": 67,
                "carbs": 145,
                "fat": 35
            }
        }
    
    async def process(self, user_input: str, user_id: str) -> Dict[str, Any]:
        """사용자 입력 처리"""
        try:
            print("\n🔄 프로세스 시작:")
            print(f"- 사용자 입력: {user_input}")
            print(f"- 사용자 ID: {user_id}")
            
            # 프롬프트 초기화 확인
            self.prompts = self._initialize_prompts()
            
            # 프롬프트 확인
            if "recommendation" not in self.prompts or "goal_conversion" not in self.prompts:
                print("❌ 필수 프롬프트 누락")
                return self._get_default_recommendations()
            
            # 사용자 정보 조회
            user_data = get_user_info(int(user_id))
            if not user_data:
                print(f"❌ 사용자 정보를 찾을 수 없음: {user_id}")
                return self._get_default_recommendations()
            
            print("✅ 사용자 정보 조회 성공:", user_data)
            
            # 사용자 정보 및 선호도 생성
            try:
                user_info = self._create_user_info(user_data)
                user_preferences = self._create_user_preferences(user_data)
                
                print("✅ 사용자 정보 생성 성공:")
                print(f"- user_info: {user_info}")
                print(f"- user_preferences: {user_preferences}")
                
            except Exception as e:
                print(f"❌ 사용자 정보 생성 중 오류: {str(e)}")
                return self._get_default_recommendations()
            
            # 목표를 diet_type으로 변환
            diet_type = self._convert_goal_to_diet_type(user_info.goal, user_info)
            print(f"✅ 변환된 diet_type: {diet_type}")
            
            # 식단 계획 조회
            diet_plan = self._get_diet_plan(diet_type, user_info.gender)
            if not diet_plan:
                print("❌ 식단 계획을 찾을 수 없음")
                return self._get_default_recommendations()
            
            print("✅ 식단 계획 조회 성공:", diet_plan)
            
            # 주간 식사 기록 조회
            try:
                weekly_meals = get_weekly_meals(int(user_id))
                nutrition_info = analyze_weekly_nutrition(weekly_meals)
                nutrition_prompt = self._create_nutrition_prompt(nutrition_info)
                print("✅ 주간 식사 기록 조회 성공")
                
            except Exception as e:
                print(f"❌ 주간 식사 기록 조회 중 오류: {str(e)}")
                nutrition_prompt = "영양소 정보가 없습니다."
            
            # 기본 추천 결과 반환
            result = self._get_default_recommendations()
            formatted_response = self._format_meal_recommendation(result)
            
            return {
                "type": "food",
                "response": formatted_response,
                "data": result
            }
            
        except Exception as e:
            print(f"❌ 프로세스 실행 중 오류: {str(e)}")
            return self._get_default_recommendations()
    
    def _create_error_response(self, message: str) -> Dict[str, Any]:
        """에러 응답 생성"""
        return {
            "type": "food",
            "response": f"죄송합니다. {message}"
        }  
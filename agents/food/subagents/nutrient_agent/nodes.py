from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from pydantic.v1 import BaseModel, Field, ConfigDict
from langchain.schema import AIMessage, HumanMessage
from langchain.prompts import ChatPromptTemplate
from langchain.callbacks.manager import CallbackManager
from agents.food.common.utils import (
    analyze_meal_input,
    analyze_nutrition,
    get_user_info,
    get_weekly_meals,
    analyze_weekly_nutrition,
    get_nutrition_recommendations
)

class NutrientState(BaseModel):
    """영양 분석 상태"""
    model_config = ConfigDict(validate_by_name=True)
    user_data: Dict[str, Any]
    user_input: str
    messages: List[Dict[str, str]]
    context: Dict[str, Any]
    task: str = ""
    nutrition_data: Dict[str, Any] = {}

def analyze_input(state: Dict[str, Any]) -> Dict[str, Any]:
    """사용자 입력 분석"""
    user_input = state["user_input"]
    user_data = state["user_data"]
    
    # 입력 분석 로직
    analysis = analyze_meal_input(user_input)
    state["analysis"] = analysis
    state["task"] = "analyze_meal"
    
    return state

def check_deficiency(state: Dict[str, Any]) -> Dict[str, Any]:
    """영양소 결핍 확인"""
    user_data = state["user_data"]
    
    # 현재 영양소 상태 확인
    current_nutrition = analyze_nutrition(user_data)
    target_nutrition = user_data.get("target_nutrition", {})
    
    # 결핍 확인
    deficiencies = {}
    for nutrient, target in target_nutrition.items():
        if nutrient in current_nutrition:
            diff = target - current_nutrition[nutrient]
            if diff > 0:
                deficiencies[nutrient] = diff
    
    state["current_nutrition"] = current_nutrition
    state["target_nutrition"] = target_nutrition
    state["deficiencies"] = deficiencies
    state["task"] = "check_deficiency"
    
    return state

def recommend_foods(state: Dict[str, Any]) -> Dict[str, Any]:
    """식품 추천"""
    deficiencies = state.get("deficiencies", {})
    
    # 결핍된 영양소에 대한 식품 추천
    recommendations = {}
    for nutrient, amount in deficiencies.items():
        recommendations[nutrient] = recommend_foods(nutrient, amount)
    
    state["recommendations"] = recommendations
    state["task"] = "recommend_foods"
    
    return state

class NutrientAgent:
    def __init__(self, model_name: str = "gpt-4o-mini"):
        """영양소 분석 에이전트 초기화"""
        # model_name이 None이거나 문자열이 아닌 경우 기본값 사용
        if not model_name or not isinstance(model_name, str):
            model_name = "gpt-4o-mini"
            
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=0.7
        )
        
        self.analysis_prompt = ChatPromptTemplate.from_messages([
            ("system", """영양소 분석 결과를 해석하고 개선점을 제안하는 AI 어시스턴트입니다.
            다음 형식의 JSON으로 응답해주세요:
            {
                "analysis": "영양소 분석 결과 요약",
                "improvements": ["개선점 1", "개선점 2", ...],
                "recommendations": ["추천 1", "추천 2", ...]
            }"""),
            ("human", "{input}")
        ])
    
    async def process(self, user_input: str, user_id: str) -> Dict[str, Any]:
        """영양소 분석 처리"""
        try:
            # 사용자 정보 조회
            user_info = get_user_info(int(user_id))
            if not user_info:
                return {
                    "type": "food",
                    "response": "죄송합니다. 사용자 정보를 찾을 수 없습니다."
                }
            
            # 주간 식단 조회
            weekly_meals = get_weekly_meals(int(user_id))
            if not weekly_meals:
                return {
                    "type": "food",
                    "response": "죄송합니다. 주간 식단 기록이 없습니다."
                }
            
            # 주간 영양소 분석
            weekly_nutrition = analyze_weekly_nutrition(weekly_meals)
            
            # 영양소 추천
            nutrition_info = get_nutrition_recommendations(user_info, weekly_nutrition)
            
            # 분석 결과 생성
            prompt = f"""주간 영양소 분석 결과:
            - BMR: {nutrition_info['bmr']:.2f} kcal
            - TDEE: {nutrition_info['tdee']:.2f} kcal
            - 현재 영양소: {weekly_nutrition}
            - 목표 영양소: {nutrition_info['target_nutrition']}
            - 부족한 영양소: {nutrition_info['deficiencies']}
            """
            
            chain = self.analysis_prompt | self.llm
            response = await chain.ainvoke({"input": prompt})
            
            if not isinstance(response, AIMessage):
                return {
                    "type": "food",
                    "response": "죄송합니다. 영양소 분석에 실패했습니다."
                }
            
            analysis = response.content
            
            # 응답 생성
            response_text = f"주간 영양소 분석 결과입니다:\n\n"
            response_text += f"{analysis}\n\n"
            
            if nutrition_info["deficiencies"]:
                response_text += "부족한 영양소:\n"
                for nutrient, amount in nutrition_info["deficiencies"].items():
                    response_text += f"- {nutrient}: {amount:.2f}g\n"
                response_text += "\n추천 식품:\n"
                for nutrient, foods in nutrition_info["recommendations"].items():
                    for food in foods:
                        response_text += f"- {food['name']}\n"
            
            return {
                "type": "food",
                "response": response_text
            }
            
        except Exception as e:
            print(f"영양소 분석 중 오류 발생: {e}")
            return {
                "type": "food",
                "response": "죄송합니다. 영양소 분석 중 오류가 발생했습니다."
            }
    
    def _generate_response(self, result: Dict[str, Any]) -> str:
        """결과를 바탕으로 응답 생성"""
        task = result.get("task", "")
        
        if task == "check_deficiency":
            return self._generate_deficiency_response(result)
        elif task == "recommend_foods":
            return self._generate_recommendation_response(result)
        elif task == "analyze_meal":
            return self._generate_meal_analysis_response(result)
        elif task == "get_today_meals":
            return self._generate_today_meals_response(result)
        elif task == "get_weekly_meals":
            return self._generate_weekly_meals_response(result)
        else:
            return "죄송합니다. 요청을 처리할 수 없습니다."
    
    def _generate_deficiency_response(self, result: Dict[str, Any]) -> str:
        """영양소 결핍 분석 응답 생성"""
        response = "현재 영양소:\n"
        for nutrient, amount in result["current_nutrition"].items():
            response += f"- {nutrient}: {amount:.1f}g\n"
        
        response += "\n목표 영양소:\n"
        for nutrient, amount in result["target_nutrition"].items():
            response += f"- {nutrient}: {amount:.1f}g\n"
        
        if result["deficiencies"]:
            response += "\n부족한 영양소:\n"
            for nutrient, amount in result["deficiencies"].items():
                response += f"- {nutrient}: {amount:.1f}g\n"
            
            response += "\n추천 식품:\n"
            for nutrient, foods in result["recommendations"].items():
                response += f"\n{nutrient}가 풍부한 식품:\n"
                for food in foods:
                    response += f"- {food['name']}: {food['nutrition'][nutrient]:.1f}g/100g\n"
        
        return response
    
    def _generate_recommendation_response(self, result: Dict[str, Any]) -> str:
        """식품 추천 응답 생성"""
        response = "추천 식품:\n"
        for nutrient, foods in result["recommendations"].items():
            response += f"\n{nutrient}가 풍부한 식품:\n"
            for food in foods:
                response += f"- {food['name']}: {food['nutrition'][nutrient]:.1f}g/100g\n"
                response += "  영양소:\n"
                for nutrient, amount in food["nutrition"].items():
                    response += f"    {nutrient}: {amount:.1f}g\n"
        
        return response
    
    def _generate_meal_analysis_response(self, result: Dict[str, Any]) -> str:
        """식단 분석 응답 생성"""
        analysis = result["analysis"]
        response = f"분석된 식단:\n"
        response += f"- 식사 유형: {analysis['meal_type']}\n"
        response += f"- 식품: {', '.join(analysis['foods'])}\n"
        response += "\n영양소:\n"
        for nutrient, amount in analysis["nutrition"].items():
            response += f"- {nutrient}: {amount:.1f}g\n"
        
        return response
    
    def _generate_today_meals_response(self, result: Dict[str, Any]) -> str:
        """오늘의 식사 응답 생성"""
        meals = result["meals"]
        if not meals:
            return "오늘은 아직 식사 기록이 없습니다."
        
        response = "오늘의 식사:\n"
        for meal in meals:
            response += f"\n{meal['meal_type']}:\n"
            response += f"- 식품: {', '.join(meal['foods'])}\n"
            response += "  영양소:\n"
            for nutrient, amount in meal["nutrition"].items():
                response += f"    {nutrient}: {amount:.1f}g\n"
        
        return response
    
    def _generate_weekly_meals_response(self, result: Dict[str, Any]) -> str:
        """주간 식사 응답 생성"""
        weekly_nutrition = result["weekly_nutrition"]
        nutrition_info = result["nutrition_info"]
        
        response = "주간 영양소 분석:\n"
        response += "\n평균 영양소:\n"
        for nutrient, amount in weekly_nutrition.items():
            response += f"- {nutrient}: {amount:.1f}g\n"
        
        response += "\n목표 영양소:\n"
        for nutrient, amount in nutrition_info["target_nutrition"].items():
            response += f"- {nutrient}: {amount:.1f}g\n"
        
        if nutrition_info["deficiencies"]:
            response += "\n부족한 영양소:\n"
            for nutrient, amount in nutrition_info["deficiencies"].items():
                response += f"- {nutrient}: {amount:.1f}g\n"
            
            response += "\n추천 식품:\n"
            for nutrient, foods in nutrition_info["recommendations"].items():
                response += f"\n{nutrient}가 풍부한 식품:\n"
                for food in foods:
                    response += f"- {food['name']}: {food['nutrition'][nutrient]:.1f}g/100g\n"
        
        return response 
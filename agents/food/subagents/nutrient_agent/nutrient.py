from typing import Dict, Any
from langchain_openai import ChatOpenAI

from agents.food.subagents.meal_input_agent.nodes import create_workflow
from .utils import analyze_nutrition, recommend_foods

class NutrientAgent:
    def __init__(self):
        """영양소 분석 에이전트 초기화"""
        self.llm = ChatOpenAI(model="gpt-4o-mini")
        self.workflow = create_workflow()
    
    def process(self, user_info: Dict[str, Any], message: str) -> Dict[str, Any]:
        """영양소 분석 처리"""
        try:
            # 초기 상태 생성
            initial_state = {
                "user_data": user_info,
                "user_input": message,
                "messages": [],
                "context": {}
            }
            
            # 워크플로우 실행
            result = self.workflow.run(initial_state)
            
            # 결과에 메시지 추가
            result["messages"].append({
                "role": "user",
                "content": message
            })
            
            # 응답 생성
            response = self._generate_response(result)
            result["messages"].append({
                "role": "assistant",
                "content": response
            })
            
            return result
            
        except Exception as e:
            print(f"영양소 분석 처리 중 오류 발생: {e}")
            return {
                "error": str(e),
                "messages": [{
                    "role": "assistant",
                    "content": "죄송합니다. 영양소 분석 처리 중 오류가 발생했습니다."
                }]
            }
    
    def _generate_response(self, result: Dict[str, Any]) -> str:
        """결과를 바탕으로 응답 생성"""
        task = result.get("task", "")
        
        if task == "check_deficiency":
            return self._generate_deficiency_response(result)
        elif task == "recommend_foods":
            return self._generate_recommendation_response(result)
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
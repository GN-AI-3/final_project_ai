from typing import Dict, Any, List, Optional, TypedDict
from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage
from langchain.prompts import ChatPromptTemplate
from agents.food.common.db import save_meal_record, get_today_meals, get_weekly_meals, recommend_foods
from agents.food.common.tools import FoodSearchTool
from langgraph.graph import Graph, StateGraph
import json
from dataclasses import dataclass
from pydantic import BaseModel, Field
import re
from datetime import datetime

class MealItemModel(BaseModel):
    """식사 항목 모델"""
    name: str
    portion: float
    unit: str
    calories: float
    protein: float
    carbs: float
    fat: float

    class Config:
        validate_assignment = True

@dataclass
class MealItem:
    """식사 항목 데이터 클래스"""
    name: str
    portion: float
    unit: str
    calories: float
    protein: float
    carbs: float
    fat: float

class AgentState(TypedDict):
    """에이전트 상태"""
    user_id: str
    meal_type: str
    food_input: str
    meal_items: List[Dict[str, Any]]
    total_nutrition: Dict[str, float]
    nutrition_analysis: Dict[str, Any]
    food_recommendations: List[Dict[str, Any]]
    food_info: Optional[Dict[str, Any]]
    error: Optional[str]

class MealInputAgent:
    """식사 입력 에이전트"""
    
    DEFAULT_MODEL = "gpt-4o-mini"
    DEFAULT_PORTION_SIZE = 100  # 기본 1인분 크기 (그램)
    
    def __init__(self, model_name: str = DEFAULT_MODEL):
        """에이전트 초기화"""
        self.model_name = self._validate_model_name(model_name)
        self.llm = self._initialize_llm()
        self.prompts = self._initialize_prompts()
        self.search_tool = FoodSearchTool()
        self.workflow = self._create_workflow()
    
    def _validate_model_name(self, model_name: str) -> str:
        """모델 이름 유효성 검사"""
        return model_name if model_name and isinstance(model_name, str) else self.DEFAULT_MODEL
    
    def _initialize_llm(self) -> ChatOpenAI:
        """LLM 초기화"""
        return ChatOpenAI(
            model=self.model_name,
            temperature=0.7
        )
    
    def _initialize_prompts(self) -> Dict[str, str]:
        """프롬프트 초기화"""
        return {
            "meal_input": """당신은 영양 전문가입니다. 사용자의 식사 입력을 분석하고 영양 정보를 제공해주세요.

    다음 형식의 JSON으로만 응답하세요 (다른 텍스트 없이):
    {{"meal_items":[{{"name":"음식 이름","portion":1,"unit":"개","calories":100,"protein":1,"carbs":25,"fat":0}}],"total_nutrition":{{"calories":100,"protein":1,"carbs":25,"fat":0}}}}

    사용자 입력: "{user_input}"
    """
        }

    def _create_workflow(self) -> Graph:
        """워크플로우 생성"""
        workflow = StateGraph(AgentState)

        # 노드 추가
        workflow.add_node("analyze_meal", self._analyze_meal)
        workflow.add_node("save_meal", self._save_meal)
        workflow.add_node("analyze_nutrition", self._analyze_nutrition)
        workflow.add_node("recommend_food", self._recommend_food)

        # 엣지 추가
        workflow.add_edge("analyze_meal", "save_meal")
        workflow.add_edge("save_meal", "analyze_nutrition")
        workflow.add_edge("analyze_nutrition", "recommend_food")

        # 시작 노드 설정
        workflow.set_entry_point("analyze_meal")

        return workflow.compile()

    async def _analyze_meal(self, state: AgentState) -> AgentState:
        """식사 분석"""
        try:
            # 웹 검색 결과가 있는 경우 활용
            if state.get("food_info"):
                food_info = state["food_info"]
                # 영양 정보 추출
                nutrition_info = food_info.get("nutrition", {})
                if nutrition_info:
                    meal_item = {
                        "name": food_info.get("name", state["food_input"]),
                        "portion": 1.0,
                        "unit": "인분",
                        "calories": nutrition_info.get("calories", 0),
                        "protein": nutrition_info.get("protein", 0),
                        "carbs": nutrition_info.get("carbs", 0),
                        "fat": nutrition_info.get("fat", 0)
                    }
                    state["meal_items"] = [meal_item]
                    return state

            # LLM을 사용한 분석
            prompt = ChatPromptTemplate.from_messages([
                ("system", "식사 정보를 분석하여 영양 정보를 추출하세요."),
                ("human", "{input}")
            ])
            
            chain = prompt | self.llm
            
            response = await chain.ainvoke({"input": state["food_input"]})
            
            # 응답 파싱
            try:
                result = json.loads(response.content)
                state["meal_items"] = result.get("meal_items", [])
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 기본값 사용
                state["meal_items"] = [self._create_default_meal_item(state["food_input"])]
            
            return state
            
        except Exception as e:
            state["error"] = f"식사 분석 중 오류 발생: {str(e)}"
            return state

    async def _save_meal(self, state: AgentState) -> AgentState:
        """식사 기록 저장"""
        try:
            for item in state["meal_items"]:
                save_meal_record(
                    user_id=int(state["user_id"]),
                    meal_type=state["meal_type"],
                    food_name=item["name"],
                    portion=item["portion"],
                    unit=item["unit"],
                    calories=item["calories"],
                    protein=item["protein"],
                    carbs=item["carbs"],
                    fat=item["fat"]
                )
            return state
        except Exception as e:
            state["error"] = f"식사 기록 저장 중 오류 발생: {str(e)}"
            return state

    async def _analyze_nutrition(self, state: AgentState) -> AgentState:
        """영양소 분석"""
        try:
            today_meals = get_today_meals(int(state["user_id"]))
            weekly_meals = get_weekly_meals(int(state["user_id"]))
            
            # 오늘의 총 영양소 계산
            today_total = {
                "calories": sum(float(meal["calories"]) for meal in today_meals),
                "protein": sum(float(meal["protein"]) for meal in today_meals),
                "carbs": sum(float(meal["carbs"]) for meal in today_meals),
                "fat": sum(float(meal["fat"]) for meal in today_meals)
            }
            
            # 주간 평균 영양소 계산
            weekly_total = {
                "calories": sum(float(meal["calories"]) for meal in weekly_meals) / 7,
                "protein": sum(float(meal["protein"]) for meal in weekly_meals) / 7,
                "carbs": sum(float(meal["carbs"]) for meal in weekly_meals) / 7,
                "fat": sum(float(meal["fat"]) for meal in weekly_meals) / 7
            }
            
            # 영양소 분석 결과 저장
            state["nutrition_analysis"] = {
                "today_total": today_total,
                "weekly_average": weekly_total,
                "deficits": {
                    "protein": max(0, weekly_total["protein"] - today_total["protein"]),
                    "carbs": max(0, weekly_total["carbs"] - today_total["carbs"]),
                    "fat": max(0, weekly_total["fat"] - today_total["fat"])
                }
            }
            
            return state
        except Exception as e:
            state["error"] = f"영양소 분석 중 오류 발생: {str(e)}"
            return state

    async def _recommend_food(self, state: AgentState) -> AgentState:
        """보완 식품 추천"""
        try:
            recommendations = recommend_foods(int(state["user_id"]))
            state["food_recommendations"] = recommendations
            return state
        except Exception as e:
            state["error"] = f"보완 식품 추천 중 오류 발생: {str(e)}"
            return state

    async def process(self, user_input: str, user_id: str, meal_type: str, food_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """사용자 입력 처리"""
        try:
            # 초기 상태 설정
            initial_state: AgentState = {
                "user_id": user_id,
                "meal_type": meal_type,
                "food_input": user_input,
                "meal_items": [],
                "total_nutrition": {},
                "nutrition_analysis": {},
                "food_recommendations": [],
                "food_info": food_info,
                "error": None
            }
            
            # 워크플로우 실행
            final_state = await self.workflow.ainvoke(initial_state)
            
            if final_state["error"]:
                return self._create_error_response(final_state["error"])
            
            return {
                "type": "food",
                "response": {
                    "meal_items": final_state["meal_items"],
                    "total_nutrition": final_state["total_nutrition"],
                    "nutrition_analysis": final_state["nutrition_analysis"],
                    "food_recommendations": final_state["food_recommendations"],
                    "food_info": final_state.get("food_info")
                }
            }
            
        except Exception as e:
            return self._create_error_response(f"처리 중 오류 발생: {str(e)}")

    def _convert_portion(self, portion_str: str) -> float:
        """포션 문자열을 그램으로 변환"""
        try:
            # 숫자만 추출
            number = float(''.join(filter(str.isdigit, portion_str)))
            
            # 단위에 따른 변환
            if "개" in portion_str:
                return number * self.DEFAULT_PORTION_SIZE
            elif "그램" in portion_str or "g" in portion_str:
                return number
            else:
                return self.DEFAULT_PORTION_SIZE
        except (ValueError, TypeError):
            return self.DEFAULT_PORTION_SIZE
    
    def _create_meal_item(self, item_data: Dict[str, Any]) -> MealItem:
        """식사 항목 생성"""
        try:
            print(f"식사 항목 생성 시작: {item_data}")  # 디버깅용 로그 추가
            
            # 필수 필드 검증
            required_fields = ["name", "portion", "unit", "calories", "protein", "carbs", "fat"]
            for field in required_fields:
                if field not in item_data:
                    print(f"필수 필드 '{field}'가 없습니다. 기본값을 사용합니다.")
                    if field == "name":
                        item_data[field] = "기본 식사"
                    elif field == "portion":
                        item_data[field] = 1.0
                    elif field == "unit":
                        item_data[field] = "개"
                    elif field in ["calories", "protein", "carbs", "fat"]:
                        item_data[field] = 0.0
            
            # 숫자 필드 검증
            numeric_fields = ["portion", "calories", "protein", "carbs", "fat"]
            for field in numeric_fields:
                if not isinstance(item_data[field], (int, float)):
                    print(f"숫자 필드 '{field}'가 숫자가 아닙니다. 기본값을 사용합니다.")
                    item_data[field] = 0.0
            
            # Pydantic 모델 검증
            model = MealItemModel(**item_data)
            
            # MealItem 객체 생성
            meal_item = MealItem(
                name=model.name,
                portion=model.portion,
                unit=model.unit,
                calories=model.calories,
                protein=model.protein,
                carbs=model.carbs,
                fat=model.fat
            )
            
            print(f"생성된 식사 항목: {meal_item}")  # 디버깅용 로그 추가
            return meal_item
            
        except Exception as e:
            print(f"식사 항목 생성 중 오류 발생: {e}")
            import traceback
            print(f"오류 스택 트레이스: {traceback.format_exc()}")  # 스택 트레이스 출력
            # 오류 발생 시 기본 MealItem 객체 생성
            return MealItem(
                name="기본 식사",
                portion=1.0,
                unit="개",
                calories=300.0,
                protein=10.0,
                carbs=40.0,
                fat=8.0
            )
    
    def _create_success_response(self, meal_items: List[MealItem], total_nutrition: Dict[str, float]) -> Dict[str, Any]:
        """성공 응답 생성"""
        try:
            # meal_items가 비어있는 경우 기본값 생성
            if not meal_items:
                print("meal_items가 비어있습니다. 기본 식사 항목을 생성합니다.")
                meal_items = [self._create_meal_item({
                    "name": "기본 식사",
                    "portion": 1,
                    "unit": "인분",
                    "calories": 300,
                    "protein": 10,
                    "carbs": 40,
                    "fat": 8
                })]
            
            # total_nutrition이 비어있는 경우 계산
            if not total_nutrition:
                print("total_nutrition이 비어있습니다. 계산하여 생성합니다.")
                total_calories = 0
                total_protein = 0
                total_carbs = 0
                total_fat = 0
                
                for item in meal_items:
                    total_calories += item.calories
                    total_protein += item.protein
                    total_carbs += item.carbs
                    total_fat += item.fat
                
                total_nutrition = {
                    "calories": total_calories,
                    "protein": total_protein,
                    "carbs": total_carbs,
                    "fat": total_fat
                }
            
            # 응답 생성
            response = {
                "type": "food",
                "response": {
                    "meal_items": [
                        {
                            "name": item.name,
                            "portion": item.portion,
                            "unit": item.unit,
                            "calories": item.calories,
                            "protein": item.protein,
                            "carbs": item.carbs,
                            "fat": item.fat
                        }
                        for item in meal_items
                    ],
                    "total_nutrition": total_nutrition
                }
            }
            
            print(f"생성된 응답: {response}")  # 디버깅용 로그 추가
            return response
            
        except Exception as e:
            print(f"성공 응답 생성 중 오류 발생: {e}")
            import traceback
            print(f"오류 스택 트레이스: {traceback.format_exc()}")  # 스택 트레이스 출력
            # 오류 발생 시 기본 응답 생성
            return {
                "type": "food",
                "response": {
                    "meal_items": [
                        {
                            "name": "기본 식사",
                            "portion": 1,
                            "unit": "인분",
                            "calories": 300,
                            "protein": 10,
                            "carbs": 40,
                            "fat": 8
                        }
                    ],
                    "total_nutrition": {
                        "calories": 300,
                        "protein": 10,
                        "carbs": 40,
                        "fat": 8
                    }
                }
            }
    
    def _create_error_response(self, message: str) -> Dict[str, Any]:
        """에러 응답 생성"""
        return {
            "type": "food",
            "response": f"죄송합니다. {message}"
        }
    
    def _parse_meal_data(self, response_content: str) -> Dict[str, Any]:
        """식사 데이터 파싱"""
        try:
            # print(f"원본 응답: {response_content}")  # 디버깅용 로그 추가
            
            # JSON 부분만 추출
            start_idx = response_content.find('{')
            end_idx = response_content.rfind('}') + 1
            if start_idx == -1 or end_idx == 0:
                print("JSON 형식이 올바르지 않습니다. 기본 식사 항목을 제공합니다.")
                return self._get_default_meal_data()
            
            json_str = response_content[start_idx:end_idx]
            # print(f"추출된 JSON 문자열: {json_str}")  # 디버깅용 로그 추가
            
            # JSON 문자열 정리
            # 1. 줄바꿈과 공백 제거
            json_str = json_str.replace('\n', '')
            # 2. 불필요한 공백 제거
            json_str = ' '.join(json_str.split())
            
            # 3. 이중 따옴표 문제 해결
            # 이중 따옴표로 감싸진 키 이름을 단일 따옴표로 변경
            # \"key\" 패턴을 "key"로 변경
            json_str = re.sub(r'\\"([^"]+)\\"', r'"\1"', json_str)
            
            # 4. 숫자 값이 문자열로 감싸진 경우 처리
            json_str = re.sub(r':\s*"(\d+(\.\d+)?)"', r':\1', json_str)
            
            # 5. 백틱(`) 문자 제거
            json_str = json_str.replace('`', '')
            
            # 6. 코드 블록 마커 제거
            json_str = re.sub(r'```json\s*', '', json_str)
            json_str = re.sub(r'\s*```', '', json_str)
            
            # 7. 들여쓰기 문제 해결
            json_str = re.sub(r'\s+', ' ', json_str)
            
            # 8. 중괄호와 콤마 주변의 공백 제거
            json_str = re.sub(r'\s*{\s*', '{', json_str)
            json_str = re.sub(r'\s*}\s*', '}', json_str)
            json_str = re.sub(r'\s*,\s*', ',', json_str)
            
            # 9. 모든 공백 제거 (마지막 시도)
            json_str = ''.join(json_str.split())
            
            # print(f"정리된 JSON 문자열: {json_str}")  # 디버깅용 로그 추가
            
            try:
                data = json.loads(json_str)
                # print(f"첫 번째 JSON 파싱 성공: {data}")  # 디버깅용 로그 추가
            except json.JSONDecodeError as e:
                print(f"첫 번째 JSON 파싱 시도 실패: {e}")
                print(f"오류 위치: {e.pos}, 오류 메시지: {e.msg}")  # 오류 위치와 메시지 출력
                # 첫 번째 시도 실패 시 더 적극적인 정리
                # 모든 공백 제거
                json_str = ''.join(json_str.split())
                # 이중 따옴표 문제 해결 시도
                json_str = re.sub(r'\\"([^"]+)\\"', r'"\1"', json_str)
                # 숫자 값이 문자열로 감싸진 경우 처리
                json_str = re.sub(r':\s*"(\d+(\.\d+)?)"', r':\1', json_str)
                # 백틱(`) 문자 제거
                json_str = json_str.replace('`', '')
                # 코드 블록 마커 제거
                json_str = re.sub(r'```json\s*', '', json_str)
                json_str = re.sub(r'\s*```', '', json_str)
                
                print(f"두 번째 시도 전 JSON 문자열: {json_str}")  # 디버깅용 로그 추가
                
                try:
                    data = json.loads(json_str)
                    print(f"두 번째 JSON 파싱 성공: {data}")  # 디버깅용 로그 추가
                except json.JSONDecodeError as e:
                    print(f"두 번째 JSON 파싱 시도 실패: {e}")
                    print(f"오류 위치: {e.pos}, 오류 메시지: {e.msg}")  # 오류 위치와 메시지 출력
                    # 두 번째 시도도 실패하면 기본 식사 데이터 제공
                    return self._get_default_meal_data()
            
            # 필수 필드 검증
            if "meal_items" not in data:
                print("meal_items 필드가 없습니다. 기본 식사 항목을 제공합니다.")
                return self._get_default_meal_data()
            
            # meal_items가 리스트가 아닌 경우 처리
            if not isinstance(data["meal_items"], list):
                print("meal_items가 리스트가 아닙니다. 기본 식사 항목을 제공합니다.")
                return self._get_default_meal_data()
            
            # total_nutrition 필드가 없는 경우 생성
            if "total_nutrition" not in data:
                print("total_nutrition 필드가 없습니다. 계산하여 추가합니다.")
                total_calories = 0
                total_protein = 0
                total_carbs = 0
                total_fat = 0
                
                for item in data["meal_items"]:
                    total_calories += item.get("calories", 0)
                    total_protein += item.get("protein", 0)
                    total_carbs += item.get("carbs", 0)
                    total_fat += item.get("fat", 0)
                
                data["total_nutrition"] = {
                    "calories": total_calories,
                    "protein": total_protein,
                    "carbs": total_carbs,
                    "fat": total_fat
                }
            
            return data
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 오류: {e}")
            print(f"오류 위치: {e.pos}, 오류 메시지: {e.msg}")  # 오류 위치와 메시지 출력
            return self._get_default_meal_data()
        except Exception as e:
            print(f"데이터 파싱 오류: {e}")
            import traceback
            print(f"오류 스택 트레이스: {traceback.format_exc()}")  # 스택 트레이스 출력
            return self._get_default_meal_data()
    
    def _get_default_meal_data(self) -> Dict[str, Any]:
        """기본 식사 데이터 제공"""
        return {
            "meal_items": [
                {
                    "name": "기본 식사",
                    "portion": 1,
                    "unit": "인분",
                    "calories": 300,
                    "protein": 10,
                    "carbs": 40,
                    "fat": 8
                }
            ],
            "total_nutrition": {
                "calories": 300,
                "protein": 10,
                "carbs": 40,
                "fat": 8
            }
        }

    def _create_default_meal_item(self, food_name: str) -> Dict[str, Any]:
        """기본 식사 항목 생성"""
        return {
            "name": food_name,
            "portion": 1.0,
            "unit": "인분",
            "calories": 300.0,
            "protein": 10.0,
            "carbs": 40.0,
            "fat": 8.0
        }

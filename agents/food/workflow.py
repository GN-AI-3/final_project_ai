from langgraph.graph import StateGraph
from langchain_openai import ChatOpenAI
from .nodes import (
    UserState,
    nutrition_calculation_node,
    meal_planning_node,
    vector_search_node,
    self_rag_node,
    evaluate_data_node,
    bmi_calculation_node,
    nutrition_analysis_node,
    recommend_supplements_node
)
 
import os
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'

# 환경 변수 로드
load_dotenv()

def create_workflow():
    """
    워크플로우 그래프 생성 및 실행
    1. StateGraph 생성
    2. 노드 추가 및 연결
    3. Conditional Edge 설정
    4. 워크플로우 실행 및 결과 출력
    """
    # LLM 초기화
    llm = ChatOpenAI(
        model="gpt-3.5-turbo",

        temperature=0.7,
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # 워크플로우 그래프 생성
    workflow = StateGraph(UserState)
    
    # 노드 추가
    workflow.add_node("vector_search", vector_search_node)
    workflow.add_node("evaluate_data", lambda state: evaluate_data_node(state, llm))
    workflow.add_node("self_rag", lambda state: self_rag_node(state, llm))
    workflow.add_node("bmi_calculation", bmi_calculation_node)
    workflow.add_node("nutrition_calculation", nutrition_calculation_node)
    workflow.add_node("nutrition_analysis_node", lambda state: nutrition_analysis_node(state, llm))
    workflow.add_node("recommend_supplements", lambda state: recommend_supplements_node(state, llm)) 
    workflow.add_node("meal_planning", lambda state: meal_planning_node(state, llm))
    
    # 조건부 엣지 설정
    def route_by_confidence(state: UserState) -> str:
        confidence = state.get("confidence", 0.0)
        return "high_confidence" if confidence > 0.8 else "low_confidence"
    
    workflow.add_conditional_edges(
        "evaluate_data",
        route_by_confidence,
        {
            "high_confidence": "bmi_calculation",
            "low_confidence": "self_rag"
        }
    )
    
    # 일반 엣지 설정
    workflow.add_edge("vector_search", "evaluate_data")
    workflow.add_edge("self_rag", "bmi_calculation")
    workflow.add_edge("bmi_calculation", "nutrition_calculation")
    workflow.add_edge("nutrition_calculation", "nutrition_analysis_node")
    workflow.add_edge("nutrition_analysis_node", "recommend_supplements")
    workflow.add_edge("recommend_supplements", "meal_planning")
    
    # 시작 노드 설정
    workflow.set_entry_point("vector_search")
    
    return workflow.compile()
def run_workflow(initial_state: UserState):
    """
    워크플로우 실행 및 결과 출력
    """
    app = create_workflow()
    result = app.invoke(initial_state)
    
 
    
    print("\n=== 입력한 식품 정보 ===")
    for food in result.get("user_data", {}).get("target_foods", []):
        print(f"🔹 식품명: {food}")
        if food in result.get("food_info", {}):
            info = result["food_info"][food]
            print(f"🔹 영양 정보: {info}")
        else:
            print("🔹 영양 정보: 정보 없음")
    
    print("\n=== 신체 정보 ===")
    print(f"🔹 BMI: {result.get('bmi', '정보 없음'):.1f} ({result.get('bmi_status', '정보 없음')})")
    print(f"🔹 목표: {result.get('user_data', {}).get('goal', '정보 없음')}")
    
    print("\n=== 영양 분석 ===")
    nutrition_analysis = result.get("nutrition_analysis", {})
    print(f"🔹 식단 평가: {nutrition_analysis.get('evaluation', '정보 없음')}")
    print("🔹 부족한 영양소: ")
    deficient_nutrients = nutrition_analysis.get("deficient_nutrients", [])
    if deficient_nutrients:
        for nutrient in deficient_nutrients:
            print(f"  - {nutrient}")
    else:
        print("  - 부족한 영양소 정보 없음")
    
    print("\n=== 추천 보완 식품 ===")
    if "supplement_recommendations" in result:
        if result["supplement_recommendations"]:
            for food in result["supplement_recommendations"]:
                print(f"\n{food.get('name', '이름 없음')}:")
                print(f"  - 이유: {food.get('reason', '정보 없음')}")
        else:
            print("추천 보완 식품 정보가 없습니다.")
    else:
        print("추천 보완 식품 정보가 없습니다.")

    
    print("\n=== 추천 식단 ===")
    if "meal_plan" in result:
        if result["meal_plan"]:
            print(result["meal_plan"])  # LLM 응답을 텍스트 그대로 출력
        else:
            print("추천 식단 정보가 없습니다.")
    else:
        print("추천 식단 정보가 없습니다.")
    
    return result

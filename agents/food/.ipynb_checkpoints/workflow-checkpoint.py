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
from .tools import create_nutrition_report, export_to_jupyter
import os
 
import httpx
from httpx import HTTPTransport

 

def create_workflow():
    """
    워크플로우 그래프 생성 및 실행
    1. StateGraph 생성
    2. 노드 추가 및 연결
    3. Conditional Edge 설정
    4. 워크플로우 실행 및 결과 출력
    """
    # 프록시 설정
    transport = HTTPTransport(proxy="http://127.0.0.1:7890")
    client = httpx.Client(transport=transport)
    
    # LLM 설정
    llm = ChatOpenAI(
     model="gpt-4o-mini",
        temperature=0.7,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        http_client=client
    )
    
    # 워크플로우 그래프 생성
    workflow = StateGraph(UserState)
    
    # 노드 추가
    workflow.add_node("vector_search", vector_search_node)
    workflow.add_node("evaluate_data", lambda state: evaluate_data_node(state, llm))
    workflow.add_node("self_rag", lambda state: self_rag_node(state, llm))
    workflow.add_node("bmi_calculation", bmi_calculation_node)
    workflow.add_node("nutrition_calculation", nutrition_calculation_node)
    workflow.add_node("nutrition_analysis", lambda state: nutrition_analysis_node(state, llm))
    workflow.add_node("recommend_supplements", lambda state: recommend_supplements_node(state, llm))
    workflow.add_node("meal_planning", lambda state: meal_planning_node(state, llm))
    
    # Conditional Edge 설정
    def data_quality_router(state: UserState) -> str:
        if state.get("data_quality", {}).get("is_reliable", False):
            return "bmi_calculation"
        return "self_rag"
    
    # 엣지 연결
    workflow.add_edge("vector_search", "evaluate_data")
    workflow.add_conditional_edges(
        "evaluate_data",
        data_quality_router,
        {
            "bmi_calculation": "bmi_calculation",
            "self_rag": "self_rag"
        }
    )
    workflow.add_edge("self_rag", "bmi_calculation")
    workflow.add_edge("bmi_calculation", "nutrition_calculation")
    workflow.add_edge("nutrition_calculation", "nutrition_analysis")
    workflow.add_edge("nutrition_analysis", "recommend_supplements")
    workflow.add_edge("recommend_supplements", "meal_planning")
    
    # 시작 노드와 종료 노드 설정
    workflow.set_entry_point("vector_search")
    workflow.set_finish_point("meal_planning")
    
    # 그래프 컴파일
    return workflow.compile()

def run_workflow(initial_state: UserState):
    """
    워크플로우 실행 및 결과 출력
    """
    app = create_workflow()
    result = app.invoke(initial_state)
    
    # 결과 시각화
    create_nutrition_report(result)
    
    # Jupyter Notebook으로 내보내기
    export_to_jupyter(result)
    
    # 텍스트 결과 출력
    print("\n=== 입력한 식품 정보 ===")
    for food in result["user_data"]["target_foods"]:
        print(f"🔹 식품명: {food}")
        if food in result.get("food_info", {}):
            info = result["food_info"][food]
            print(f"🔹 영양 정보: {info}")
    
    print("\n=== 신체 정보 ===")
    print(f"🔹 BMI: {result['bmi']:.1f} ({result.get('bmi_status', '정보 없음')})")
    print(f"🔹 목표: {result['user_data']['goal']}")
    
    print("\n=== 영양 분석 ===")
    print(f"🔹 식단 평가: {result.get('nutrition_analysis', {}).get('evaluation', '정보 없음')}")
    print("🔹 부족한 영양소:")
    for nutrient in result.get("nutrition_analysis", {}).get("deficient_nutrients", []):
        print(f"  - {nutrient}")
    
    print("\n=== 추천 보완 식품 ===")
    for food in result.get("supplement_recommendations", []):
        print(f"🔹 {food['name']}: {food.get('reason', '')}")
    
    print("\n=== 추천 식단 ===")
    for meal in result["meal_plan"]:
        print(f"\n{meal['meal_type']}:")
        for food in meal['foods']:
            print(f"- {food['name']}: {food['amount']} (예상 칼로리: {food['calories']:.0f}kcal)")
    
    return result 
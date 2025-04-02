from langgraph.graph import StateGraph, END, START
from ..nodes.routing_node import routing
from ..models.state_models import RoutingState
from ..nodes.exercise_routine_node import exercise_routine_agent
from ..nodes.exercise_form_node import exercise_form_agent
from ..nodes.exercise_direction_node import exercise_direction_agent
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

# def generate_plan(state: WorkoutState) -> WorkoutState:
#     """회원 분석 후 초기 운동 계획 생성"""
#     user_info = state["user_info"]
#     analysis = analyze_user_info.invoke({
#         "exercise_history": user_info["exercise_history"],
#         "age": user_info["age"],
#         "weight": user_info["weight"],
#         "height": user_info["height"],
#         "injuries": user_info["injuries"],
#         "goals": user_info["goals"],
#         "available_equipment": user_info["available_equipment"],
#         "preferred_workout_time": user_info.get("preferred_workout_time", "morning"),
#         "weekly_workout_days": user_info.get("weekly_workout_days", 3)
#     })
    
#     workout_plan = generate_workout_plan.invoke({
#         "fitness_level": analysis["fitness_level"],
#         "focus_areas": analysis["focus_areas"],
#         "restrictions": analysis["restrictions"],
#         "preferred_workout_time": analysis["preferred_workout_time"],
#         "weekly_workout_days": analysis["weekly_workout_days"]
#     })
    
#     # AI 메시지 추가
#     state["messages"].append(
#         AIMessage(
#             content=f"운동 계획 생성 완료: {workout_plan['weekly_workout_days']}일/주, {workout_plan['focus_areas'][0]} 중심",
#             additional_kwargs={
#                 "tool_calls": [{
#                     "id": "plan_1",
#                     "type": "function",
#                     "function": {
#                         "name": "generate_workout_plan",
#                         "arguments": json.dumps(workout_plan, ensure_ascii=False)
#                     }
#                 }]
#             }
#         )
#     )
    
#     # Tool 응답 메시지 추가
#     state["messages"].append(
#         ToolMessage(
#             content="계획 생성 완료",
#             name="generate_workout_plan",
#             tool_call_id="plan_1"
#         )
#     )
    
#     state["workout_plan"] = workout_plan
#     state["current_step"] = "plan_generated"
#     return state

# def collect_feedback(state: WorkoutState) -> WorkoutState:
#     """사용자 피드백 수집 및 계획 조정"""
#     feedback = {
#         "too_difficult": False,
#         "too_easy": False,
#         "preferred_exercises": [],
#         "disliked_exercises": []
#     }
    
#     if feedback:
#         adjusted_plan = adjust_plan_based_on_feedback.invoke({
#             "workout_plan": state["workout_plan"],
#             "feedback": feedback
#         })
        
#         # AI 메시지 추가
#         state["messages"].append(
#             AIMessage(
#                 content="운동 계획 조정 완료",
#                 additional_kwargs={
#                     "tool_calls": [{
#                         "id": "feedback_1",
#                         "type": "function",
#                         "function": {
#                             "name": "adjust_plan_based_on_feedback",
#                             "arguments": json.dumps(adjusted_plan, ensure_ascii=False)
#                         }
#                     }]
#                 }
#             )
#         )
        
#         # Tool 응답 메시지 추가
#         state["messages"].append(
#             ToolMessage(
#                 content="계획 조정 완료",
#                 name="adjust_plan_based_on_feedback",
#                 tool_call_id="feedback_1"
#             )
#         )
        
#         state["workout_plan"] = adjusted_plan
    
#     state["feedback"] = feedback
#     state["current_step"] = "feedback_received"
#     return state

# def finalize_plan(state: WorkoutState) -> WorkoutState:
#     """최종 계획 검토 및 추천사항 제공"""
#     # 간소화된 프롬프트 사용
#     prompt = ChatPromptTemplate.from_messages([
#         ("system", "운동 계획을 검토하고 핵심 추천사항을 2-3문장으로 제공해주세요."),
#         MessagesPlaceholder(variable_name="messages"),
#         ("human", "운동 계획 검토: {workout_plan}")
#     ])
    
#     chain = prompt | llm
#     response = chain.invoke({
#         "messages": state["messages"],
#         "workout_plan": json.dumps(state["workout_plan"], indent=2, ensure_ascii=False)
#     })
    
#     state["messages"].append(response)
#     state["current_step"] = "complete"
#     return state

def create_workout_workflow():
    """운동 워크플로우 생성"""
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.7
    )

    workflow = StateGraph(RoutingState)
    
    # Add nodes
    # workflow.add_node("analyze_user_info", analyze_user_info)
    # 사용자 DB 조회 -> 사용자 정보를 토대로 키워드 추출 (타겟 근육, 운동 경력 등)
    # workflow.add_node("target_muscle", target_muscle")
    # 키워드 추출 -> 운동 추천
    # workflow.add_node("web_search", web_search)
    # 웹 검색 기반 운동 추천
    # workflow.add_node("merge_exercise", merge_exercise)
    # 웹 검색 기반 운동과 키워드 기반 운동 병합
    # workflow.add_node("judge_exercise", judge_exercise)
    # 추천 운동이 적합한지 판단

    # 노드 추가
    workflow.add_node("routing", lambda state: routing(state, llm))
    workflow.add_node("exercise_routine", lambda state: exercise_routine_agent(state, llm))
    workflow.add_node("exercise_form", lambda state: exercise_form_agent(state, llm))
    workflow.add_node("exercise_direction", lambda state: exercise_direction_agent(state, llm))    

    # 엣지 추가
    workflow.add_edge(START, "routing")
    workflow.add_conditional_edges(
        "routing", lambda state: state.category,
        {
            "운동 루틴": "exercise_routine",
            "운동 자세": "exercise_form",
            "운동 방향성": "exercise_direction"
        }
    )
    
    # # Add edges
    # workflow.add_edge(START, "generate")
    # workflow.add_edge("generate", "collect_feedback")
    # workflow.add_edge("collect_feedback", "finalize")
    # workflow.add_edge("finalize", END)
    
    return workflow.compile()
from typing import Dict, List
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
import json
from ..models.state_models import WorkoutState
from ..tools.analysis_tools import analyze_user_info
from ..tools.recommendation_tools import recommend_exercises, generate_workout_plan
from ..tools.feedback_tools import adjust_plan_based_on_feedback
from dotenv import load_dotenv

load_dotenv()

# LLM 초기화
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.7
)

def generate_plan(state: WorkoutState) -> WorkoutState:
    """회원 분석 후 초기 운동 계획 생성"""
    user_info = state["user_info"]
    analysis = analyze_user_info.invoke({
        "exercise_history": user_info["exercise_history"],
        "age": user_info["age"],
        "weight": user_info["weight"],
        "height": user_info["height"],
        "injuries": user_info["injuries"],
        "goals": user_info["goals"],
        "available_equipment": user_info["available_equipment"],
        "preferred_workout_time": user_info.get("preferred_workout_time", "morning"),
        "weekly_workout_days": user_info.get("weekly_workout_days", 3)
    })
    
    workout_plan = generate_workout_plan.invoke({
        "fitness_level": analysis["fitness_level"],
        "focus_areas": analysis["focus_areas"],
        "restrictions": analysis["restrictions"],
        "preferred_workout_time": analysis["preferred_workout_time"],
        "weekly_workout_days": analysis["weekly_workout_days"]
    })
    
    # AI 메시지 추가
    state["messages"].append(
        AIMessage(
            content=f"운동 계획 생성 완료: {workout_plan['weekly_workout_days']}일/주, {workout_plan['focus_areas'][0]} 중심",
            additional_kwargs={
                "tool_calls": [{
                    "id": "plan_1",
                    "type": "function",
                    "function": {
                        "name": "generate_workout_plan",
                        "arguments": json.dumps(workout_plan, ensure_ascii=False)
                    }
                }]
            }
        )
    )
    
    # Tool 응답 메시지 추가
    state["messages"].append(
        ToolMessage(
            content="계획 생성 완료",
            name="generate_workout_plan",
            tool_call_id="plan_1"
        )
    )
    
    state["workout_plan"] = workout_plan
    state["current_step"] = "plan_generated"
    return state

def collect_feedback(state: WorkoutState) -> WorkoutState:
    """사용자 피드백 수집 및 계획 조정"""
    feedback = {
        "too_difficult": False,
        "too_easy": False,
        "preferred_exercises": [],
        "disliked_exercises": []
    }
    
    if feedback:
        adjusted_plan = adjust_plan_based_on_feedback.invoke({
            "workout_plan": state["workout_plan"],
            "feedback": feedback
        })
        
        # AI 메시지 추가
        state["messages"].append(
            AIMessage(
                content="운동 계획 조정 완료",
                additional_kwargs={
                    "tool_calls": [{
                        "id": "feedback_1",
                        "type": "function",
                        "function": {
                            "name": "adjust_plan_based_on_feedback",
                            "arguments": json.dumps(adjusted_plan, ensure_ascii=False)
                        }
                    }]
                }
            )
        )
        
        # Tool 응답 메시지 추가
        state["messages"].append(
            ToolMessage(
                content="계획 조정 완료",
                name="adjust_plan_based_on_feedback",
                tool_call_id="feedback_1"
            )
        )
        
        state["workout_plan"] = adjusted_plan
    
    state["feedback"] = feedback
    state["current_step"] = "feedback_received"
    return state

def finalize_plan(state: WorkoutState) -> WorkoutState:
    """최종 계획 검토 및 추천사항 제공"""
    # 간소화된 프롬프트 사용
    prompt = ChatPromptTemplate.from_messages([
        ("system", "운동 계획을 검토하고 핵심 추천사항을 2-3문장으로 제공해주세요."),
        MessagesPlaceholder(variable_name="messages"),
        ("human", "운동 계획 검토: {workout_plan}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({
        "messages": state["messages"],
        "workout_plan": json.dumps(state["workout_plan"], indent=2, ensure_ascii=False)
    })
    
    state["messages"].append(response)
    state["current_step"] = "complete"
    return state

def create_workout_workflow():
    """운동 워크플로우 생성"""
    workflow = StateGraph(WorkoutState)
    
    # Add nodes
    workflow.add_node("generate", generate_plan)
    workflow.add_node("collect_feedback", collect_feedback)
    workflow.add_node("finalize", finalize_plan)
    
    # Add edges
    workflow.add_edge(START, "generate")
    workflow.add_edge("generate", "collect_feedback")
    workflow.add_edge("collect_feedback", "finalize")
    workflow.add_edge("finalize", END)
    
    # 초기 상태 설정
    initial_state: WorkoutState = {
        "messages": [],
        "user_info": {},
        "current_step": "start",
        "workout_plan": {},
        "feedback": {}
    }
    
    return workflow.compile() 
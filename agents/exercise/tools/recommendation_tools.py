from typing import Dict, List
from langchain.tools import tool, BaseTool
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import json
from ..models.input_models import ExerciseRecommendationInput
from ..prompts.system_prompts import WORKOUT_RECOMMENDATION_PROMPT
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

# Initialize the LLM
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.7
)

# 운동 과학 연구 데이터베이스 (예시)
EXERCISE_RESEARCH_DB = {
    "스쿼트": {
        "research_papers": [
            {
                "title": "The Effect of Squat Depth on Lower Limb Muscle Activation",
                "authors": "Smith et al.",
                "year": 2022,
                "key_findings": "깊은 스쿼트가 대퇴사두근 활성화를 30% 더 증가",
                "recommendations": "무릎이 90도 이상 굽힐 때까지 스쿼트 수행"
            }
        ],
        "clinical_trials": [
            {
                "title": "Squat vs. Leg Press for Knee Rehabilitation",
                "participants": 100,
                "duration": "12주",
                "results": "스쿼트가 무릎 안정성 향상에 더 효과적"
            }
        ]
    },
    "데드리프트": {
        "research_papers": [
            {
                "title": "Deadlift Variations and Lower Back Health",
                "authors": "Johnson et al.",
                "year": 2023,
                "key_findings": "루마니안 데드리프트가 요통 환자에게 더 안전",
                "recommendations": "초기에는 루마니안 변형 추천"
            }
        ]
    }
}

class ExerciseRecommendationInput(BaseModel):
    fitness_level: str = Field(..., description="사용자의 피트니스 레벨 (초급/중급/고급)")
    focus_areas: List[str] = Field(..., description="중점적으로 다룰 운동 영역")
    restrictions: List[str] = Field(..., description="운동 제한사항")
    preferred_workout_time: str = Field(..., description="선호하는 운동 시간")
    weekly_workout_days: int = Field(..., description="주간 운동 일수")

class RecommendExercisesTool(BaseTool):
    name: str = "recommend_exercises"
    description: str = "사용자의 정보를 기반으로 맞춤형 운동을 추천합니다."
    args_schema: type[BaseModel] = ExerciseRecommendationInput

    def _run(self, fitness_level: str, focus_areas: List[str], restrictions: List[str], 
             preferred_workout_time: str, weekly_workout_days: int) -> Dict:
        llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.7
        )
        
        prompt = f"""
        다음 정보를 바탕으로 맞춤형 운동을 추천해주세요:
        - 피트니스 레벨: {fitness_level}
        - 중점 영역: {', '.join(focus_areas)}
        - 제한사항: {', '.join(restrictions)}
        - 선호 운동 시간: {preferred_workout_time}
        - 주간 운동 일수: {weekly_workout_days}일

        각 운동에 대해 다음 정보를 포함해주세요:
        - 운동 이름
        - 세트 수
        - 반복 횟수
        - 휴식 시간
        """
        
        response = llm.invoke(prompt)
        
        return {
            "exercises": response.content,
            "fitness_level": fitness_level,
            "focus_areas": focus_areas,
            "restrictions": restrictions,
            "preferred_workout_time": preferred_workout_time,
            "weekly_workout_days": weekly_workout_days
        }

class GenerateWorkoutPlanTool(BaseTool):
    name: str = "generate_workout_plan"
    description: str = "사용자의 정보를 기반으로 주간 운동 계획을 생성합니다."
    args_schema: type[BaseModel] = ExerciseRecommendationInput

    def _run(self, fitness_level: str, focus_areas: List[str], restrictions: List[str], 
             preferred_workout_time: str, weekly_workout_days: int) -> Dict:
        llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.7
        )
        
        prompt = f"""
        다음 정보를 바탕으로 주 {weekly_workout_days}회 운동 계획을 생성해주세요.
        각 운동은 반드시 name, sets, reps, rest 정보를 포함해야 합니다.

        - 피트니스 레벨: {fitness_level}
        - 중점 영역: {', '.join(focus_areas)}
        - 제한사항: {', '.join(restrictions)}
        - 선호 운동 시간: {preferred_workout_time}

        정확히 다음 형식으로 JSON 응답을 생성해주세요:
        {{
            "workout_days": [
                {{
                    "day": "1일차",
                    "exercises": [
                        {{
                            "name": "운동 이름",
                            "sets": 3,
                            "reps": "10-12",
                            "rest": "60초"
                        }}
                    ]
                }}
            ],
            "focus_areas": ["중점영역1", "중점영역2"],
            "weekly_workout_days": {weekly_workout_days}
        }}
        """
        
        response = llm.invoke(prompt)
        
        try:
            result = json.loads(response.content)
            # 응답 형식 검증
            if not isinstance(result.get("workout_days"), list):
                raise ValueError("workout_days must be a list")
            
            for day in result["workout_days"]:
                if not isinstance(day.get("exercises"), list):
                    raise ValueError("exercises must be a list")
                for exercise in day["exercises"]:
                    required_fields = ["name", "sets", "reps", "rest"]
                    if not all(field in exercise for field in required_fields):
                        raise ValueError(f"Exercise must contain all required fields: {required_fields}")
            
            return result
        except Exception as e:
            print(f"Error parsing LLM response: {e}")
            return {
                "workout_days": [],
                "focus_areas": focus_areas,
                "weekly_workout_days": weekly_workout_days
            }

recommend_exercises = RecommendExercisesTool()
generate_workout_plan = GenerateWorkoutPlanTool()

@tool(args_schema=ExerciseRecommendationInput)
def recommend_exercises(fitness_level: str, goals: List[str], age: int, weight: float, 
                       height: float, injuries: List[str], available_equipment: List[str],
                       target_muscles: str = None) -> Dict:
    """학술 연구를 바탕으로 사용자의 목표와 신체 조건에 맞는 운동을 추천"""
    # 연구 데이터 기반 추천 로직
    research_based_recommendations = []
    for exercise, research_data in EXERCISE_RESEARCH_DB.items():
        # 부상 고려
        if any(injury in str(research_data) for injury in injuries):
            continue
            
        # 연구 결과 분석
        research_summary = {
            "exercise": exercise,
            "evidence": [],
            "safety_considerations": []
        }
        
        # 연구 논문 분석
        for paper in research_data.get("research_papers", []):
            research_summary["evidence"].append({
                "type": "research_paper",
                "title": paper["title"],
                "key_findings": paper["key_findings"],
                "recommendations": paper["recommendations"]
            })
        
        # 임상 시험 분석
        for trial in research_data.get("clinical_trials", []):
            research_summary["evidence"].append({
                "type": "clinical_trial",
                "title": trial["title"],
                "results": trial["results"],
                "participants": trial["participants"]
            })
        
        research_based_recommendations.append(research_summary)
    
    # LLM을 사용한 추가 추천
    prompt = ChatPromptTemplate.from_messages([
        ("system", WORKOUT_RECOMMENDATION_PROMPT),
        ("human", """다음 정보와 연구 결과를 바탕으로 운동을 추천해주세요:
- 운동 경력: {fitness_level}
- 목표: {goals}
- 나이: {age}
- 체중: {weight}kg
- 키: {height}cm
- 부상/제한사항: {injuries}
- 사용 가능한 장비: {available_equipment}
- 타겟 근육: {target_muscles}

연구 결과:
{research_data}""")
    ])
    
    chain = prompt | llm
    response = chain.invoke({
        "fitness_level": fitness_level,
        "goals": goals,
        "age": age,
        "weight": weight,
        "height": height,
        "injuries": injuries,
        "available_equipment": available_equipment,
        "target_muscles": target_muscles,
        "research_data": json.dumps(research_based_recommendations, ensure_ascii=False)
    })
    
    try:
        recommendations = json.loads(response.content)
        # 연구 데이터와 LLM 추천을 결합
        for exercise in recommendations["exercises"]:
            research_data = next(
                (r for r in research_based_recommendations if r["exercise"] == exercise["name"]),
                None
            )
            if research_data:
                exercise["research_evidence"] = [
                    f"{e['key_findings']} ({e['title']})"
                    for e in research_data["evidence"]
                    if e["type"] == "research_paper"
                ]
        return recommendations
    except:
        return {
            "exercises": [],
            "scientific_basis": "추천 실패",
            "recommendations": "다시 시도해주세요"
        } 
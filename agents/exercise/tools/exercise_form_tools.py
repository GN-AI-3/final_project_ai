from langchain.tools import tool
from tavily import TavilyClient
from ..models.state_models import RoutingState
import os
from dotenv import load_dotenv

load_dotenv()

@tool
def web_search(query: str) -> str:
    """웹 검색 기반 운동 자세 추천"""
    tavily_client = TavilyClient(
        api_key=os.getenv("TAVILY_API_KEY")
    )
    results = tavily_client.search(query)
    return results

@tool
def get_user_info(user_id: str) -> str:
    """사용자 정보 조회"""

    return "사용자 정보 조회"

@tool
def get_exercise_info(exercise_name: str) -> str:
    """운동 정보 조회"""
    return "운동 정보 조회"

from typing import Dict, Any
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from ..models.state_models import RoutingState
from langchain.tools import Tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import MessagesPlaceholder, ChatPromptTemplate
from langchain.tools import StructuredTool
from ..tools.exercise_member_tools import master_select_db_multi
from ..models.input_models import MasterSelectMultiInput, EmptyArgs

load_dotenv()

def routing(state: RoutingState, llm: ChatOpenAI) -> RoutingState:
    """라우팅 노드"""

    # 테스트용 유저 정보 설정
    user_type = state.user_type

    if user_type == "trainer":
        state.plan = "trainer"
        return state
    elif user_type == "member":
        state.plan = "member"
        return state
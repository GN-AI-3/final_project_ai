# make/make2/agent_state.py
from typing import Annotated, Dict, Any, List, Optional
from pydantic import BaseModel
from langgraph.channels import LastValue

class AgentState(BaseModel):
    """
    에이전트의 상태를 관리하는 클래스
    """
    user_input: Annotated[str, LastValue(str)] = ""
    member_id: Annotated[int, LastValue(int)] = 3
    context: Annotated[Dict[str, Any], LastValue(dict)] = {}
    parsed_plan: Annotated[Dict[str, Any], LastValue(dict)] = {}
    tool_result: Annotated[str, LastValue(str)] = ""
    agent_out: Annotated[str, LastValue(str)] = ""
    retry_count: Annotated[int, LastValue(int)] = 0
    need_tool: Annotated[bool, LastValue(bool)] = False
    tool_name: Annotated[str, LastValue(str)] = ""
    tool_input: Annotated[Dict[str, Any], LastValue(dict)] = {}
    ask_user: Annotated[List[str], LastValue(list)] = []
    final_output: Annotated[str, LastValue(str)] = ""
    context_missing: Annotated[List[str], LastValue(list)] = []
    error: Annotated[str, LastValue(str)] = ""



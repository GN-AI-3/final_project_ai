# make/make2/agent_state.py
from typing import Annotated, Dict, Any, Optional
from pydantic import BaseModel
from langgraph.channels import LastValue

class AgentState(BaseModel):
    user_input : Annotated[str,  LastValue(str)]
    member_id  : Annotated[int,  LastValue(int)]

    context     : Annotated[Dict[str, Any], LastValue(dict)] = {}
    parsed_plan : Annotated[Dict[str, Any], LastValue(dict)] = {}
    tool_result : Annotated[str, LastValue(str)] = ""
    agent_out   : Annotated[str, LastValue(str)] = ""
    retry_count : Annotated[int, LastValue(int)] = 0
    tool_name: Optional[str] = None 
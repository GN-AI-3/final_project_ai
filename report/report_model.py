from typing import Any, List, Dict
from pydantic import BaseModel

class reportState(BaseModel):
    ptContractId: int
    exercise_report: dict = {}
    diet_report: dict = {}
    inbody_report: dict = {}


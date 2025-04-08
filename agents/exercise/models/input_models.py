from pydantic import BaseModel
from typing import Dict
from typing_extensions import TypedDict

class GetUserInfoInput(BaseModel):
    member_id: str

class MasterSelectInput(BaseModel):
    table_name: str
    column_name: str
    value: str

class MasterSelectMultiInput(BaseModel):
    table_name: str
    conditions: Dict[str, str]

class EmptyArgs(BaseModel):
    pass

class ExerciseRecordInput(TypedDict):
    member_id: int
    exercise_id: int
    date: str
    record_data: dict
    memo_data: dict
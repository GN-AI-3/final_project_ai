from pydantic import BaseModel
from typing import Dict

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
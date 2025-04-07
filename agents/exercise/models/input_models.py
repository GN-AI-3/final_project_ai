from pydantic import BaseModel

class GetUserInfoInput(BaseModel):
    member_id: str

class MasterSelectInput(BaseModel):
    table_name: str
    column_name: str
    value: str
from pydantic import BaseModel

class GetUserInfoInput(BaseModel):
    user_id: str

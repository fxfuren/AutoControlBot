from pydantic import BaseModel
from typing import List, Optional

class User(BaseModel):
    tg_id: int
    username: Optional[str]
    fio: Optional[str]
    role: str
    chats: List[str]

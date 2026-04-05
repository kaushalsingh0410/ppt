from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from langchain_core.messages import BaseMessage
from typing import List,Dict

class Ppt(BaseModel):
    feedback: Optional[str] = None
    num_slide: Optional[int] = None
    topic: Optional[str] = None
    action: Optional[str] = None
    last_update: Optional[str] = None
    thread_id: Optional[str] = None

class ThreadResponse(BaseModel):
    thread_id: str
    topic: str
    updated_at: datetime
    last_update: str
    img_path: Optional[str] = None

    class Config:
        from_attributes = True

class ThreadWithStateResponse(BaseModel):
    thread: ThreadResponse
    # state: List[BaseMessage]
    outline: List
    detailed_slides: List[Dict]

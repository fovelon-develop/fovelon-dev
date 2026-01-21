from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


# -------- Chat --------

class ChatMeta(BaseModel):
    session_id: Optional[str] = None
    lead_id: Optional[int] = None
    page_url: Optional[str] = None
    country: Optional[str] = None
    language: Optional[str] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None


class ChatRequest(BaseModel):
    business_id: int = Field(..., description="ID of the business/website")
    message: str = Field(..., description="User message from widget")
    meta: Optional[ChatMeta] = None


class ChatResponse(BaseModel):
    answer: str
    lead_id: int
    detected_language: Optional[str] = None
    topics: List[str] = []


# -------- Leads for inbox --------

class LeadSummary(BaseModel):
    id: int
    name: Optional[str] = None
    email: Optional[str] = None
    visitor_ip: Optional[str] = None
    last_seen_at: Optional[datetime] = None
    time_on_site_seconds: Optional[int] = None
    messages_count: Optional[int] = None
    created_at: datetime
    country: Optional[str]
    language: Optional[str]
    topic: Optional[str]
    last_question: Optional[str]
    last_answer: Optional[str]
    source_page: Optional[str]

    class Config:
        from_attributes = True

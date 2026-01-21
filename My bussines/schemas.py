from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


# -------- Chat --------

class ChatMeta(BaseModel):
    page_url: Optional[str] = None
    country: Optional[str] = None
    language: Optional[str] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None


class ChatRequest(BaseModel):
    business_id: int = Field(..., description="ID of the business/website")
    message: str = Field(..., description="User message from widget")
    lead_id: Optional[int] = None
    meta: Optional[ChatMeta] = None


class ChatResponse(BaseModel):
    answer: str
    lead_id: int
    detected_language: Optional[str] = None
    topics: List[str] = []


# -------- Leads for inbox --------

class LeadSummary(BaseModel):
    id: int
    created_at: datetime
    country: Optional[str]
    language: Optional[str]
    topic: Optional[str]
    last_question: Optional[str]
    last_answer: Optional[str]
    source_page: Optional[str]

    class Config:
        from_attributes = True


# -------- Lead detail (messages) --------

class MessageOut(BaseModel):
    id: int
    created_at: datetime
    role: str
    content: str
    language: Optional[str] = None

    class Config:
        from_attributes = True

class LeadDetail(BaseModel):
    lead: LeadSummary
    messages: List[MessageOut] = []


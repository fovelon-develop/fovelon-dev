from fastapi import Request
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException
from models import Business, FAQ, Lead, Message
from schemas import ChatRequest
from datetime import datetime


def get_business(db: Session, business_id: int) -> Optional[Business]:
    return db.query(Business).filter(Business.id == business_id).first()


def get_active_faqs(db: Session, business_id: int) -> List[FAQ]:
    return (
        db.query(FAQ)
        .filter(FAQ.business_id == business_id, FAQ.is_active == 1)
        .all()
    )


def create_lead_with_messages(
    db: Session,
    chat_req: ChatRequest,
    answer: str,
    detected_language: Optional[str],
    topics: List[str],
) -> Lead:
    meta_dict = chat_req.meta.dict() if chat_req.meta else {}
    first_topic = topics[0] if topics else None

    lead = Lead(
        business_id=chat_req.business_id,
        name=chat_req.meta.user_name if chat_req.meta else None,
        email=chat_req.meta.user_email if chat_req.meta else None,
        country=chat_req.meta.country if chat_req.meta else None,
        language=detected_language or (chat_req.meta.language if chat_req.meta else None),
        topic=first_topic,
        last_question=chat_req.message,
        last_answer=answer,
        source_page=chat_req.meta.page_url if chat_req.meta else None,
        meta=meta_dict or None,
    )
    db.add(lead)
    db.flush()  # تا lead.id داشته باشیم

    user_msg = Message(
        lead_id=lead.id,
        business_id=chat_req.business_id,
        role="user",
        content=chat_req.message,
        language=detected_language,
    )
    bot_msg = Message(
        lead_id=lead.id,
        business_id=chat_req.business_id,
        role="assistant",
        content=answer,
        language=detected_language,
    )
    db.add_all([user_msg, bot_msg])
    db.commit()
    db.refresh(lead)
    return lead


def list_leads_for_business(
    db: Session, business_id: int, limit: int = 50, offset: int = 0
) -> List[Lead]:
    return (
        db.query(Lead)
        .filter(Lead.business_id == business_id)
        .order_by(Lead.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


# ---------- new: lead/session helpers ----------

def get_lead(db: Session, lead_id: int) -> Lead | None:
    return db.query(Lead).filter(Lead.id == lead_id).first()

def create_empty_lead(db: Session, business_id: int, meta: dict | None = None) -> Lead:
    lead = Lead(
        business_id=business_id,
        meta=meta or {},
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead

def append_messages_to_lead(
    db: Session,
    lead_id: int,
    business_id: int,
    user_message: str,
    answer: str,
    detected_language: str | None,
    topics: list[str],
    request: Request,
) -> Lead:
    lead = get_lead(db, lead_id=lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if lead.business_id != business_id:
        raise HTTPException(status_code=400, detail="Lead business mismatch")

    # Update lead summary fields
    lead.last_question = user_message
    lead.last_answer = answer
    if detected_language:
        lead.language = detected_language
    if topics:
        lead.topic = topics[0]

    meta = lead.meta or {}
    # Update analytics
    xff = request.headers.get("x-forwarded-for")
    ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else None)
    if ip and not meta.get("visitor_ip"):
        meta["visitor_ip"] = ip
    meta["last_seen_at"] = datetime.utcnow().isoformat() + "Z"
    meta["messages_count"] = int(meta.get("messages_count") or 0) + 1
    lead.meta = meta

    # Create messages
    user_msg = Message(
        lead_id=lead.id,
        business_id=business_id,
        role="user",
        content=user_message,
        language=detected_language,
    )
    assistant_msg = Message(
        lead_id=lead.id,
        business_id=business_id,
        role="assistant",
        content=answer,
        language=detected_language,
    )
    db.add_all([user_msg, assistant_msg])
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def list_messages_for_lead(db: Session, lead_id: int):
    return (
        db.query(models.Message)
        .filter(models.Message.lead_id == lead_id)
        .order_by(models.Message.created_at.asc())
        .all()
    )

from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
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


def append_message_to_lead(
    db: Session,
    lead: Lead,
    chat_req: ChatRequest,
    answer: str,
    detected_language: Optional[str],
    topics: List[str],
) -> Lead:
    # update lead summary fields
    lead.last_question = chat_req.message
    lead.last_answer = answer
    if detected_language:
        lead.language = detected_language
    if topics:
        lead.topic = topics[0]
    # merge meta
    if chat_req.meta:
        meta_dict = chat_req.meta.dict()
        existing = lead.meta or {}
        existing.update({k:v for k,v in meta_dict.items() if v is not None})
        lead.meta = existing

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

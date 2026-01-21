from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import relationship

try:
    from sqlalchemy.dialects.postgresql import JSONB  # type: ignore
except Exception:
    JSONB = None
from datetime import datetime

from database import Base


class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    website = Column(String(255), nullable=True)
    default_language = Column(String(10), nullable=True, default="en")
    created_at = Column(DateTime, default=datetime.utcnow)

    faqs = relationship("FAQ", back_populates="business", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="business", cascade="all, delete-orphan")


class FAQ(Base):
    __tablename__ = "faqs"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    language = Column(String(10), nullable=True, default="en")
    is_active = Column(Integer, default=1)

    business = relationship("Business", back_populates="faqs")


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)

    name = Column(String(200), nullable=True)
    email = Column(String(200), nullable=True)
    country = Column(String(80), nullable=True)
    language = Column(String(20), nullable=True)
    topic = Column(String(80), nullable=True)

    last_question = Column(Text, nullable=True)
    last_answer = Column(Text, nullable=True)

    source_page = Column(String(255), nullable=True)
    # Works on SQLite locally and becomes JSONB on Postgres.
    meta_type = JSON().with_variant(JSONB(), "postgresql") if JSONB is not None else JSON
    meta = Column(meta_type, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    business = relationship("Business", back_populates="leads")
    messages = relationship("Message", back_populates="lead", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)

    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    language = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    lead = relationship("Lead", back_populates="messages")

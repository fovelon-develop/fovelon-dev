from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import os

from dotenv import load_dotenv
from openai import OpenAI

from database import Base, engine, get_db
from models import Business, FAQ
from schemas import ChatRequest, ChatResponse, LeadSummary
import crud

load_dotenv()

# ساخت جدول‌ها در اولین اجرا (MVP – بعداً میشه Alembic)
Base.metadata.create_all(bind=engine)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# If you don't set an OpenAI key, the app can still run in DEMO mode.
# Demo mode returns FAQ-based answers without calling OpenAI.
DEMO_MODE = not bool(OPENAI_API_KEY)
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

app = FastAPI(title="AutoSupport AI Backend")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# CORS برای تست لوکال
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # در پروداکشن محدود کن
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- simple demo pages (no hosting needed) ----------

@app.get("/", include_in_schema=False)
def landing_page():
    return FileResponse(os.path.join(BASE_DIR, "landing.html"))


@app.get("/widget", include_in_schema=False)
def widget_page():
    return FileResponse(os.path.join(BASE_DIR, "widget.html"))


@app.get("/inbox", include_in_schema=False)
def inbox_page():
    return FileResponse(os.path.join(BASE_DIR, "inbox.html"))


# ---------- helper: تشخیص ساده topic ----------

def detect_topics(text: str) -> List[str]:
    text_low = text.lower()
    topics = []
    if any(k in text_low for k in ["price", "pricing", "cost", "fee", "plan"]):
        topics.append("pricing")
    if any(k in text_low for k in ["install", "setup", "script", "embed", "widget"]):
        topics.append("setup")
    if any(k in text_low for k in ["language", "spanish", "german", "arabic", "farsi", "persian"]):
        topics.append("languages")
    if any(k in text_low for k in ["integrat", "zapier", "api", "webhook"]):
        topics.append("integration")
    if not topics:
        topics.append("general")
    return topics


# ---------- /chat ----------

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest, db: Session = Depends(get_db)):
    business = crud.get_business(db, payload.business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    faqs = crud.get_active_faqs(db, payload.business_id)

    faq_text = ""
    for faq in faqs[:12]:
        faq_text += f"Q: {faq.question}\nA: {faq.answer}\n\n"

    # 20 زبان مختلف که ویجت/assistant پشتیبانی می‌کند
    supported_langs = (
        "English, Spanish, German, French, Portuguese, Russian, Arabic, Farsi, "
        "Turkish, Italian, Dutch, Polish, Ukrainian, Japanese, Chinese, Hindi, "
        "Danish, Swedish, Norwegian, Kurdish and many more."
    )

    system_prompt = f"""
You are an AI support assistant for a website called "{business.name}".

- Answer ONLY based on the FAQ and info below plus the user's question.
- If you are not sure, DO NOT invent answers. Instead, ask the visitor for name and email
  so a human can follow up.
- Be short, clear and friendly. 
- You support all languages. If the user writes in another language, answer in that language.

Supported languages include: {supported_langs}

Here are some FAQ entries for context:
{faq_text or "No FAQ was provided yet."}
    """.strip()

    user_message = payload.message.strip()

    if DEMO_MODE:
        # Very simple fallback: return the first FAQ that shares a keyword.
        # This lets you run & demo the whole flow without any paid API.
        answer = None
        for faq in faqs:
            if any(w in faq.question.lower() for w in user_message.lower().split()[:6]):
                answer = faq.answer
                break
        if not answer:
            answer = (
                "Thanks! To help you properly, could you share your name and email "
                "so a human can follow up? (Demo mode: no AI key set.)"
            )
    else:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=350,
        )
        answer = completion.choices[0].message.content.strip()

    topics = detect_topics(user_message)
    detected_language = None  # میشه بعداً با متد جدا تشخیص داد

    lead = crud.create_lead_with_messages(
        db=db,
        chat_req=payload,
        answer=answer,
        detected_language=detected_language,
        topics=topics,
    )

    return ChatResponse(
        answer=answer,
        lead_id=lead.id,
        detected_language=lead.language,
        topics=topics,
    )


# ---------- /leads ----------

# Existing query-string version: /leads?business_id=1
@app.get("/leads", response_model=List[LeadSummary])
def list_leads(
    business_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    leads = crud.list_leads_for_business(db, business_id=business_id, limit=limit, offset=offset)
    return leads


# Convenience route for the inbox UI which calls /leads/<business_id>
@app.get("/leads/{business_id}", response_model=List[LeadSummary])
def list_leads_path(
    business_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    return list_leads(business_id=business_id, limit=limit, offset=offset, db=db)




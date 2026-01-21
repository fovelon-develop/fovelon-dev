from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import os
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

from database import Base, engine, get_db
from models import Business, FAQ
from schemas import ChatRequest, ChatResponse, LeadSummary, LeadDetail
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



# ---------- analytics helpers ----------

def get_client_ip(request: Request) -> str | None:
    # Render passes client ip in X-Forwarded-For
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None

def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"



# ---------- session lifecycle (for real analytics) ----------

@app.post("/session/start")
def session_start(payload: ChatRequest, request: Request, db: Session = Depends(get_db)):
    # Create a lead for this browsing session and return lead_id.
    business = crud.get_business(db, payload.business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    meta = payload.meta.dict() if payload.meta else {}
    meta["session_id"] = (payload.meta.session_id if payload.meta else None) or meta.get("session_id")
    meta["page_url"] = meta.get("page_url") or (payload.meta.page_url if payload.meta else None)
    meta["country"] = meta.get("country") or (payload.meta.country if payload.meta else None)
    meta["language"] = meta.get("language") or (payload.meta.language if payload.meta else None)
    meta["visitor_ip"] = get_client_ip(request)
    meta["user_agent"] = request.headers.get("user-agent")
    meta["referer"] = request.headers.get("referer")
    meta["started_at"] = now_iso()
    meta["last_seen_at"] = now_iso()
    meta.setdefault("time_on_site_seconds", 0)
    meta.setdefault("messages_count", 0)

    lead = crud.create_empty_lead(db=db, business_id=payload.business_id, meta=meta)
    return {"lead_id": lead.id}

@app.post("/session/end")
def session_end(payload: dict, request: Request, db: Session = Depends(get_db)):
    lead_id = payload.get("lead_id")
    duration = payload.get("duration_seconds")
    if not lead_id:
        raise HTTPException(status_code=400, detail="lead_id required")
    lead = crud.get_lead(db, lead_id=lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    meta = lead.meta or {}
    meta["last_seen_at"] = now_iso()
    if isinstance(duration, (int, float)) and duration >= 0:
        meta["time_on_site_seconds"] = int(meta.get("time_on_site_seconds") or 0) + int(duration)
    lead.meta = meta
    db.add(lead)
    db.commit()
    return {"ok": True}

# ---------- /chat ----------

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest, request: Request, db: Session = Depends(get_db)):
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

    lead_id = payload.meta.lead_id if payload.meta else None
    if lead_id:
        lead = crud.append_messages_to_lead(
            db=db,
            lead_id=lead_id,
            business_id=payload.business_id,
            user_message=user_message,
            answer=answer,
            detected_language=detected_language,
            topics=topics,
            request=request,
        )
    else:
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



def serialize_lead(lead, db: Session):
    meta = lead.meta or {}
    # messages_count: count messages for this lead
    try:
        msg_count = db.query(Message).filter(crud.Message.lead_id == lead.id).count()
    except Exception:
        msg_count = None
    return {
        "id": lead.id,
        "created_at": lead.created_at,
        "name": lead.name,
        "email": lead.email,
        "country": lead.country,
        "language": lead.language,
        "topic": lead.topic,
        "last_question": lead.last_question,
        "last_answer": lead.last_answer,
        "source_page": lead.source_page,
        "visitor_ip": meta.get("visitor_ip"),
        "last_seen_at": meta.get("last_seen_at"),
        "time_on_site_seconds": meta.get("time_on_site_seconds"),
        "messages_count": msg_count if msg_count is not None else meta.get("messages_count"),
    }

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
    return [serialize_lead(l, db) for l in leads]


# Convenience route for the inbox UI which calls /leads/<business_id>
@app.get("/leads/{business_id}", response_model=List[LeadSummary])
def list_leads_path(
    business_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    return list_leads(business_id=business_id, limit=limit, offset=offset, db=db)




# Compatibility redirects (so old links like /widget.html keep working)
@app.get("/widget.html", include_in_schema=False)
def widget_html_redirect():
    return RedirectResponse(url="/widget", status_code=302)

@app.get("/inbox.html", include_in_schema=False)
def inbox_html_redirect():
    return RedirectResponse(url="/inbox", status_code=302)


@app.get("/lead/{lead_id}", response_model=LeadDetail)
def get_lead_detail(lead_id: int, db: Session = Depends(get_db)):
    lead = crud.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    data = serialize_lead(lead, db)
    messages = crud.list_messages_for_lead(db, lead_id)
    data["messages"] = [
        {"role": m.role, "content": m.content, "created_at": m.created_at}
        for m in messages
    ]
    return data

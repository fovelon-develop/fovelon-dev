from database import Base, engine, SessionLocal
from models import Business, FAQ

Base.metadata.create_all(bind=engine)

db = SessionLocal()

# آیا بیزنس تستی وجود دارد؟
existing = db.query(Business).filter_by(id=1).first()
if existing:
    print("Business #1 already exists.")
else:
    biz = Business(
        id=1,
        name="Demo Coaching Program",
        website="https://example.com",
        default_language="en",
    )
    db.add(biz)
    db.flush()

    faqs = [
        FAQ(
            business_id=biz.id,
            question="How long does it take to install the widget?",
            answer="Usually under 5 minutes. You paste one script tag into your site and the assistant goes live.",
        ),
        FAQ(
            business_id=biz.id,
            question="Can the assistant answer in multiple languages?",
            answer="Yes. It can reply in more than 20 languages. Your visitors simply write in their language and the AI follows.",
        ),
        FAQ(
            business_id=biz.id,
            question="Will the AI invent answers?",
            answer="No. It uses your FAQ and offer. If it is not confident, it asks for contact details and sends the question to your inbox.",
        ),
    ]
    db.add_all(faqs)
    db.commit()
    print("Seed data created: business #1 with sample FAQs.")

db.close()

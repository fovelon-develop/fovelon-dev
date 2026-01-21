from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# --- Developer-friendly default ---
# If you don't have hosting yet, you can run everything locally with SQLite.
# To use Postgres later, set DATABASE_URL in your .env.
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./app.db"

engine = create_engine(DATABASE_URL, echo=False, future=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    from sqlalchemy.orm import Session
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

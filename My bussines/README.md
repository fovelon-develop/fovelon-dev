# AutoSupport AI (MVP) – Local Run

This project can run **without any hosting**.

## 1) Create venv & install

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
```

## 2) (Optional) set env

Copy `.env.example` to `.env`.

- If you **don't** set `OPENAI_API_KEY`, the app runs in **DEMO mode** (no paid API).
- If you **don't** set `DATABASE_URL`, the app uses **SQLite**: `./app.db`.

## 3) Seed demo data

```bash
python seed_demo_data.py
```

## 4) Run backend

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## 5) Open demo pages

- Landing: http://127.0.0.1:8000/
- Widget: http://127.0.0.1:8000/widget
- Inbox:  http://127.0.0.1:8000/inbox

## Notes
- Inbox expects `business_id=1` (created by `seed_demo_data.py`).

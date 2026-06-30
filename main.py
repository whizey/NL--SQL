"""
main.py  -  FastAPI NL->SQL Clinic API (RAG-augmented)
Start:  uvicorn main:app --port 8000 --reload

Pipeline per request:
    question -> RAG retrieval (top-k verified Q->SQL examples)
             -> few-shot prompt -> Groq (primary) / Gemini (fallback)
             -> SQL safety validation -> execute -> chart -> JSON
With MD5 response caching (5-min TTL) and per-IP rate limiting (20 req/min).
"""

import hashlib
import logging
import os
import re
import sqlite3
import time
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
import google.generativeai as genai
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from openai import OpenAI
from pydantic import BaseModel, Field, validator

from rag import retriever  # <-- RAG retrieval layer

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
DB_PATH           = "clinic.db"
GROQ_API_KEY      = os.getenv("GROQ_API_KEY", "")
CACHE_TTL         = 300
RATE_LIMIT_MAX    = 20
RATE_LIMIT_WINDOW = 60
TOP_K             = 3
TODAY             = date.today().isoformat()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="Clinic NL->SQL API (RAG)", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

groq_client = OpenAI(api_key=GROQ_API_KEY or "none", base_url="https://api.groq.com/openai/v1")

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = f"""You are a SQLite SQL generator. Return ONLY the raw SQL query - no explanation, no markdown, no code fences, no trailing semicolon.

RULES:
1. Generate exactly ONE SELECT statement.
2. Only use columns that exist in the schema below - never invent column names.
3. Always SELECT meaningful columns (names, labels) alongside aggregates.
4. Use table aliases consistently: patients p, doctors d, appointments a, invoices i, treatments t.
5. NEVER join tables unless the question explicitly needs data from both tables.
6. For revenue/invoice questions with no mention of doctor/patient name -> query invoices table alone.
7. invoices already has doctor_id - never route through appointments to reach doctors.

SCHEMA:
  patients    (id, first_name, last_name, email, phone, date_of_birth, gender, city, registered_date)
  doctors     (id, name, specialization, department, phone)
  appointments(id, patient_id, doctor_id, appointment_date, status, notes)
              -- status: 'Scheduled' | 'Completed' | 'Cancelled' | 'No-Show'
  treatments  (id, appointment_id, treatment_name, cost, duration_minutes)
  invoices    (id, patient_id, doctor_id, invoice_date, total_amount, paid_amount, status)
              -- status: 'Paid' | 'Pending' | 'Overdue'  ("unpaid" = Pending or Overdue)

TIME RULES (today = {TODAY}):
  "last month"  -> >= DATE('now','start of month','-1 month') AND < DATE('now','start of month')
  "this year"   -> strftime('%Y', col) = strftime('%Y','now')
  monthly trend -> strftime('%Y-%m', col)
"""

# ── SQL Safety ────────────────────────────────────────────────────────────────
_BLOCKED_KW = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|EXEC|EXECUTE|GRANT|REVOKE|SHUTDOWN|xp_|sp_)\b",
    re.IGNORECASE,
)
_BLOCKED_TBL = re.compile(
    r"\b(sqlite_master|sqlite_sequence|sqlite_stat\d?|information_schema)\b", re.IGNORECASE
)


def validate_sql(sql: str) -> Tuple[bool, str]:
    s = sql.strip()
    if not s.upper().startswith("SELECT"):
        return False, "Only SELECT queries are allowed."
    if _BLOCKED_KW.search(s):
        return False, "Query contains a forbidden keyword."
    if _BLOCKED_TBL.search(s):
        return False, "Queries against system tables are not allowed."
    return True, ""


# ── Cache ─────────────────────────────────────────────────────────────────────
_cache: Dict[str, Dict] = {}
def _cache_key(q: str) -> str: return hashlib.md5(q.strip().lower().encode()).hexdigest()
def _cache_get(key: str) -> Optional[Dict]:
    e = _cache.get(key)
    return e["data"] if e and (time.time() - e["ts"]) < CACHE_TTL else None
def _cache_set(key: str, data: Dict): _cache[key] = {"ts": time.time(), "data": data}

# ── Rate Limiting ─────────────────────────────────────────────────────────────
_rate_limit: Dict[str, List[float]] = {}
def _within_rate_limit(ip: str) -> bool:
    now = time.time()
    hits = [t for t in _rate_limit.get(ip, []) if now - t < RATE_LIMIT_WINDOW]
    if len(hits) >= RATE_LIMIT_MAX:
        return False
    _rate_limit[ip] = hits + [now]
    return True

# ── SQL Execution ─────────────────────────────────────────────────────────────
def run_sql(sql: str) -> Tuple[List[str], List[List]]:
    con = sqlite3.connect(DB_PATH); con.row_factory = sqlite3.Row
    cur = con.cursor(); cur.execute(sql); raw = cur.fetchall(); con.close()
    if not raw:
        return [], []
    return list(raw[0].keys()), [list(r) for r in raw]

# ── Chart Builder ─────────────────────────────────────────────────────────────
def build_chart(columns: List[str], rows: List[List]) -> Optional[Dict]:
    try:
        import plotly.graph_objects as go
        if not rows or len(columns) < 2:
            return None
        x, y = [], []
        for r in rows:
            x.append(str(r[0]))
            try:
                y.append(float(r[1]))
            except (TypeError, ValueError):
                return None
        is_time = any(k in columns[0].lower() for k in ("month", "date", "year"))
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers") if is_time else go.Bar(x=x, y=y))
        return {"plotly": fig.to_dict(), "chart_type": "line" if is_time else "bar"}
    except Exception as e:
        log.warning("Chart build failed: %s", e)
        return None

# ── LLM Call — RAG-augmented | Primary: Groq | Fallback: Gemini ───────────────
def call_llm(question: str) -> Tuple[str, str, int]:
    """Retrieve verified examples, inject as few-shot context, then generate."""
    fewshot = retriever.build_fewshot_block(question, k=TOP_K)
    n_examples = fewshot.count("Q:") if fewshot else 0
    user_content = (f"{fewshot}\n\nNow write SQL for this question:\n{question}"
                    if fewshot else question)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user_content},
    ]

    # Primary: Groq
    if GROQ_API_KEY:
        try:
            resp = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile", temperature=0, messages=messages)
            log.info("LLM: Groq | retrieved %d examples", n_examples)
            return resp.choices[0].message.content, "Groq · llama-3.3-70b", n_examples
        except Exception as e:
            log.warning("Groq failed (%s) - falling back to Gemini", e)

    # Fallback: Gemini
    google_key = os.getenv("GOOGLE_API_KEY")
    if google_key:
        try:
            genai.configure(api_key=google_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            resp = model.generate_content(SYSTEM_PROMPT + "\n\n" + user_content)
            log.info("LLM: Gemini fallback | retrieved %d examples", n_examples)
            return resp.text, "Gemini · gemini-2.0-flash", n_examples
        except Exception as e:
            log.warning("Gemini also failed: %s", e)

    raise HTTPException(503, detail="Both Groq and Gemini failed. Check your API keys in .env")


def clean_sql(raw: str) -> str:
    sql = re.sub(r"```(?:sql)?", "", raw.strip(), flags=re.IGNORECASE).replace("```", "")
    m = re.search(r"(SELECT\b[\s\S]+)", sql, re.IGNORECASE)
    return (m.group(1).strip() if m else sql.strip()).rstrip(";").strip()

# ── Models ────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    @validator("question")
    def not_blank(cls, v):
        if not v.strip():
            raise ValueError("question must not be blank")
        return v.strip()

def _error_response(status: int, message: str, sql: Optional[str] = None):
    return JSONResponse(status_code=status, content={
        "message": message, "sql_query": sql, "model_used": None, "columns": [],
        "rows": [], "row_count": 0, "chart": None, "chart_type": None,
        "examples_used": 0, "cached": False})

# ── Routes ────────────────────────────────────────────────────────────────────
@app.post("/chat")
async def chat(req: ChatRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    log.info("POST /chat | ip=%s | q=%r", client_ip, req.question)

    if not _within_rate_limit(client_ip):
        raise HTTPException(429, detail="Too many requests - slow down.")

    ckey = _cache_key(req.question)
    cached = _cache_get(ckey)
    if cached:
        log.info("Cache HIT | %s", req.question)
        return JSONResponse(content={**cached, "cached": True})

    try:
        raw_llm, model_used, n_examples = call_llm(req.question)
    except HTTPException:
        raise
    except Exception as e:
        log.error("LLM error: %s", e, exc_info=True)
        return _error_response(500, f"LLM error: {str(e)}")

    sql = clean_sql(raw_llm)
    if not sql or "select" not in sql.lower():
        return _error_response(500, "Failed to extract a valid SQL statement.", sql)

    ok, err = validate_sql(sql)
    if not ok:
        return _error_response(400, f"Blocked SQL: {err}", sql)

    try:
        columns, rows = run_sql(sql)
    except sqlite3.Error as e:
        return _error_response(422, str(e), sql)

    chart_info = build_chart(columns, rows) if rows and len(columns) >= 2 else None
    result = {
        "message": "Here are your results." if rows else "No data found.",
        "sql_query": sql, "model_used": model_used,
        "columns": columns, "rows": rows, "row_count": len(rows),
        "chart": chart_info["plotly"] if chart_info else None,
        "chart_type": chart_info["chart_type"] if chart_info else None,
        "examples_used": n_examples, "cached": False,
    }
    _cache_set(ckey, result)
    return JSONResponse(content=result)


@app.get("/health")
async def health():
    db_status = "disconnected"
    try:
        con = sqlite3.connect(DB_PATH); con.execute("SELECT COUNT(*) FROM patients"); con.close()
        db_status = "connected"
    except Exception as e:
        log.error("DB health check failed: %s", e)
    return {"status": "ok", "database": db_status,
            "retrieval_examples": len(retriever.pairs)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

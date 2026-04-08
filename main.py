"""
main.py  –  FastAPI NL→SQL Clinic API
Start:  uvicorn main:app --port 8000 --reload

Endpoints:
    POST /chat    — natural language → SQL + results + chart
    GET  /health  — liveness + DB check
    GET  /        — browser UI
"""

import hashlib
import logging
import os
import re
import sqlite3
import time
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv  # ← ADD THIS LINE
import google.generativeai as genai
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from openai import OpenAI
from pydantic import BaseModel, Field, validator
load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
DB_PATH           = "clinic.db"
GROQ_API_KEY      = os.getenv("GROQ_API_KEY", "")
CACHE_TTL         = 300
RATE_LIMIT_MAX    = 20
RATE_LIMIT_WINDOW = 60
TODAY             = date.today().isoformat()

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger(__name__)

# ── FastAPI ───────────────────────────────────────────────────────────────────
app = FastAPI(title="Clinic NL→SQL API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── LLM Clients ───────────────────────────────────────────────────────────────
groq_client = OpenAI(
    api_key=GROQ_API_KEY or "none",
    base_url="https://api.groq.com/openai/v1",
)

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = f"""You are a SQLite SQL generator. Return ONLY the raw SQL query — no explanation, no markdown, no code fences, no trailing semicolon.

RULES:
1. Generate exactly ONE SELECT statement.
2. Only use columns that exist in the schema below — never invent column names.
3. Always SELECT meaningful columns (names, labels) alongside aggregates.
4. Use table aliases consistently: patients p, doctors d, appointments a, invoices i, treatments t.
5. NEVER join tables unless the question explicitly needs data from both tables.
6. For revenue/invoice questions with no mention of doctor/patient name → query invoices table alone.
7. Before writing any JOIN ask: "does my SELECT or WHERE need a column from that table?" If no — skip the join.
   invoices already has doctor_id — never route through appointments to reach doctors.

SCHEMA:
  patients    (id, first_name, last_name, email, phone, date_of_birth, gender, city, registered_date)
  doctors     (id, name, specialization, department, phone)
  appointments(id, patient_id, doctor_id, appointment_date, status, notes)
              -- status values: 'Scheduled' | 'Completed' | 'Cancelled' | 'No-Show'
  treatments  (id, appointment_id, treatment_name, cost, duration_minutes)
  invoices    (id, patient_id, doctor_id, invoice_date, total_amount, paid_amount, status)
              -- status values: 'Paid' | 'Pending' | 'Overdue'
              -- "unpaid" = status IN ('Pending', 'Overdue')

TIME RULES (today = {TODAY}):
  "last month"   → >= DATE('now','start of month','-1 month') AND < DATE('now','start of month')
  "last quarter" → >= DATE('now','-3 months') AND < DATE('now')
  "this year"    → strftime('%Y', col) = strftime('%Y','now')
  "last year"    → strftime('%Y', col) = strftime('%Y','now','-1 year')
  monthly trend  → strftime('%Y-%m', col)
"""

# ── SQL Safety ────────────────────────────────────────────────────────────────
_BLOCKED_KW = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|EXEC|EXECUTE"
    r"|GRANT|REVOKE|SHUTDOWN|xp_|sp_)\b",
    re.IGNORECASE,
)
_BLOCKED_TBL = re.compile(
    r"\b(sqlite_master|sqlite_sequence|sqlite_stat\d?|information_schema)\b",
    re.IGNORECASE,
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


def _cache_key(q: str) -> str:
    return hashlib.md5(q.strip().lower().encode()).hexdigest()


def _cache_get(key: str) -> Optional[Dict]:
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < CACHE_TTL:
        return entry["data"]
    return None


def _cache_set(key: str, data: Dict):
    _cache[key] = {"ts": time.time(), "data": data}


# ── Rate Limiting ─────────────────────────────────────────────────────────────
_rate_limit: Dict[str, List[float]] = {}


def _within_rate_limit(ip: str) -> bool:
    now  = time.time()
    hits = [t for t in _rate_limit.get(ip, []) if now - t < RATE_LIMIT_WINDOW]
    if len(hits) >= RATE_LIMIT_MAX:
        return False
    _rate_limit[ip] = hits + [now]
    return True


# ── SQL Execution ─────────────────────────────────────────────────────────────
def run_sql(sql: str) -> Tuple[List[str], List[List]]:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(sql)
    raw = cur.fetchall()
    con.close()
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
        if is_time:
            fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers"))
        else:
            fig.add_trace(go.Bar(x=x, y=y))

        return {
            "plotly":     fig.to_dict(),
            "chart_type": "line" if is_time else "bar",
        }
    except Exception as e:
        log.warning("Chart build failed: %s", e)
        return None


# ── LLM Call — Primary: Groq | Fallback: Gemini ──────────────────────────────
def call_llm(question: str) -> Tuple[str, str]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": question},
    ]

    # Primary: Groq
    if GROQ_API_KEY:
        try:
            resp = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                temperature=0,
                messages=messages,
            )
            log.info("LLM: Groq")
            return resp.choices[0].message.content, "Groq · llama-3.3-70b"
        except Exception as e:
            log.warning("Groq failed (%s) — falling back to Gemini", e)

    # Fallback: Gemini
    google_key = os.getenv("GOOGLE_API_KEY")
    if google_key:
        try:
            genai.configure(api_key=google_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            resp  = model.generate_content(SYSTEM_PROMPT + "\n\nQuestion: " + question)
            log.info("LLM: Gemini fallback")
            return resp.text, "Gemini · gemini-2.0-flash"
        except Exception as e:
            log.warning("Gemini also failed: %s", e)

    raise HTTPException(503, detail="Both Groq and Gemini failed. Check your API keys in .env")


def clean_sql(raw: str) -> str:
    """Strip markdown fences and grab the first SELECT statement."""
    sql = raw.strip()
    sql = re.sub(r"```(?:sql)?", "", sql, flags=re.IGNORECASE).replace("```", "")
    m   = re.search(r"(SELECT\b[\s\S]+)", sql, re.IGNORECASE)
    sql = m.group(1).strip() if m else sql.strip()
    return sql.rstrip(";").strip()


# ── Request / Response Models ─────────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)

    @validator("question")
    def not_blank(cls, v):
        if not v.strip():
            raise ValueError("question must not be blank")
        return v.strip()


class ChatResponse(BaseModel):
    message:    str
    sql_query:  Optional[str]
    model_used: Optional[str]
    columns:    List[str]
    rows:       List[List[Any]]
    row_count:  int
    chart:      Optional[Dict]
    chart_type: Optional[str]
    cached:     bool = False


class HealthResponse(BaseModel):
    status:             str
    database:           str
    agent_memory_items: int


def _error_response(status: int, message: str, sql: Optional[str] = None):
    return JSONResponse(
        status_code=status,
        content={
            "message":    message,
            "sql_query":  sql,
            "model_used": None,
            "columns":    [],
            "rows":       [],
            "row_count":  0,
            "chart":      None,
            "chart_type": None,
            "cached":     False,
        },
    )


# ── Routes ────────────────────────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    log.info("POST /chat | ip=%s | q=%r", client_ip, req.question)

    if not _within_rate_limit(client_ip):
        log.warning("Rate limit exceeded | ip=%s", client_ip)
        raise HTTPException(429, detail="Too many requests — slow down.")

    ckey   = _cache_key(req.question)
    cached = _cache_get(ckey)
    if cached:
        log.info("Cache HIT | %s", req.question)
        return JSONResponse(content={**cached, "cached": True})

    try:
        raw_llm, model_used = call_llm(req.question)
    except HTTPException:
        raise
    except Exception as e:
        log.error("LLM error: %s", e, exc_info=True)
        return _error_response(500, f"LLM error: {str(e)}")

    log.info("RAW LLM (%s): %s", model_used, raw_llm)
    sql = clean_sql(raw_llm)
    log.info("CLEANED SQL: %s", sql)

    if not sql or "select" not in sql.lower():
        return _error_response(500, "Failed to extract a valid SQL statement.", sql)

    ok, err = validate_sql(sql)
    if not ok:
        return _error_response(400, f"Blocked SQL: {err}", sql)

    try:
        columns, rows = run_sql(sql)
        log.info("ROWS: %d", len(rows))
    except sqlite3.Error as e:
        log.error("SQL exec error: %s", e)
        return _error_response(422, str(e), sql)

    chart_info = build_chart(columns, rows) if rows and len(columns) >= 2 else None

    result = {
        "message":    "Here are your results." if rows else "No data found.",
        "sql_query":  sql,
        "model_used": model_used,
        "columns":    columns,
        "rows":       rows,
        "row_count":  len(rows),
        "chart":      chart_info["plotly"]     if chart_info else None,
        "chart_type": chart_info["chart_type"] if chart_info else None,
        "cached":     False,
    }

    _cache_set(ckey, result)
    return JSONResponse(content=result)


@app.get("/health", response_model=HealthResponse)
async def health():
    db_status = "disconnected"
    mem_count = 15

    try:
        con = sqlite3.connect(DB_PATH)
        con.execute("SELECT COUNT(*) FROM patients")
        con.close()
        db_status = "connected"
    except Exception as e:
        log.error("DB health check failed: %s", e)

    try:
        if os.path.exists("memory_count.txt"):
            with open("memory_count.txt") as f:
                mem_count = int(f.read().strip())
    except Exception:
        pass

    return HealthResponse(status="ok", database=db_status, agent_memory_items=mem_count)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )


# ── UI ────────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def home():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <title>NL → SQL</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap" rel="stylesheet"/>
    <style>
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        :root {
            --bg:       #07090f;
            --surface:  #0e1117;
            --border:   #1c2236;
            --accent:   #7aa2d4;
            --muted:    #3a4f66;
            --text:     #c9d8e8;
            --text-dim: #526070;
            --sql-col:  #89b4d6;
            --error:    #e07a7a;
            --groq:     #4fd1a5;
            --gemini:   #4285f4;
        }

        html, body { min-height: 100vh; background: var(--bg); color: var(--text); font-family: 'Syne', sans-serif; }

        body::before {
            content: ''; position: fixed; inset: 0;
            background-image: linear-gradient(var(--border) 1px, transparent 1px),
                              linear-gradient(90deg, var(--border) 1px, transparent 1px);
            background-size: 40px 40px; opacity: 0.35; pointer-events: none; z-index: 0;
        }

        .wrap { position: relative; z-index: 1; max-width: 860px; margin: 0 auto; padding: 48px 24px 80px; }

        header { display: flex; align-items: center; gap: 14px; margin-bottom: 40px; }
        .logo-badge {
            width: 42px; height: 42px; background: var(--accent); border-radius: 10px;
            display: grid; place-items: center; font-size: 20px; flex-shrink: 0;
            box-shadow: 0 0 18px rgba(122,162,212,0.2);
        }
        header h1 { font-size: 1.6rem; font-weight: 800; letter-spacing: -0.02em; color: #fff; }
        header h1 span { color: var(--accent); }
        .tag {
            margin-left: auto; font-family: 'Space Mono', monospace; font-size: 0.65rem;
            color: var(--text-dim); border: 1px solid var(--border); padding: 4px 10px;
            border-radius: 99px; letter-spacing: 0.08em;
        }

        .input-card {
            background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
            padding: 20px; margin-bottom: 24px; transition: border-color 0.2s;
        }
        .input-card:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(122,162,212,0.08); }
        .input-label {
            font-family: 'Space Mono', monospace; font-size: 0.65rem; color: var(--text-dim);
            letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 10px;
        }
        textarea {
            width: 100%; background: transparent; border: none; outline: none; resize: none;
            color: var(--text); font-family: 'Syne', sans-serif; font-size: 1.05rem;
            line-height: 1.6; min-height: 72px; caret-color: var(--accent);
        }
        textarea::placeholder { color: var(--muted); }
        .input-footer {
            display: flex; align-items: center; justify-content: space-between;
            margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border);
        }

        .hint { font-family: 'Space Mono', monospace; font-size: 0.6rem; color: var(--text-dim); transition: color 0.3s; }
        .hint.groq   { color: var(--groq); }
        .hint.gemini { color: var(--gemini); }

        button#ask-btn {
            display: flex; align-items: center; gap: 8px; background: var(--accent);
            color: #0d1117; font-family: 'Syne', sans-serif; font-weight: 700;
            font-size: 0.85rem; padding: 10px 22px; border: none; border-radius: 10px;
            cursor: pointer; letter-spacing: 0.02em; transition: opacity 0.15s, transform 0.1s;
        }
        button#ask-btn:hover  { opacity: 0.85; transform: translateY(-1px); }
        button#ask-btn:active { transform: translateY(0); }
        button#ask-btn:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }

        .spinner {
            display: none; width: 14px; height: 14px;
            border: 2px solid rgba(7,9,15,0.3); border-top-color: #07090f;
            border-radius: 50%; animation: spin 0.7s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        .section {
            background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
            margin-bottom: 16px; overflow: hidden; animation: fadeUp 0.3s ease both;
        }
        @keyframes fadeUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

        .section-header {
            display: flex; align-items: center; justify-content: space-between;
            padding: 12px 18px; border-bottom: 1px solid var(--border);
        }
        .section-title {
            font-family: 'Space Mono', monospace; font-size: 0.65rem; letter-spacing: 0.12em;
            text-transform: uppercase; color: var(--text-dim); display: flex; align-items: center; gap: 8px;
        }
        .section-title .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 6px rgba(122,162,212,0.4); }

        .row-badge {
            font-family: 'Space Mono', monospace; font-size: 0.6rem;
            background: rgba(122,162,212,0.08); color: var(--accent);
            border: 1px solid rgba(122,162,212,0.2); padding: 2px 8px; border-radius: 99px;
        }

        .model-badge { font-family: 'Space Mono', monospace; font-size: 0.6rem; padding: 2px 8px; border-radius: 99px; border: 1px solid; }
        .model-badge.groq   { background: rgba(79,209,165,0.08); color: var(--groq);   border-color: rgba(79,209,165,0.25); }
        .model-badge.gemini { background: rgba(66,133,244,0.08); color: var(--gemini); border-color: rgba(66,133,244,0.25); }

        pre#sql_output {
            font-family: 'Space Mono', monospace; font-size: 0.8rem; color: var(--sql-col);
            padding: 18px; overflow-x: auto; line-height: 1.7; white-space: pre-wrap; word-break: break-word;
        }

        .table-wrap { overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; font-family: 'Space Mono', monospace; font-size: 0.75rem; }
        thead th {
            text-align: left; padding: 10px 18px; color: var(--text-dim); font-weight: 400;
            letter-spacing: 0.06em; border-bottom: 1px solid var(--border); white-space: nowrap;
        }
        tbody tr { border-bottom: 1px solid rgba(28,34,54,0.6); transition: background 0.1s; }
        tbody tr:last-child { border-bottom: none; }
        tbody tr:hover { background: rgba(122,162,212,0.04); }
        tbody td { padding: 9px 18px; color: var(--text); white-space: nowrap; }

        #chart { padding: 8px; }

        .error-banner {
            background: rgba(224,122,122,0.08); border: 1px solid rgba(224,122,122,0.25);
            border-radius: 12px; padding: 14px 18px; color: var(--error);
            font-family: 'Space Mono', monospace; font-size: 0.75rem; margin-bottom: 16px; display: none;
        }

        .hidden { display: none !important; }
    </style>
</head>
<body>
<div class="wrap">
    <header>
        <div class="logo-badge">⚡</div>
        <h1>NL <span>→</span> SQL</h1>
        <span class="tag">CLINIC DB · v1</span>
    </header>

    <div class="input-card">
        <div class="input-label">Your question</div>
        <textarea id="question" rows="3" placeholder="e.g. Which doctor has the most appointments?"></textarea>
        <div class="input-footer">
            <span class="hint" id="model-hint">Powered by SQLite</span>
            <button id="ask-btn" onclick="ask()">
                <span class="btn-text">Run Query</span>
                <span class="btn-arrow">→</span>
                <span class="spinner" id="spinner"></span>
            </button>
        </div>
    </div>

    <div class="error-banner" id="error-banner"></div>

    <div class="section hidden" id="sql-section">
        <div class="section-header">
            <span class="section-title"><span class="dot"></span>Generated SQL</span>
            <span class="model-badge hidden" id="model-badge"></span>
        </div>
        <pre id="sql_output"></pre>
    </div>

    <div class="section hidden" id="results-section">
        <div class="section-header">
            <span class="section-title"><span class="dot"></span>Results</span>
            <span class="row-badge" id="row-badge"></span>
        </div>
        <div class="table-wrap" id="table-wrap"></div>
    </div>

    <div class="section hidden" id="chart-section">
        <div class="section-header">
            <span class="section-title"><span class="dot"></span>Visualization</span>
        </div>
        <div id="chart"></div>
    </div>
</div>

<script>
function updateModelUI(modelUsed) {
    if (!modelUsed) return;
    const hint  = document.getElementById("model-hint");
    const badge = document.getElementById("model-badge");

    const isGroq   = modelUsed.toLowerCase().includes("groq");
    const isGemini = modelUsed.toLowerCase().includes("gemini");
    const cls = isGroq ? "groq" : isGemini ? "gemini" : "groq";

    hint.textContent = "Powered by " + modelUsed + " · SQLite";
    hint.className   = "hint " + cls;
    badge.textContent = modelUsed;
    badge.className   = "model-badge " + cls;
    badge.classList.remove("hidden");
}

async function ask() {
    const q = document.getElementById("question").value.trim();
    if (!q) return;

    const btn       = document.getElementById("ask-btn");
    const spinner   = document.getElementById("spinner");
    const arrow     = document.querySelector(".btn-arrow");
    const btnText   = document.querySelector(".btn-text");
    const errBanner = document.getElementById("error-banner");

    btn.disabled          = true;
    spinner.style.display = "block";
    arrow.style.display   = "none";
    btnText.textContent   = "Running…";

    ["sql-section","results-section","chart-section"].forEach(
        id => document.getElementById(id).classList.add("hidden")
    );
    document.getElementById("model-badge").classList.add("hidden");
    errBanner.style.display = "none";

    try {
        const res  = await fetch("/chat", {
            method:  "POST",
            headers: {"Content-Type": "application/json"},
            body:    JSON.stringify({question: q}),
        });
        const data = await res.json();

        if (!res.ok) {
            errBanner.textContent   = data.message || "Something went wrong.";
            errBanner.style.display = "block";
            return;
        }

        updateModelUI(data.model_used);

        if (data.sql_query) {
            document.getElementById("sql_output").textContent = data.sql_query;
            document.getElementById("sql-section").classList.remove("hidden");
        }

        const wrap = document.getElementById("table-wrap");
        wrap.innerHTML = "";
        if (data.columns?.length && data.rows?.length) {
            const tbl   = document.createElement("table");
            const thead = document.createElement("thead");
            const hrow  = document.createElement("tr");
            data.columns.forEach(c => {
                const th = document.createElement("th");
                th.textContent = c;
                hrow.appendChild(th);
            });
            thead.appendChild(hrow);
            tbl.appendChild(thead);

            const tbody = document.createElement("tbody");
            data.rows.forEach(row => {
                const tr = document.createElement("tr");
                row.forEach(cell => {
                    const td = document.createElement("td");
                    td.textContent = cell ?? "—";
                    tr.appendChild(td);
                });
                tbody.appendChild(tr);
            });
            tbl.appendChild(tbody);
            wrap.appendChild(tbl);
        } else {
            wrap.innerHTML = '<p style="padding:18px;font-family:Space Mono,monospace;font-size:.78rem;color:#5a6a8a;">No data found.</p>';
        }
        document.getElementById("row-badge").textContent = (data.row_count ?? 0) + " rows";
        document.getElementById("results-section").classList.remove("hidden");

        document.getElementById("chart").innerHTML = "";
        if (data.chart) {
            const layout = Object.assign({
                paper_bgcolor: "transparent",
                plot_bgcolor:  "transparent",
                font:   { family: "Space Mono, monospace", color: "#cdd8f0", size: 11 },
                margin: { t: 20, r: 20, b: 48, l: 48 },
                xaxis:  { gridcolor: "#1c2236", linecolor: "#1c2236" },
                yaxis:  { gridcolor: "#1c2236", linecolor: "#1c2236" },
            }, data.chart.layout || {});

            const traces = (data.chart.data || []).map(t =>
                t.type === "bar"
                    ? { ...t, marker: { color: "#7aa2d4" } }
                    : { ...t, line: { color: "#7aa2d4", width: 2 }, marker: { color: "#7aa2d4", size: 6 } }
            );

            Plotly.newPlot("chart", traces, layout, { responsive: true, displayModeBar: false });
            document.getElementById("chart-section").classList.remove("hidden");
        }

    } catch (e) {
        errBanner.textContent   = "Network error: " + e.message;
        errBanner.style.display = "block";
    } finally {
        btn.disabled          = false;
        spinner.style.display = "none";
        arrow.style.display   = "inline";
        btnText.textContent   = "Run Query";
    }
}

document.getElementById("question").addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") ask();
});
</script>
</body>
</html>
"""


# ── Dev entry point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
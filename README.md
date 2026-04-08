# Clinic NL2SQL — AI-Powered Natural Language to SQL System

**Cogninest AI — AI/ML Developer Intern Assignment | Round 1**

Ask questions in plain English about a clinic database and get back SQL queries, data results, and charts — without writing a single line of SQL.

---

## What This Builds

```
User: "Which doctor has the most appointments?"
         ↓
FastAPI → Vanna 2.0 Agent → LLM (Groq llama-3.3-70b) → SQL → clinic.db → JSON response
```

---

## LLM Provider Chosen

**Option B — Groq** (`llama-3.3-70b-versatile`)  
Free tier at [console.groq.com](https://console.groq.com). No credit card required.

To switch to Google Gemini: set `GOOGLE_API_KEY` in `.env` (and remove `GROQ_API_KEY`). The code auto-detects which key is present.

---

## Project Structure

```
project/
├── setup_database.py   # Creates clinic.db with 5 tables + dummy data
├── vanna_setup.py      # Vanna 2.0 Agent initialisation
├── seed_memory.py      # Pre-seeds 15 Q→SQL examples into agent memory
├── main.py             # FastAPI application (POST /chat, GET /health)
├── requirements.txt    # All dependencies
├── .env.example        # Template for API keys
├── .gitignore
├── README.md           # This file
├── RESULTS.md          # Test results for 20 questions
└── clinic.db           # Generated SQLite database (run setup_database.py)
```

---

## Setup Instructions

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/cogninest-nl2sql.git
cd cogninest-nl2sql
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Linux / macOS
# venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set your API key


cp .env.example .env
# Edit .env and paste your Groq API key:
# GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx


Get a free Groq key at [console.groq.com](https://console.groq.com) → API Keys → Create.

### 5. Create the database

```bash
python setup_database.py
```

Expected output:
```
Seeding doctors ...
Seeding patients ...
Seeding appointments ...
Seeding treatments ...
Seeding invoices ...
  patients: 200 rows
  doctors: 15 rows
  appointments: 500 rows
  treatments: 350 rows
  invoices: 300 rows

Done! Database saved to: clinic.db
```

### 6. Seed agent memory

```bash
python seed_memory.py
```

This pre-loads 15 verified question→SQL pairs so the agent has a head start.

### 7. Start the API server

```bash
uvicorn main:app --port 8000 --reload
```

The API is now live at **http://localhost:8000**

---

## API Documentation

### `POST /chat`

Ask a natural language question about the clinic data.

**Request:**
```json
{
  "question": "Show me the top 5 patients by total spending"
}
```

**Response:**
```json
{
  "message":    "Here are the top 5 patients by total spending...",
  "sql_query":  "SELECT p.first_name, p.last_name, SUM(i.total_amount) AS total_spent ...",
  "columns":    ["first_name", "last_name", "total_spent"],
  "rows":       [["Aarav", "Sharma", 7820.50], ["Priya", "Patel", 6910.00]],
  "row_count":  5,
  "chart":      { "data": [...], "layout": {...} },
  "chart_type": "bar",
  "cached":     false
}
```

**cURL example:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How many patients do we have?"}'
```

**Validation errors** (unsafe SQL) return HTTP 400:
```json
{
  "message": "The AI generated an unsafe query. Only SELECT queries are permitted."
}
```

---

### `GET /health`

Check server and database status.

**Response:**
```json
{
  "status":             "ok",
  "database":           "connected",
  "agent_memory_items": 15
}
```

**cURL example:**
```bash
curl http://localhost:8000/health
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│  FastAPI (main.py)                                  │
│  ├── POST /chat                                     │
│  │   ├── Input validation (Pydantic)                │
│  │   ├── Rate limiting (20 req/min per IP)          │
│  │   ├── Cache lookup (5 min TTL)                   │
│  │   ├── Vanna 2.0 Agent → LLM → SQL               │
│  │   ├── SQL Validator (SELECT only, no DDL)        │
│  │   ├── SqliteRunner → clinic.db                   │
│  │   ├── Plotly chart builder                       │
│  │   └── JSON response                              │
│  └── GET /health                                    │
│                                                     │
│  Vanna 2.0 Agent (vanna_setup.py)                  │
│  ├── LLM: Groq llama-3.3-70b (OpenAILlmService)   │
│  ├── Tools: RunSqlTool, VisualizeDataTool           │
│  ├── Memory: DemoAgentMemory (15 seeded examples)   │
│  └── DB: SqliteRunner → clinic.db                  │
│                                                     │
│  clinic.db (SQLite)                                 │
│  ├── patients (200 rows)                            │
│  ├── doctors (15 rows)                              │
│  ├── appointments (500 rows)                        │
│  ├── treatments (350 rows)                          │
│  └── invoices (300 rows)                            │
└─────────────────────────────────────────────────────┘
```

---

## Bonus Features Implemented

| Feature | Details |
|---|---|
| Chart generation | Plotly bar/line charts returned in response |
| Input validation | Pydantic model, min/max length, blank check |
| Query caching | 5-minute in-memory cache keyed by question hash |
| Rate limiting | 20 requests/minute per IP address |
| Structured logging | All requests and errors logged with timestamps |

---

## One-Command Run (for reviewers)

```bash
pip install -r requirements.txt && python setup_database.py \
  && python seed_memory.py && uvicorn main:app --port 8000
```

---

## Resources

- [Vanna AI Docs](https://vanna.ai/docs)
- [Vanna 2.0 Quickstart](https://vanna.ai/docs/tutorials/quickstart-5min)
- [Groq Console](https://console.groq.com)
- [FastAPI Docs](https://fastapi.tiangolo.com)

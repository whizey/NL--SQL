# NL → SQL — AI-Powered Clinic Query System

## What is this?

A Natural Language to SQL system built for a clinic database. Type a question in English — the system generates the SQL, runs it safely, and returns a table of results plus a chart.

**Built with:**
- 🧠 **Vanna 2.0** — AI agent with memory-based learning
- ⚡ **Groq** (`llama-3.3-70b-versatile`) — primary LLM, free tier
- 🔁 **Ollama** (`llama3.2`) — automatic local fallback
- 🚀 **FastAPI** — REST API + browser UI
- 🗄️ **SQLite** — lightweight clinic database
- 📊 **Plotly** — bar and line charts

---

## Demo

```
Question:  "Which doctor has the most appointments?"

Generated SQL:
  SELECT d.name, COUNT(a.id) AS total_appointments
  FROM doctors d
  JOIN appointments a ON d.id = a.doctor_id
  GROUP BY d.name
  ORDER BY total_appointments DESC
  LIMIT 1

Result:
  ┌──────────────────┬──────────────────────┐
  │ name             │ total_appointments   │
  ├──────────────────┼──────────────────────┤
  │ Dr. Priya Sharma │ 67                   │
  └──────────────────┴──────────────────────┘
```

---

## Table of Contents

- [Quick Start](#quick-start)
- [Setup](#setup)
- [Memory Seeding](#memory-seeding)
- [Running the Server](#running-the-server)
- [API Reference](#api-reference)
- [Architecture](#architecture)
- [Database Schema](#database-schema)
- [Project Structure](#project-structure)
- [Security](#security)
- [Bonus Features](#bonus-features)

---

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/nl2sql_project.git
cd nl2sql_project

python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

echo "GROQ_API_KEY=your_key_here" > .env

python setup_database.py
python seed_memory.py
uvicorn main:app --port 8000 --reload
```

Open **http://localhost:8000** in your browser.

> Get a free Groq API key at [console.groq.com](https://console.groq.com)

---

## Setup

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) — for local LLM fallback
- A free [Groq API key](https://console.groq.com)

### 1. Clone

```bash
git clone https://github.com/YOUR_USERNAME/nl2sql_project.git
cd nl2sql_project
```

### 2. Virtual environment

```bash
python -m venv venv
source venv/bin/activate      # macOS / Linux
venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
OLLAMA_MODEL=llama3.2
OLLAMA_URL=http://localhost:11434/v1
```

### 5. Start Ollama

```bash
ollama serve          # run in a separate terminal
ollama pull llama3.2  # ~2 GB download, only needed once
```

### 6. Create the database

```bash
python setup_database.py
```

<details>
<summary>Expected output</summary>

```
Seeding doctors ...
Seeding patients ...
Seeding appointments ...
Seeding treatments ...
Seeding invoices ...
  patients:     200 rows
  doctors:       15 rows
  appointments: 500 rows
  treatments:   350 rows
  invoices:     300 rows

Done! Database saved to: clinic.db
```

</details>

---

## Memory Seeding

Vanna 2.0 uses `DemoAgentMemory` instead of the old `vn.train()` pattern. This script pre-seeds **15 verified question→SQL pairs** so the agent has a strong head start before the first real query.

```bash
python seed_memory.py
```

<details>
<summary>Expected output</summary>

```
Seeding 15 Q→SQL pairs into agent memory...

  [01] OK  — How many patients are there?
  [02] OK  — List all patients from Mumbai
  [03] OK  — Count patients by gender
  [04] OK  — How many appointments does each doctor have?
  [05] OK  — Which doctor has the most appointments?
  [06] OK  — How many appointments are there by status?
  [07] OK  — Show appointments for the last 3 months
  [08] OK  — Show appointments grouped by month
  [09] OK  — What is the total revenue?
  [10] OK  — Show unpaid invoices
  [11] OK  — What is the average treatment cost?
  [12] OK  — Show revenue trend by month
  [13] OK  — How many appointments were completed last month?
  [14] OK  — List patients with more than 2 appointments
  [15] OK  — Show revenue by doctor

Done. Agent memory now has 15 items.
```

</details>

---

## Running the Server

```bash
uvicorn main:app --port 8000 --reload
```

| Endpoint | Description |
|----------|-------------|
| `http://localhost:8000` | Browser UI |
| `http://localhost:8000/chat` | `POST` — ask a question |
| `http://localhost:8000/health` | `GET` — liveness check |
| `http://localhost:8000/docs` | Swagger auto-docs |

---

## API Reference

### `POST /chat`

Ask a natural language question about the clinic data.

**Request**

```json
{
  "question": "Show me the top 5 patients by total spending"
}
```

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `question` | `string` | ✅ | min 3 · max 500 chars |

**Response `200 OK`**

```json
{
  "message":    "Here are your results.",
  "sql_query":  "SELECT p.first_name, p.last_name, SUM(i.total_amount) AS total_spent FROM patients p JOIN invoices i ON p.id = i.patient_id GROUP BY p.id ORDER BY total_spent DESC LIMIT 5",
  "model_used": "Groq · llama-3.3-70b",
  "columns":    ["first_name", "last_name", "total_spent"],
  "rows":       [
    ["Aarav",  "Sharma", 7820.50],
    ["Priya",  "Patel",  6910.00]
  ],
  "row_count":  5,
  "chart":      { "data": [...], "layout": {...} },
  "chart_type": "bar",
  "cached":     false
}
```

**Error responses**

| Status | When | Example message |
|--------|------|-----------------|
| `400` | Unsafe SQL generated | `"Blocked SQL: Only SELECT queries are allowed."` |
| `422` | SQL execution failed | `"no such column: t.doctor_id"` |
| `429` | Rate limit exceeded | `"Too many requests — slow down."` |
| `500` | LLM failed | `"LLM error: ..."` |
| `503` | Both LLMs down | `"Both Groq and Ollama failed."` |

**cURL**

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How many patients do we have?"}'
```

---

### `GET /health`

Check server and database status.

**Response `200 OK`**

```json
{
  "status":             "ok",
  "database":           "connected",
  "agent_memory_items": 15
}
```

**cURL**

```bash
curl http://localhost:8000/health
```

---

## Architecture

```
                         ┌──────────────┐
                         │  Browser UI  │
                         │   / cURL     │
                         └──────┬───────┘
                                │ POST /chat
                                ▼
                    ┌───────────────────────┐
                    │       FastAPI          │
                    │  ┌─────────────────┐  │
                    │  │ Pydantic schema │  │
                    │  │ Rate limiter    │  │
                    │  │ Cache (5 min)   │  │
                    │  └────────┬────────┘  │
                    └───────────┼───────────┘
                                │
                    ┌───────────▼───────────┐
                    │       LLM Layer        │
                    │                       │
                    │  Groq (primary)   ──► │ llama-3.3-70b
                    │       │ (on fail) ──► │
                    │  Ollama (fallback) ──►│ llama3.2 local
                    └───────────┬───────────┘
                                │ Raw SQL
                    ┌───────────▼───────────┐
                    │    SQL Validator       │
                    │  SELECT only           │
                    │  No DDL / DML          │
                    │  No system tables      │
                    └───────────┬───────────┘
                                │ Safe SQL
                    ┌───────────▼───────────┐
                    │     clinic.db          │
                    │     (SQLite)           │
                    └───────────┬───────────┘
                                │ Rows + Columns
                    ┌───────────▼───────────┐
                    │   Plotly Chart Builder │
                    │  Bar · Line            │
                    └───────────┬───────────┘
                                │
                         JSON Response
```

**Vanna 2.0 Agent setup (`vanna_setup.py`)**

```
OpenAILlmService (Groq)
    │
    ├── RunSqlTool                     → executes SQL via SqliteRunner
    ├── VisualizeDataTool              → chart generation
    ├── SaveQuestionToolArgsTool       → saves correct Q→SQL to memory
    └── SearchSavedCorrectToolUsesTool → retrieves similar past queries

DemoAgentMemory  →  15 pre-seeded Q→SQL examples
DefaultUserResolver  →  single default user
```

---

## Database Schema

```
patients
  id · first_name · last_name · email · phone
  date_of_birth · gender · city · registered_date
        │
        │ patient_id                    patient_id
        ├─────────────────┐        ┌────────────────
        │                 │        │
appointments          invoices
  id                    id
  patient_id (FK)       patient_id (FK)
  doctor_id  (FK)       invoice_date
  appointment_date      total_amount
  status                paid_amount
  notes                 status
        │
        │ doctor_id
        │
doctors
  id · name · specialization · department · phone
        │
        │ appointment_id
        │
treatments
  id · appointment_id (FK)
  treatment_name · cost · duration_minutes
```

**Appointment status values:** `Scheduled` · `Completed` · `Cancelled` · `No-Show`

**Invoice status values:** `Paid` · `Pending` · `Overdue`

---

## Project Structure

```
nl2sql_project/
├── main.py              # FastAPI app — routes, LLM, SQL execution, UI
├── vanna_setup.py       # Vanna 2.0 Agent initialisation
├── setup_database.py    # Schema creation + dummy data seeding
├── seed_memory.py       # Pre-seeds 15 Q→SQL pairs into agent memory
├── requirements.txt     # All Python dependencies
├── .env                 # Secret keys (not committed)
├── .env.example         # Template for .env
├── .gitignore
├── README.md            # This file
├── RESULTS.md           # Test results for all 20 assignment questions
└── clinic.db            # Generated SQLite database
```

---

## Security

Every SQL string produced by the LLM is validated before it touches the database.

| Check | Blocked values |
|-------|---------------|
| Statement type | Anything that is not `SELECT` |
| DML keywords | `INSERT` `UPDATE` `DELETE` `DROP` `ALTER` `TRUNCATE` `CREATE` |
| Dangerous functions | `EXEC` `EXECUTE` `xp_` `sp_` `GRANT` `REVOKE` `SHUTDOWN` |
| System tables | `sqlite_master` `sqlite_sequence` `sqlite_stat*` `information_schema` |

If validation fails, the query is **rejected immediately** — it never reaches the database.

---

## Bonus Features

| Feature | Detail |
|---------|--------|
| 📊 Chart generation | Plotly bar (categorical) and line (time-series) returned in every response |
| ✅ Input validation | Pydantic with min/max length and blank check |
| ⚡ Query caching | MD5-keyed 5-minute in-memory cache — identical questions return instantly |
| 🚦 Rate limiting | Sliding-window 20 req / 60 s per IP |
| 📋 Structured logging | Timestamped logs for every request, LLM call, SQL, and error |
| 🔀 Automatic LLM fallback | Groq → Ollama on any failure — zero manual intervention |
| 🏷️ Model indicator | UI badge shows which model answered — green (Groq) · blue (Ollama) |

---

## Resources

- [Vanna AI Docs](https://vanna.ai/docs)
- [Vanna 2.0 Quickstart](https://vanna.ai/docs/tutorials/quickstart-5min)
- [Groq Console](https://console.groq.com)
- [FastAPI Docs](https://fastapi.tiangolo.com)
- [Ollama](https://ollama.com)
- [Plotly Python](https://plotly.com/python)

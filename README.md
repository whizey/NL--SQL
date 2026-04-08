# NL → SQL — Ask Your Database in Plain English

## What does this do?

You type a question in plain English. The system figures out the right SQL, runs it on a clinic database, and gives you back a table of results — plus a chart if it makes sense.

No SQL knowledge needed. No manual query writing. Just ask.

```
You:    "Which doctor has the most appointments?"

System: SELECT d.name, COUNT(a.id) AS total
        FROM doctors d
        JOIN appointments a ON d.id = a.doctor_id
        GROUP BY d.name ORDER BY total DESC LIMIT 1

Result: Dr. Priya Sharma — 67 appointments  📊
```

---

## How it works (simple version)

```
Your question
     ↓
FastAPI receives it
     ↓
Groq LLM (llama-3.3-70b) converts it to SQL
     ↓  (if Groq fails → Gemini 2.0 Flash takes over automatically)
SQL is validated — dangerous queries are blocked
     ↓
SQLite runs the query on clinic.db
     ↓
Results + chart sent back to you
```

---

## LLM Setup

| Role | Provider | Model | Cost |
|------|----------|-------|------|
| Primary | [Groq](https://console.groq.com) | `llama-3.3-70b-versatile` | Free tier |
| Fallback | [Google Gemini](https://aistudio.google.com/apikey) | `gemini-2.0-flash` | Free, no daily limit |

The system **automatically switches** to Gemini if Groq hits its rate limit — zero manual intervention needed. The UI shows a badge telling you which model answered.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Full Setup](#full-setup)
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

# Add your API keys
echo "GROQ_API_KEY=your_groq_key" >> .env
echo "GOOGLE_API_KEY=your_gemini_key" >> .env

python setup_database.py
python seed_memory.py
uvicorn main:app --port 8000 --reload
```

Open **http://localhost:8000** — start asking questions.

---

## Full Setup

### Prerequisites

- Python 3.10+
- A free [Groq API key](https://console.groq.com) — takes 2 minutes
- A free [Gemini API key](https://aistudio.google.com/apikey) — sign in with Google

### Step 1 — Clone

```bash
git clone https://github.com/YOUR_USERNAME/nl2sql_project.git
cd nl2sql_project
```

### Step 2 — Virtual environment

```bash
python -m venv venv
source venv/bin/activate      # macOS / Linux
venv\Scripts\activate         # Windows
```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Create your `.env` file

```env
# Primary LLM — get free key at console.groq.com
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx

# Fallback LLM — get free key at aistudio.google.com/apikey
GOOGLE_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxx
```

### Step 5 — Create the database

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

Vanna 2.0 learns from examples stored in its memory. This script pre-loads **15 verified question→SQL pairs** so the agent already knows common patterns before you ask your first question.

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

> **Note:** Vanna 2.0 does NOT use the old `vn.train()` method from Vanna 0.x. It uses `DemoAgentMemory` instead — a completely different system.

---

## Running the Server

```bash
uvicorn main:app --port 8000 --reload
```

| URL | What it does |
|-----|-------------|
| `http://localhost:8000` | Browser UI — type questions here |
| `http://localhost:8000/chat` | `POST` API endpoint |
| `http://localhost:8000/health` | Check if everything is running |
| `http://localhost:8000/docs` | Auto-generated API docs |

---

## API Reference

### `POST /chat`

Send a plain English question, get SQL + results + chart back.

**Request:**
```json
{
  "question": "Show me the top 5 patients by total spending"
}
```

**Response:**
```json
{
  "message":    "Here are your results.",
  "sql_query":  "SELECT p.first_name, p.last_name, SUM(i.total_amount) AS total_spent FROM patients p JOIN invoices i ON p.id = i.patient_id GROUP BY p.id ORDER BY total_spent DESC LIMIT 5",
  "model_used": "Groq · llama-3.3-70b",
  "columns":    ["first_name", "last_name", "total_spent"],
  "rows":       [["Aarav", "Sharma", 7820.50], ["Priya", "Patel", 6910.00]],
  "row_count":  5,
  "chart":      { "data": [...], "layout": {...} },
  "chart_type": "bar",
  "cached":     false
}
```

**Error responses:**

| Status | Meaning |
|--------|---------|
| `400` | SQL was unsafe — blocked before execution |
| `422` | SQL ran but hit a database error |
| `429` | Too many requests — slow down |
| `503` | Both Groq and Gemini failed — check your API keys |

**cURL example:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How many patients do we have?"}'
```

---

### `GET /health`

```bash
curl http://localhost:8000/health
```

```json
{
  "status":             "ok",
  "database":           "connected",
  "agent_memory_items": 15
}
```

---

## Architecture

```
Your question (browser or API)
         │
         ▼
┌─────────────────────────────────────┐
│            FastAPI                  │
│  • Validates input (Pydantic)       │
│  • Checks rate limit (20/min)       │
│  • Checks cache (5-min TTL)         │
└─────────────┬───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│           LLM Layer                 │
│  Primary  → Groq llama-3.3-70b     │
│  Fallback → Gemini 2.0 Flash       │
│  (auto-switches on any failure)     │
└─────────────┬───────────────────────┘
              │ raw SQL
              ▼
┌─────────────────────────────────────┐
│         SQL Validator               │
│  • SELECT only                      │
│  • No DROP / DELETE / ALTER         │
│  • No system tables                 │
└─────────────┬───────────────────────┘
              │ safe SQL
              ▼
┌─────────────────────────────────────┐
│       SQLite  (clinic.db)           │
└─────────────┬───────────────────────┘
              │ rows + columns
              ▼
┌─────────────────────────────────────┐
│      Plotly Chart Builder           │
│  Bar chart or Line chart            │
└─────────────┬───────────────────────┘
              │
              ▼
         JSON Response
```

**Vanna 2.0 Agent** (`vanna_setup.py`):

| Component | What it does |
|-----------|-------------|
| `OpenAILlmService` | Connects to Groq (OpenAI-compatible API) |
| `SqliteRunner` | Runs queries on `clinic.db` |
| `DemoAgentMemory` | Stores and retrieves example Q→SQL pairs |
| `RunSqlTool` | Executes the generated SQL |
| `VisualizeDataTool` | Handles chart generation |
| `SaveQuestionToolArgsTool` | Saves correct queries to memory |
| `SearchSavedCorrectToolUsesTool` | Finds similar past queries |

---

## Database Schema

```
patients    (id, first_name, last_name, email, phone, date_of_birth, gender, city, registered_date)
doctors     (id, name, specialization, department, phone)
appointments(id, patient_id, doctor_id, appointment_date, status, notes)
treatments  (id, appointment_id, treatment_name, cost, duration_minutes)
invoices    (id, patient_id, invoice_date, total_amount, paid_amount, status)
```

**Data:** 200 patients · 15 doctors · 500 appointments · 350 treatments · 300 invoices

**Status values:**
- appointments: `Scheduled` `Completed` `Cancelled` `No-Show`
- invoices: `Paid` `Pending` `Overdue`

---

## Project Structure

```
nl2sql_project/
├── main.py              # FastAPI app — all routes, LLM calls, UI
├── vanna_setup.py       # Vanna 2.0 Agent setup
├── setup_database.py    # Creates clinic.db + inserts dummy data
├── seed_memory.py       # Loads 15 Q→SQL examples into agent memory
├── requirements.txt     # Python packages
├── .env                 # Your API keys (never commit this)
├── .env.example         # Template showing what keys are needed
├── .gitignore
├── README.md            # This file
├── RESULTS.md           # Test results for all 20 questions
└── clinic.db            # SQLite database (auto-generated)
```

---

## Security

Every SQL query generated by the LLM is checked before it touches the database:

| What's checked | What's blocked |
|----------------|----------------|
| Statement type | Anything that isn't `SELECT` |
| Write operations | `INSERT` `UPDATE` `DELETE` `DROP` `ALTER` `TRUNCATE` `CREATE` |
| Dangerous functions | `EXEC` `xp_` `sp_` `GRANT` `REVOKE` `SHUTDOWN` |
| System tables | `sqlite_master` `sqlite_sequence` `information_schema` |

If a query fails validation it is **rejected immediately** — it never reaches the database.

API keys are loaded from `.env` and never hardcoded anywhere in the source code.

---

## Bonus Features

| Feature | How it works |
|---------|-------------|
| 📊 Charts | Plotly bar charts for rankings, line charts for trends — returned in every response |
| ✅ Input validation | Pydantic rejects blank questions, enforces min 3 / max 500 characters |
| ⚡ Query caching | Same question asked twice? Served from cache in milliseconds (5-min TTL) |
| 🚦 Rate limiting | Max 20 requests per 60 seconds per IP — prevents abuse |
| 📋 Logging | Every request, LLM call, SQL query, and error is timestamped and logged |
| 🔀 Auto LLM fallback | Groq hits rate limit → Gemini takes over automatically, no downtime |
| 🏷️ Model badge | UI shows exactly which model answered — green for Groq, blue for Gemini |

---

## One-Command Setup (for reviewers)

```bash
pip install -r requirements.txt && python setup_database.py \
&& python seed_memory.py && uvicorn main:app --port 8000
```

---

## Resources

- [Vanna AI Docs](https://vanna.ai/docs)
- [Vanna 2.0 Quickstart](https://vanna.ai/docs/tutorials/quickstart-5min)
- [Groq Console](https://console.groq.com)
- [Google AI Studio](https://aistudio.google.com/apikey)
- [FastAPI Docs](https://fastapi.tiangolo.com)
- [Plotly Python](https://plotly.com/python)

---

<div align="center">
Built with ❤️ for the Cogninest AI internship assignment · April 2026
</div>

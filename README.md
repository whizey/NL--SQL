# NL → SQL — Ask Your Database in Plain English

> Built for the **Cogninest AI** · AI/ML Developer Intern Assignment · Round 1

![Python](https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-latest-009688?logo=fastapi&logoColor=white)
![Vanna](https://img.shields.io/badge/Vanna-2.0.x-purple)
![Groq](https://img.shields.io/badge/Primary-Groq%20llama--3.3--70b-orange)
![Gemini](https://img.shields.io/badge/Fallback-Gemini%202.0%20Flash-4285f4)
![SQLite](https://img.shields.io/badge/database-SQLite-003B57?logo=sqlite&logoColor=white)

---

## Project Description

**NL → SQL** is a Natural Language to SQL chatbot built with **FastAPI** and **Vanna 2.0**. It lets clinic staff ask questions in plain English and get results from a SQLite database — without writing a single line of SQL.

The system takes your question, converts it to SQL using a large language model, validates the query for safety, runs it on the database, and returns a table of results along with an interactive chart.

```
You type:   "Which doctor has the most appointments?"

System generates:
  SELECT d.name, COUNT(a.id) AS total
  FROM doctors d
  JOIN appointments a ON d.id = a.doctor_id
  GROUP BY d.name ORDER BY total DESC LIMIT 1

You get:    Dr. Priya Sharma — 67 appointments  [+ bar chart]
```

**LLM setup:**
- **Primary:** Groq `llama-3.3-70b-versatile` — fast, free tier
- **Fallback:** Google Gemini `gemini-2.0-flash` — kicks in automatically if Groq hits its rate limit

> **Note for reviewers:** This is a locally-run API. Clone the repo, follow the setup steps below, and the server will run at `http://localhost:8000` on your machine.

---

## Table of Contents

- [Project Description](#project-description)
- [Setup Instructions](#setup-instructions)
- [How to Run the Memory Seeding Script](#how-to-run-the-memory-seeding-script)
- [How to Start the API Server](#how-to-start-the-api-server)
- [API Documentation](#api-documentation)
- [Architecture Overview](#architecture-overview)
- [Database Schema](#database-schema)
- [Project Structure](#project-structure)
- [Security](#security)
- [Bonus Features](#bonus-features)

---

## Setup Instructions

### Prerequisites

- Python 3.10+
- A free [Groq API key](https://console.groq.com) — sign up, takes 2 minutes
- A free [Gemini API key](https://aistudio.google.com/apikey) — sign in with Google

### Step 1 — Clone the repository

```bash
git clone https://github.com/whizey/NL--SQL.git
cd NL--SQL
```

### Step 2 — Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows
```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Set up your API keys

Create a `.env` file in the project root:

```env
# Primary LLM — get free key at console.groq.com
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx

# Fallback LLM — get free key at aistudio.google.com/apikey
GOOGLE_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxx
```

> The system uses Groq by default. If Groq hits its daily limit, it automatically switches to Gemini — no manual changes needed.

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

## How to Run the Memory Seeding Script

Vanna 2.0 uses `DemoAgentMemory` to learn from examples. This script pre-loads **15 verified question→SQL pairs** into the agent's memory so it performs well from the very first query.

> **Important:** Run this after `setup_database.py` — the database must exist first.

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

The 15 pairs cover all required categories — patient queries, doctor queries, appointment queries, financial queries, and time-based queries.

> **Vanna 2.0 note:** This does NOT use the old `vn.train(ddl=..., sql=...)` pattern from Vanna 0.x. Vanna 2.0 uses `DemoAgentMemory` and `save_tool_usage` instead — a completely different architecture.

---

## How to Start the API Server

```bash
uvicorn main:app --port 8000 --reload
```

The server starts at **http://localhost:8000**

| URL | Description |
|-----|-------------|
| `http://localhost:8000` | Browser UI — type questions here |
| `http://localhost:8000/chat` | `POST` endpoint for API calls |
| `http://localhost:8000/health` | Health check |
| `http://localhost:8000/docs` | Auto-generated Swagger docs |

**One-command setup for reviewers:**

```bash
pip install -r requirements.txt && python setup_database.py \
&& python seed_memory.py && uvicorn main:app --port 8000
```

---

## API Documentation

### `POST /chat`

Converts a plain English question into SQL, executes it, and returns results with an optional chart.

**Request body:**

```json
{
  "question": "Show me the top 5 patients by total spending"
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `question` | string | ✅ | min 3 chars, max 500 chars |

**Success response `200 OK`:**

```json
{
  "message":    "Here are your results.",
  "sql_query":  "SELECT p.first_name, p.last_name, SUM(i.total_amount) AS total_spent FROM patients p JOIN invoices i ON p.id = i.patient_id GROUP BY p.id ORDER BY total_spent DESC LIMIT 5",
  "model_used": "Groq · llama-3.3-70b",
  "columns":    ["first_name", "last_name", "total_spent"],
  "rows":       [
    ["Aarav",  "Sharma", 7820.50],
    ["Priya",  "Patel",  6910.00],
    ["Rahul",  "Gupta",  6540.75]
  ],
  "row_count":  5,
  "chart":      { "data": [...], "layout": {...} },
  "chart_type": "bar",
  "cached":     false
}
```

**Error responses:**

| Status | When it happens | Example message |
|--------|----------------|-----------------|
| `400` | SQL was unsafe — blocked before running | `"Blocked SQL: Only SELECT queries are allowed."` |
| `422` | SQL ran but hit a database error | `"no such column: t.doctor_id"` |
| `429` | Too many requests | `"Too many requests — slow down."` |
| `503` | Both Groq and Gemini failed | `"Both Groq and Gemini failed. Check your API keys."` |

**cURL example:**

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How many patients do we have?"}'
```

---

### `GET /health`

Checks that the server is running and the database is reachable.

**Response `200 OK`:**

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
User (browser or API client)
          │
          ▼
┌─────────────────────────────────────────┐
│              FastAPI (main.py)          │
│                                         │
│  1. Validate input (Pydantic)           │
│  2. Check rate limit (20 req / 60s)     │
│  3. Check cache (5-min TTL)             │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│              LLM Layer                  │
│                                         │
│  Primary  → Groq llama-3.3-70b         │
│  Fallback → Gemini 2.0 Flash           │
│  (auto-switches on rate limit or error) │
└──────────────┬──────────────────────────┘
               │ raw SQL
               ▼
┌─────────────────────────────────────────┐
│           SQL Validator                 │
│                                         │
│  ✓ SELECT only                          │
│  ✗ INSERT / UPDATE / DELETE / DROP      │
│  ✗ EXEC / xp_ / GRANT / SHUTDOWN       │
│  ✗ sqlite_master / system tables        │
└──────────────┬──────────────────────────┘
               │ safe SQL
               ▼
┌─────────────────────────────────────────┐
│          SQLite (clinic.db)             │
│  patients · doctors · appointments      │
│  treatments · invoices                  │
└──────────────┬──────────────────────────┘
               │ rows + columns
               ▼
┌─────────────────────────────────────────┐
│        Plotly Chart Builder             │
│  Bar chart → rankings / comparisons     │
│  Line chart → time-series / trends      │
└──────────────┬──────────────────────────┘
               │
               ▼
          JSON Response
```

**Vanna 2.0 Agent** (`vanna_setup.py`):

| Component | Role |
|-----------|------|
| `OpenAILlmService` | Connects to Groq (OpenAI-compatible API) |
| `SqliteRunner` | Runs SQL queries on `clinic.db` |
| `DemoAgentMemory` | Stores and retrieves example Q→SQL pairs |
| `RunSqlTool` | Executes the generated SQL |
| `VisualizeDataTool` | Handles chart generation |
| `SaveQuestionToolArgsTool` | Saves correct queries to memory |
| `SearchSavedCorrectToolUsesTool` | Finds similar past queries |

---

## Database Schema

```sql
patients    (id, first_name, last_name, email, phone, date_of_birth, gender, city, registered_date)
doctors     (id, name, specialization, department, phone)
appointments(id, patient_id, doctor_id, appointment_date, status, notes)
            -- status: 'Scheduled' | 'Completed' | 'Cancelled' | 'No-Show'
treatments  (id, appointment_id, treatment_name, cost, duration_minutes)
invoices    (id, patient_id, invoice_date, total_amount, paid_amount, status)
            -- status: 'Paid' | 'Pending' | 'Overdue'
```

**Data volumes:** 200 patients · 15 doctors · 500 appointments · 350 treatments · 300 invoices

---

## Project Structure

```
nl2sql_project/
├── main.py              # FastAPI app — routes, LLM calls, SQL execution, browser UI
├── vanna_setup.py       # Vanna 2.0 Agent initialisation
├── setup_database.py    # Creates clinic.db schema + inserts all dummy data
├── seed_memory.py       # Pre-seeds 15 Q→SQL pairs into agent memory
├── requirements.txt     # All Python dependencies
├── .env                 # Your API keys — never commit this file
├── .gitignore           # Excludes .env, venv, __pycache__, clinic.db
├── README.md            # This file
├── RESULTS.md           # Test results for all 20 assignment questions
└── clinic.db            # SQLite database (auto-generated by setup_database.py)
```

---

## Security

All SQL generated by the LLM is validated before it ever reaches the database:

| Check | Blocked values |
|-------|----------------|
| Statement type | Anything that is not `SELECT` |
| Write operations | `INSERT` `UPDATE` `DELETE` `DROP` `ALTER` `TRUNCATE` `CREATE` |
| Dangerous functions | `EXEC` `EXECUTE` `xp_` `sp_` `GRANT` `REVOKE` `SHUTDOWN` |
| System tables | `sqlite_master` `sqlite_sequence` `information_schema` |

If validation fails the query is rejected immediately — it never reaches the database.

API keys are stored in `.env` and never hardcoded anywhere in the source code.

---

## Bonus Features

| Feature | Details |
|---------|---------|
| 📊 Chart generation | Plotly bar and line charts returned in every response |
| ✅ Input validation | Pydantic with min/max length and blank-check validator |
| ⚡ Query caching | MD5-keyed 5-minute in-memory cache — same question returns instantly |
| 🚦 Rate limiting | Sliding window — 20 requests per 60 seconds per IP |
| 📋 Structured logging | Timestamped logs for every request, LLM call, SQL, and error |
| 🔀 Automatic LLM fallback | Groq → Gemini on any failure — zero downtime, zero manual intervention |
| 🏷️ Model indicator | UI badge shows which model answered — green for Groq, blue for Gemini |

---

## Resources

- [Vanna AI Documentation](https://vanna.ai/docs)
- [Vanna 2.0 Quickstart](https://vanna.ai/docs/tutorials/quickstart-5min)
- [Groq Console](https://console.groq.com)
- [Google AI Studio](https://aistudio.google.com/apikey)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Plotly Python](https://plotly.com/python)

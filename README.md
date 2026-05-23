# NL → SQL — Enterprise Query Engine with LLM Orchestration

> Production-grade Natural Language to SQL system with intelligent LLM routing, RAG-enhanced query generation, and multi-model fallback architecture.

![Python](https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-latest-009688?logo=fastapi&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-0.1.x-green?logo=python&logoColor=white)
![Vanna](https://img.shields.io/badge/Vanna-2.0.x-purple)
![Groq](https://img.shields.io/badge/Primary-Groq%20llama--3.3--70b-orange)
![Gemini](https://img.shields.io/badge/Fallback-Gemini%202.0%20Flash-4285f4)
![SQLite](https://img.shields.io/badge/database-SQLite-003B57?logo=sqlite&logoColor=white)

---

## Project Overview

**NL → SQL** is a production-grade semantic query engine that converts natural language into database queries with high accuracy and reliability. Built with **FastAPI**, **LangChain**, and **Vanna 2.0**, the system bridges the gap between non-technical users and complex databases.

**Core capability:** Ask your database questions in plain English — the system generates optimal SQL, validates for security, executes, and returns structured results with interactive visualizations.

User input:      "Which doctor has the most appointments?"
System pipeline:

Parse question → LangChain semantic router
Retrieve similar Q→SQL pairs from vector memory (RAG)
Generate SQL via Groq llama-3.3-70b with few-shot examples
Validate for SQL injection / dangerous operations
Execute on clinic database
Auto-detect chart type (bar, line, table)
Return structured JSON + Plotly visualization

Output:          Dr. Priya Sharma — 67 appointments
[Interactive bar chart with trend analysis]

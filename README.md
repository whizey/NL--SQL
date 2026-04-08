# NL--SQL
AI-Powered Natural Language to SQL System

Overview
NL → SQL is a production-ready Natural Language to SQL chatbot that allows clinic staff to query a SQLite database using plain English — no SQL knowledge required. The system translates natural language questions into validated SQL queries, executes them safely, and returns structured results with interactive Plotly visualizations.

DEMO
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

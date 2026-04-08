"""
seed_memory.py
Pre-seeds DemoAgentMemory with 15 verified question→SQL pairs so the
Vanna 2.0 agent has strong examples before the first real user request.

Run once after setup_database.py:
    python seed_memory.py
"""

import asyncio
import uuid
from vanna_setup import agent
from vanna.core.user import RequestContext, User

# ── 15 verified Q→SQL pairs covering all required categories ─────────────────
QA_PAIRS = [

# ── Patient Queries ─────────────────────────────────────────────

{
    "question": "How many patients are there?",
    "sql": "SELECT COUNT(*) FROM patients;",
},
{
    "question": "List all patients from Mumbai",
    "sql": "SELECT * FROM patients WHERE city = 'Mumbai';",
},
{
    "question": "Count patients by gender",
    "sql": "SELECT gender, COUNT(*) FROM patients GROUP BY gender;",
},

# ── Doctor Queries ──────────────────────────────────────────────

{
    "question": "How many appointments does each doctor have?",
    "sql": "SELECT doctor_id, COUNT(*) FROM appointments GROUP BY doctor_id;",
},
{
    "question": "Which doctor has the most appointments?",
    "sql": "SELECT doctor_id, COUNT(*) AS total FROM appointments GROUP BY doctor_id ORDER BY total DESC LIMIT 1;",
},

# ── Appointment Queries ─────────────────────────────────────────

{
    "question": "How many appointments are there by status?",
    "sql": "SELECT status, COUNT(*) FROM appointments GROUP BY status;",
},
{
    "question": "Show appointments for the last 3 months",
    "sql": "SELECT * FROM appointments WHERE appointment_date >= DATE('now', '-3 months');",
},
{
    "question": "Show appointments grouped by month",
    "sql": "SELECT strftime('%Y-%m', appointment_date), COUNT(*) FROM appointments GROUP BY 1;",
},

# ── Financial Queries ───────────────────────────────────────────

{
    "question": "What is the total revenue?",
    "sql": "SELECT SUM(total_amount) FROM invoices;",
},
{
    "question": "Show unpaid invoices",
    "sql": "SELECT * FROM invoices WHERE status IN ('Pending', 'Overdue');",
},
{
    "question": "What is the average treatment cost?",
    "sql": "SELECT AVG(cost) FROM treatments;",
},

# ── Time-based Queries ──────────────────────────────────────────

{
    "question": "Show revenue trend by month",
    "sql": "SELECT strftime('%Y-%m', invoice_date), SUM(total_amount) FROM invoices GROUP BY 1;",
},
{
    "question": "How many appointments were completed last month?",
    "sql": "SELECT COUNT(*) FROM appointments WHERE status = 'Completed' AND appointment_date >= DATE('now', '-1 month');",
},

# ── Extra Coverage (important for generalization) ────────────────

{
    "question": "List patients with more than 2 appointments",
    "sql": "SELECT patient_id FROM appointments GROUP BY patient_id HAVING COUNT(*) > 2;",
},
{
    "question": "Show revenue by doctor",
    "sql": "SELECT a.doctor_id, SUM(i.total_amount) FROM invoices i JOIN appointments a ON i.patient_id = a.patient_id GROUP BY a.doctor_id;",
},

]
async def seed():
    """Injects all Q→SQL pairs into the agent's DemoAgentMemory."""
    print(f"Seeding {len(QA_PAIRS)} Q→SQL pairs into agent memory...\n")

    from vanna.core.tool import ToolContext
    from vanna.core.user import User
    import uuid

    ctx = ToolContext(
        user=User(
            id="seed-script",
            email="seed@clinic.local",
            group_memberships=["users"],
        ),
        conversation_id=str(uuid.uuid4()),
        request_id=str(uuid.uuid4()),
        agent_memory=agent.agent_memory,
    )

    for i, pair in enumerate(QA_PAIRS, 1):
        q   = pair["question"]
        sql = pair["sql"]
        try:
            await agent.agent_memory.save_tool_usage(
                question=q,
                tool_name="run_sql",
                args={"sql": sql},
                context=ctx,
                success=True,
            )
            print(f"  [{i:02d}] OK  — {q}")
        except Exception as e:
            print(f"  [{i:02d}] ERR — {q}\n        {e}")

    total = len(agent.agent_memory._memories)
    print(f"\nDone. Agent memory now has {total} items.")


if __name__ == "__main__":
    asyncio.run(seed())



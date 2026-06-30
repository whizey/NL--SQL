"""
knowledge_base.py
The 15 verified question -> SQL pairs that power retrieval-augmented generation.
Each pair has been hand-checked against the clinic schema and confirmed to run.
These are retrieved at query time and injected as few-shot examples.
"""

VERIFIED_PAIRS = [
    {"q": "How many patients are there?",
     "sql": "SELECT COUNT(*) AS patient_count FROM patients"},
    {"q": "List all patients from Mumbai",
     "sql": "SELECT first_name, last_name, city FROM patients WHERE city = 'Mumbai'"},
    {"q": "Count patients by gender",
     "sql": "SELECT gender, COUNT(*) AS count FROM patients GROUP BY gender"},
    {"q": "How many appointments does each doctor have?",
     "sql": "SELECT d.name, COUNT(a.id) AS appointment_count FROM doctors d JOIN appointments a ON d.id = a.doctor_id GROUP BY d.id ORDER BY appointment_count DESC"},
    {"q": "Which doctor has the most appointments?",
     "sql": "SELECT d.name, COUNT(a.id) AS appointment_count FROM doctors d JOIN appointments a ON d.id = a.doctor_id GROUP BY d.id ORDER BY appointment_count DESC LIMIT 1"},
    {"q": "How many appointments are there by status?",
     "sql": "SELECT status, COUNT(*) AS count FROM appointments GROUP BY status"},
    {"q": "What is the total revenue?",
     "sql": "SELECT SUM(total_amount) AS total_revenue FROM invoices"},
    {"q": "Show unpaid invoices",
     "sql": "SELECT id, patient_id, total_amount, status FROM invoices WHERE status IN ('Pending', 'Overdue')"},
    {"q": "What is the average treatment cost?",
     "sql": "SELECT AVG(cost) AS avg_treatment_cost FROM treatments"},
    {"q": "Show revenue by doctor",
     "sql": "SELECT d.name, SUM(i.total_amount) AS revenue FROM doctors d JOIN invoices i ON d.id = i.doctor_id GROUP BY d.id ORDER BY revenue DESC"},
    {"q": "List patients with more than 2 appointments",
     "sql": "SELECT p.first_name, p.last_name, COUNT(a.id) AS appt_count FROM patients p JOIN appointments a ON p.id = a.patient_id GROUP BY p.id HAVING COUNT(a.id) > 2"},
    {"q": "What is the average invoice amount per patient?",
     "sql": "SELECT p.first_name, p.last_name, AVG(i.total_amount) AS avg_invoice FROM patients p JOIN invoices i ON p.id = i.patient_id GROUP BY p.id"},
    {"q": "Show appointments grouped by month",
     "sql": "SELECT strftime('%Y-%m', appointment_date) AS month, COUNT(*) AS count FROM appointments GROUP BY month ORDER BY month"},
    {"q": "List doctors by number of completed appointments",
     "sql": "SELECT d.name, COUNT(a.id) AS completed FROM doctors d JOIN appointments a ON d.id = a.doctor_id WHERE a.status = 'Completed' GROUP BY d.id ORDER BY completed DESC"},
    {"q": "What is the total cost of treatments for each patient?",
     "sql": "SELECT p.first_name, p.last_name, SUM(t.cost) AS total_treatment_cost FROM patients p JOIN appointments a ON p.id = a.patient_id JOIN treatments t ON a.id = t.appointment_id GROUP BY p.id ORDER BY total_treatment_cost DESC"},
]

"""
setup_database.py
Creates clinic.db with 5 tables and realistic dummy data.
Run once: python setup_database.py
"""

import sqlite3
import random
from datetime import datetime, timedelta, date

DB_PATH = "clinic.db"

# ── Seed data pools ──────────────────────────────────────────────────────────
FIRST_NAMES = [
    "Aarav","Priya","Rahul","Sneha","Vikram","Ananya","Rohan","Kavya",
    "Arjun","Meera","Karan","Divya","Aditya","Pooja","Siddharth","Riya",
    "Nikhil","Shreya","Amit","Nisha","Rajesh","Sunita","Deepak","Asha",
    "Suresh","Geeta","Manoj","Sita","Ravi","Lata","Harish","Usha",
    "Gopal","Rekha","Mohan","Shobha","Arun","Savita","Vinod","Smita",
]
LAST_NAMES = [
    "Sharma","Verma","Singh","Patel","Kumar","Gupta","Mishra","Joshi",
    "Shah","Mehta","Nair","Rao","Reddy","Pillai","Iyer","Das","Bose",
    "Ghosh","Roy","Sen","Chatterjee","Banerjee","Mukherjee","Dutta",
]
CITIES = [
    "Mumbai","Delhi","Bangalore","Hyderabad","Chennai",
    "Kolkata","Pune","Ahmedabad","Jaipur","Lucknow",
]
SPECIALIZATIONS = ["Dermatology","Cardiology","Orthopedics","General","Pediatrics"]
DEPARTMENTS = {
    "Dermatology": "Skin & Hair",
    "Cardiology":  "Heart & Vascular",
    "Orthopedics": "Bone & Joint",
    "General":     "General Medicine",
    "Pediatrics":  "Child Health",
}
STATUSES_APT  = ["Scheduled","Completed","Cancelled","No-Show"]
STATUSES_INV  = ["Paid","Pending","Overdue"]
TREATMENTS = [
    ("Consultation",         150,  30),
    ("Blood Test",           300,  20),
    ("X-Ray",                500,  15),
    ("ECG",                  400,  20),
    ("Ultrasound",           800,  30),
    ("MRI Scan",            3500,  60),
    ("CT Scan",             2500,  45),
    ("Physiotherapy",        600,  45),
    ("Skin Biopsy",         1200,  40),
    ("Vaccination",          200,  10),
    ("Minor Surgery",       4500,  90),
    ("Dental Cleaning",      350,  30),
    ("Eye Examination",      400,  25),
    ("Allergy Test",         700,  30),
    ("Diabetes Screening",   450,  20),
    ("Bone Density Scan",    900,  25),
    ("Pulmonary Function",   750,  30),
    ("Endoscopy",           2000,  60),
    ("Cardiac Stress Test", 1800,  45),
    ("General Checkup",      250,  30),
]


def random_date(start_days_ago: int, end_days_ago: int = 0) -> date:
    start = datetime.now() - timedelta(days=start_days_ago)
    end   = datetime.now() - timedelta(days=end_days_ago)
    delta = (end - start).days
    return (start + timedelta(days=random.randint(0, max(delta, 0)))).date()


def random_datetime(start_days_ago: int, end_days_ago: int = 0) -> str:
    d = random_date(start_days_ago, end_days_ago)
    hour   = random.randint(8, 17)
    minute = random.choice([0, 15, 30, 45])
    return f"{d} {hour:02d}:{minute:02d}:00"


def maybe(value, prob_none: float = 0.15):
    """Return None with probability prob_none, else return value."""
    return None if random.random() < prob_none else value


def phone():
    return f"+91-{random.randint(70000,99999)}{random.randint(10000,99999)}"


def email(first: str, last: str) -> str:
    domains = ["gmail.com","yahoo.com","outlook.com","hotmail.com"]
    return f"{first.lower()}.{last.lower()}{random.randint(1,99)}@{random.choice(domains)}"


# ── Create schema ────────────────────────────────────────────────────────────
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS patients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name      TEXT    NOT NULL,
    last_name       TEXT    NOT NULL,
    email           TEXT,
    phone           TEXT,
    date_of_birth   DATE,
    gender          TEXT,
    city            TEXT,
    registered_date DATE
);

CREATE TABLE IF NOT EXISTS doctors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    specialization  TEXT,
    department      TEXT,
    phone           TEXT
);

CREATE TABLE IF NOT EXISTS appointments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id       INTEGER,
    doctor_id        INTEGER,
    appointment_date DATETIME,
    status           TEXT,
    notes            TEXT,
    FOREIGN KEY (patient_id) REFERENCES patients(id),
    FOREIGN KEY (doctor_id)  REFERENCES doctors(id)
);

CREATE TABLE IF NOT EXISTS treatments (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id    INTEGER,
    treatment_name    TEXT,
    cost              REAL,
    duration_minutes  INTEGER,
    FOREIGN KEY (appointment_id) REFERENCES appointments(id)
);

CREATE TABLE IF NOT EXISTS invoices (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id   INTEGER,
    invoice_date DATE,
    total_amount REAL,
    paid_amount  REAL,
    status       TEXT,
    FOREIGN KEY (patient_id) REFERENCES patients(id)
);
"""


def seed_doctors(cur):
    doctors = []
    doc_names = [
        "Dr. Aryan Kapoor","Dr. Priya Sharma","Dr. Rohit Verma",
        "Dr. Sunita Patel","Dr. Manoj Gupta","Dr. Kavitha Nair",
        "Dr. Rajan Mehta","Dr. Anita Singh","Dr. Deepak Rao",
        "Dr. Meena Iyer","Dr. Suresh Joshi","Dr. Rekha Das",
        "Dr. Anil Bose","Dr. Smita Roy","Dr. Harish Kumar",
    ]
    specs = (SPECIALIZATIONS * 3)[:15]
    random.shuffle(specs)
    for i, (name, spec) in enumerate(zip(doc_names, specs)):
        dept = DEPARTMENTS[spec]
        doctors.append((name, spec, dept, maybe(phone(), 0.05)))
    cur.executemany(
        "INSERT INTO doctors (name,specialization,department,phone) VALUES (?,?,?,?)",
        doctors
    )
    return list(range(1, len(doctors) + 1))


def seed_patients(cur, n=200):
    patients = []
    used = set()
    for _ in range(n):
        fn = random.choice(FIRST_NAMES)
        ln = random.choice(LAST_NAMES)
        # ensure distinct key for loop
        dob  = random_date(365*70, 365*5)
        reg  = random_date(365, 0)
        patients.append((
            fn, ln,
            maybe(email(fn, ln), 0.10),
            maybe(phone(), 0.12),
            dob,
            random.choice(["M","F"]),
            random.choice(CITIES),
            reg,
        ))
    cur.executemany(
        """INSERT INTO patients
           (first_name,last_name,email,phone,date_of_birth,gender,city,registered_date)
           VALUES (?,?,?,?,?,?,?,?)""",
        patients
    )
    return list(range(1, n + 1))


def seed_appointments(cur, patient_ids, doctor_ids, n=500):
    # Make some patients repeat visitors
    weighted_patients = (
        patient_ids[:30] * 4 +   # heavy users
        patient_ids[30:80] * 2 + # moderate
        patient_ids[80:]          # occasional
    )
    weighted_doctors = (
        doctor_ids[:5] * 3 +      # busier doctors
        doctor_ids[5:]
    )
    notes_pool = [
        "Follow-up required", "Patient reports improvement",
        "Referred to specialist", "Routine check", "Urgent review needed",
        "Post-surgery review", "Lab results pending", None, None, None,
    ]
    appointments = []
    for _ in range(n):
        pid    = random.choice(weighted_patients)
        did    = random.choice(weighted_doctors)
        dt     = random_datetime(365, 0)
        status = random.choices(
            STATUSES_APT, weights=[10, 55, 20, 15], k=1
        )[0]
        note   = maybe(random.choice(notes_pool), 0.30)
        appointments.append((pid, did, dt, status, note))
    cur.executemany(
        "INSERT INTO appointments (patient_id,doctor_id,appointment_date,status,notes) VALUES (?,?,?,?,?)",
        appointments
    )
    return list(range(1, n + 1))


def seed_treatments(cur, appointment_ids, n=350):
    # Only link to completed appointments
    cur.execute("SELECT id FROM appointments WHERE status='Completed'")
    completed = [r[0] for r in cur.fetchall()]
    if not completed:
        completed = appointment_ids[:200]

    treatments = []
    sample_ids = random.choices(completed, k=n)
    for apt_id in sample_ids:
        name, base_cost, base_dur = random.choice(TREATMENTS)
        cost = round(base_cost * random.uniform(0.85, 1.20), 2)
        dur  = base_dur + random.randint(-5, 10)
        treatments.append((apt_id, name, cost, max(5, dur)))
    cur.executemany(
        "INSERT INTO treatments (appointment_id,treatment_name,cost,duration_minutes) VALUES (?,?,?,?)",
        treatments
    )


def seed_invoices(cur, patient_ids, n=300):
    invoices = []
    for _ in range(n):
        pid    = random.choice(patient_ids)
        dt     = random_date(365, 0)
        total  = round(random.uniform(200, 8000), 2)
        status = random.choices(STATUSES_INV, weights=[55, 25, 20], k=1)[0]
        if status == "Paid":
            paid = total
        elif status == "Pending":
            paid = round(total * random.uniform(0, 0.5), 2)
        else:  # Overdue
            paid = round(total * random.uniform(0, 0.3), 2)
        invoices.append((pid, dt, total, paid, status))
    cur.executemany(
        "INSERT INTO invoices (patient_id,invoice_date,total_amount,paid_amount,status) VALUES (?,?,?,?,?)",
        invoices
    )


def main():
    import os
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing {DB_PATH}")

    random.seed(42)  # reproducible

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript(SCHEMA_SQL)

    print("Seeding doctors ...")
    doctor_ids = seed_doctors(cur)

    print("Seeding patients ...")
    patient_ids = seed_patients(cur, 200)

    print("Seeding appointments ...")
    appointment_ids = seed_appointments(cur, patient_ids, doctor_ids, 500)

    print("Seeding treatments ...")
    seed_treatments(cur, appointment_ids, 350)

    print("Seeding invoices ...")
    seed_invoices(cur, patient_ids, 300)

    con.commit()

    # Summary
    for table in ("patients","doctors","appointments","treatments","invoices"):
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"  {table}: {count} rows")

    con.close()
    print(f"\nDone! Database saved to: {DB_PATH}")


if __name__ == "__main__":
    main()

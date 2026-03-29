import sqlite3
from fastapi import FastAPI, HTTPException

schedule_app = FastAPI()
DB = "schedule.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            datetime TEXT,
            description TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

@schedule_app.get("/schedule")
def list_schedule():
    conn = get_db()
    events = conn.execute("SELECT * FROM events").fetchall()
    conn.close()
    return [dict(e) for e in events]

@schedule_app.post("/schedule")
def add_event(event: dict):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO events (title, datetime, description) VALUES (?, ?, ?)",
        (event.get("title"), event.get("datetime"), event.get("description"))
    )
    conn.commit()
    event_id = cursor.lastrowid
    conn.close()
    return {"status": "added", "id": event_id}

@schedule_app.delete("/schedule/{event_id}")
def delete_event(event_id: int):
    conn = get_db()
    result = conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"status": "deleted", "id": event_id}

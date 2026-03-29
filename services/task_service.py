import sqlite3
from fastapi import FastAPI, HTTPException

task_app = FastAPI()
DB = "tasks.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)
    conn.commit()
    conn.close()

init_db()

@task_app.get("/tasks")
def list_tasks():
    conn = get_db()
    tasks = conn.execute("SELECT * FROM tasks").fetchall()
    conn.close()
    return [dict(t) for t in tasks]

@task_app.post("/tasks")
def create_task(task: dict):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO tasks (title, description, status) VALUES (?, ?, ?)",
        (task.get("title"), task.get("description"), task.get("status", "pending"))
    )
    conn.commit()
    task_id = cursor.lastrowid
    conn.close()
    return {"status": "added", "id": task_id}

@task_app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    conn = get_db()
    result = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "deleted", "id": task_id}

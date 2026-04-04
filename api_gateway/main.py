from fastapi import FastAPI
import requests
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
FRONTEND_FILE = PROJECT_ROOT / "frontend.html"

SERVICES = {
    "tasks": "http://localhost:8001",
    "schedule": "http://localhost:8002",
    "trends": "http://localhost:8003",
    "github": "http://localhost:8004",
    "decision": "http://localhost:8005",
    "vibe": "http://localhost:8006",
}


@app.get("/")
def root():
    if FRONTEND_FILE.exists():
        return FileResponse(str(FRONTEND_FILE))
    return {
        "message": "OpenClaw API Gateway Running",
        "warning": f"frontend.html not found at {FRONTEND_FILE}"
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "frontend_found": FRONTEND_FILE.exists(),
        "services": SERVICES,
    }


@app.get("/tasks")
def get_tasks():
    return requests.get(f"{SERVICES['tasks']}/tasks").json()


@app.post("/tasks")
def add_task(task: dict):
    return requests.post(f"{SERVICES['tasks']}/tasks", json=task).json()


@app.patch("/tasks/{task_id}")
def update_task(task_id: int, updates: dict):
    return requests.patch(f"{SERVICES['tasks']}/tasks/{task_id}", json=updates).json()


@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    return requests.delete(f"{SERVICES['tasks']}/tasks/{task_id}").json()


@app.get("/schedule")
def get_schedule():
    return requests.get(f"{SERVICES['schedule']}/schedule").json()


@app.post("/schedule")
def add_event(event: dict):
    return requests.post(f"{SERVICES['schedule']}/schedule", json=event).json()


@app.delete("/schedule/{event_id}")
def delete_event(event_id: int):
    return requests.delete(f"{SERVICES['schedule']}/schedule/{event_id}").json()


@app.get("/trends")
def get_trends():
    return requests.get(f"{SERVICES['trends']}/trends").json()


@app.get("/github/repos")
def get_repos(username: str = "octocat", analyze: bool = False):
    return requests.get(
        f"{SERVICES['github']}/repos?username={username}&analyze={str(analyze).lower()}"
    ).json()


@app.post("/github/analyze")
def analyze_repo(payload: dict):
    return requests.post(f"{SERVICES['github']}/analyze", json=payload).json()


@app.get("/recommendation")
def get_recommendation(username: str = "octocat"):
    return requests.get(
        f"{SERVICES['decision']}/recommend?username={username}"
    ).json()


@app.post("/vibe")
def vibe_command(payload: dict):
    return requests.post(f"{SERVICES['vibe']}/vibe", json=payload).json()
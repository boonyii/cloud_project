from fastapi import FastAPI
import requests
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SERVICES = {
    "tasks": "http://localhost:8001",
    "schedule": "http://localhost:8002",
    "trends": "http://localhost:8003",
    "github": "http://localhost:8004",
    "decision": "http://localhost:8005",
}

@app.get("/")
def root():
    return {"message": "OpenClaw API Gateway Running"}

@app.get("/tasks")
def get_tasks():
    return requests.get(f"{SERVICES['tasks']}/tasks").json()

@app.post("/tasks")
def add_task(task: dict):
    return requests.post(f"{SERVICES['tasks']}/tasks", json=task).json()

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
def get_repos(username: str = "octocat"):
    return requests.get(f"{SERVICES['github']}/repos?username={username}").json()

@app.get("/recommendation")
def get_recommendation(username: str = "octocat"):
    return requests.get(f"{SERVICES['decision']}/recommend?username={username}").json()


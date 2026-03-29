from fastapi import FastAPI
import requests

app = FastAPI()

SERVICES = {
    "tasks": "http://localhost:8001",
    "schedule": "http://localhost:8002",
    "trends": "http://localhost:8003",
    "github": "http://localhost:8004",
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

@app.get("/schedule")
def get_schedule():
    return requests.get(f"{SERVICES['schedule']}/schedule").json()

@app.get("/trends")
def get_trends():
    return requests.get(f"{SERVICES['trends']}/trends").json()

@app.get("/github/repos")
def get_repos(username: str = "octocat"):
    return requests.get(f"{SERVICES['github']}/repos?username={username}").json()
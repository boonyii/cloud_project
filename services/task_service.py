from fastapi import FastAPI

task_app = FastAPI()
TASKS = []

@task_app.get("/tasks")
def list_tasks():
    return TASKS

@task_app.post("/tasks")
def create_task(task: dict):
    TASKS.append(task)
    return {"status": "added", "task": task}
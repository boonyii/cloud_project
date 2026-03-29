from fastapi import FastAPI

schedule_app = FastAPI()
SCHEDULE = []

@schedule_app.get("/schedule")
def list_schedule():
    return SCHEDULE

@schedule_app.post("/schedule")
def add_event(event: dict):
    SCHEDULE.append(event)
    return {"status": "added", "event": event}
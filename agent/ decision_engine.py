import requests

GATEWAY = "http://localhost:8000"


def recommend_tasks():
    tasks = requests.get(f"{GATEWAY}/tasks").json()
    schedule = requests.get(f"{GATEWAY}/schedule").json()

    if not tasks:
        return "No tasks available. Add some tasks."

    return f"You have {len(tasks)} tasks and {len(schedule)} events. Focus on highest priority task."


if __name__ == "__main__":
    print(recommend_tasks())

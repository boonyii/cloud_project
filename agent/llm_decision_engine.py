import os
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, Query
from dotenv import load_dotenv

load_dotenv()

decision_app = FastAPI(title="Gemini LLM Decision Service")

# -----------------------------
# Config
# -----------------------------
GATEWAY = os.getenv("GATEWAY_URL", "http://localhost:8000")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "8"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_VERSION = os.getenv("GEMINI_API_VERSION", "v1beta")
USE_LLM = os.getenv("USE_LLM", "true").lower() == "true"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("llm_decision")


# -----------------------------
# Helpers
# -----------------------------
def safe_get_json(url: str) -> Any:
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error("GET failed for %s: %s", url, e)
        return {"error": str(e)}


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def normalize_priority(priority: Optional[str]) -> str:
    if not priority:
        return "medium"
    value = str(priority).strip().lower()
    if value in {"urgent", "high"}:
        return "high"
    if value == "low":
        return "low"
    return "medium"


def extract_trends(trend_data: Any) -> List[str]:
    if isinstance(trend_data, dict):
        keywords = trend_data.get("trending_keywords", [])
        if isinstance(keywords, list):
            return [str(x) for x in keywords[:10]]
    return []


def extract_repos(repo_data: Any) -> List[str]:
    names = []
    if isinstance(repo_data, list):
        for repo in repo_data[:5]:
            if isinstance(repo, dict) and repo.get("name"):
                names.append(str(repo["name"]))
    return names


def summarize_tasks(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned = []
    for task in tasks[:10]:
        cleaned.append(
            {
                "id": task.get("id"),
                "title": task.get("title", "Untitled"),
                "description": task.get("description", ""),
                "status": task.get("status", "pending"),
                "priority": normalize_priority(task.get("priority")),
                "deadline": task.get("deadline"),
            }
        )
    return cleaned


def summarize_schedule(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned = []
    for event in events[:10]:
        cleaned.append(
            {
                "id": event.get("id"),
                "title": event.get("title", "Untitled"),
                "datetime": event.get("datetime"),
                "description": event.get("description", ""),
            }
        )
    return cleaned


def fallback_recommendation(
    tasks: List[Dict[str, Any]],
    schedule: List[Dict[str, Any]],
    trends: List[str],
    repos: List[str],
) -> Dict[str, Any]:
    open_tasks = [
        t for t in tasks
        if str(t.get("status", "pending")).lower() not in {"done", "completed", "complete"}
    ]

    now = datetime.now()
    overdue = []
    high_priority = []

    for task in open_tasks:
        if normalize_priority(task.get("priority")) == "high":
            high_priority.append(task)

        deadline = parse_datetime(task.get("deadline"))
        if deadline and deadline < now:
            overdue.append(task)

    if overdue:
        title = overdue[0].get("title", "Untitled task")
        return {
            "focus": f"Complete overdue task: {title}",
            "reason": "This task is already overdue, so it should be handled first.",
            "next_steps": [
                f"Finish or reduce the scope of '{title}'",
                "Update the task status after progress",
                "Review the remaining tasks and schedule",
            ],
            "mode": "fallback",
        }

    if high_priority:
        title = high_priority[0].get("title", "Untitled task")
        return {
            "focus": f"Work on high-priority task: {title}",
            "reason": "It is marked high priority and should be addressed before lower-priority work.",
            "next_steps": [
                f"Start '{title}' first",
                "Break it into smaller sub-tasks",
                "Connect it to GitHub work if relevant",
            ],
            "mode": "fallback",
        }

    if open_tasks:
        title = open_tasks[0].get("title", "Untitled task")
        return {
            "focus": f"Continue pending task: {title}",
            "reason": "You still have pending work, so this is the best next step.",
            "next_steps": [
                f"Make progress on '{title}'",
                "Check whether it links to your GitHub repos",
                "Review your schedule for time constraints",
            ],
            "mode": "fallback",
        }

    if repos:
        return {
            "focus": f"Work on GitHub repo: {repos[0]}",
            "reason": "There are no pending tasks, so repo work is the strongest next action.",
            "next_steps": [
                f"Open repo '{repos[0]}'",
                "Pick one bug fix or improvement",
                "Prepare it for frontend demo",
            ],
            "mode": "fallback",
        }

    if trends:
        return {
            "focus": f"Review trend: {trends[0]}",
            "reason": "There are no pending tasks, so exploring trends is useful.",
            "next_steps": [
                f"Read about '{trends[0]}'",
                "See whether it inspires a feature",
                "Add a task if it becomes actionable",
            ],
            "mode": "fallback",
        }

    return {
        "focus": "Plan your next steps",
        "reason": "No tasks, repos, or trend data were available.",
        "next_steps": [
            "Add a task",
            "Add a schedule item if needed",
            "Refresh the connected services",
        ],
        "mode": "fallback",
    }


def build_prompt(
    username: str,
    tasks: List[Dict[str, Any]],
    schedule: List[Dict[str, Any]],
    trends: List[str],
    repos: List[str],
) -> str:
    now = datetime.now().isoformat()

    return f"""
You are an intelligent cloud personal assistant inside a microservices project.

Current timestamp:
{now}

GitHub username:
{username}

Tasks:
{json.dumps(tasks, indent=2)}

Schedule:
{json.dumps(schedule, indent=2)}

Trending keywords:
{json.dumps(trends, indent=2)}

GitHub repos:
{json.dumps(repos, indent=2)}

Your job:
1. Decide what the user should focus on next.
2. Explain the reason briefly and clearly.
3. Give exactly 3 concrete next steps.
4. Prefer pending tasks over random exploration.
5. If there are urgent, overdue, or high-priority tasks, prioritize them.
6. If there are no tasks, use GitHub repos or trends to suggest useful work.
7. Keep the answer practical for a student cloud-computing demo project.
8. Mention GitHub if it helps show an API-driven development cycle from data processing to frontend user presentation.

Return ONLY valid JSON in this exact format:
{{
  "focus": "string",
  "reason": "string",
  "next_steps": ["step 1", "step 2", "step 3"]
}}
""".strip()


def call_gemini(prompt: str) -> Dict[str, Any]:
    if not GEMINI_API_KEY:
        raise ValueError("Missing GEMINI_API_KEY in .env file")

    url = (
        f"https://generativelanguage.googleapis.com/"
        f"{GEMINI_API_VERSION}/models/{GEMINI_MODEL}:generateContent"
    )

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json",
        },
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=REQUEST_TIMEOUT + 15,
    )
    response.raise_for_status()
    data = response.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError("Gemini returned no candidates")

    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise ValueError("Gemini returned no content parts")

    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise ValueError("Gemini returned empty text")

    parsed = json.loads(text)

    if not isinstance(parsed, dict):
        raise ValueError("Gemini response is not a JSON object")

    focus = parsed.get("focus")
    reason = parsed.get("reason")
    next_steps = parsed.get("next_steps")

    if not isinstance(focus, str) or not isinstance(reason, str) or not isinstance(next_steps, list):
        raise ValueError("Gemini JSON missing expected keys")

    return {
        "focus": focus,
        "reason": reason,
        "next_steps": [str(x) for x in next_steps[:3]],
        "mode": "gemini",
    }


def build_response(
    username: str,
    tasks_data: Any,
    schedule_data: Any,
    trends_data: Any,
    repos_data: Any,
    recommendation: Dict[str, Any],
) -> Dict[str, Any]:
    tasks = tasks_data if isinstance(tasks_data, list) else []
    schedule = schedule_data if isinstance(schedule_data, list) else []
    trends = extract_trends(trends_data)
    repos = extract_repos(repos_data)

    return {
        "status": "success",
        "username": username,
        "generated_at": datetime.now().isoformat(),
        "recommendation": recommendation,
        "summary": {
            "task_count": len(tasks),
            "event_count": len(schedule),
            "trend_count": len(trends),
            "repo_count": len(repos),
        },
        "data_preview": {
            "tasks": tasks[:5],
            "schedule": schedule[:5],
            "trending_keywords": trends[:5],
            "github_repos": repos[:5],
        },
        "data_sources": {
            "tasks_available": isinstance(tasks_data, list),
            "schedule_available": isinstance(schedule_data, list),
            "trends_available": isinstance(trends_data, dict),
            "github_available": isinstance(repos_data, list),
        },
    }


# -----------------------------
# Routes
# -----------------------------
@decision_app.get("/")
def root():
    return {"message": "Gemini LLM Decision Service Running"}


@decision_app.get("/health")
def health():
    return {
        "status": "ok",
        "use_llm": USE_LLM,
        "gemini_model": GEMINI_MODEL,
        "gemini_api_version": GEMINI_API_VERSION,
        "has_api_key": bool(GEMINI_API_KEY),
    }


@decision_app.get("/recommend")
def recommend(username: str = Query(default="octocat")):
    logger.info("Generating recommendation for username=%s", username)

    tasks_data = safe_get_json(f"{GATEWAY}/tasks")
    schedule_data = safe_get_json(f"{GATEWAY}/schedule")
    trends_data = safe_get_json(f"{GATEWAY}/trends")
    repos_data = safe_get_json(f"{GATEWAY}/github/repos?username={username}")

    tasks = summarize_tasks(tasks_data if isinstance(tasks_data, list) else [])
    schedule = summarize_schedule(schedule_data if isinstance(schedule_data, list) else [])
    trends = extract_trends(trends_data)
    repos = extract_repos(repos_data)

    fallback = fallback_recommendation(tasks, schedule, trends, repos)

    if not USE_LLM:
        return build_response(
            username=username,
            tasks_data=tasks_data,
            schedule_data=schedule_data,
            trends_data=trends_data,
            repos_data=repos_data,
            recommendation=fallback,
        )

    try:
        prompt = build_prompt(username, tasks, schedule, trends, repos)
        gemini_result = call_gemini(prompt)
        recommendation = gemini_result
    except Exception as e:
        logger.error("Gemini failed, using fallback: %s", e)
        recommendation = fallback
        recommendation["llm_error"] = str(e)

    return build_response(
        username=username,
        tasks_data=tasks_data,
        schedule_data=schedule_data,
        trends_data=trends_data,
        repos_data=repos_data,
        recommendation=recommendation,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(decision_app, host="127.0.0.1", port=8005, reload=True)
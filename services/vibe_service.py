from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
import requests
import os
import json
import re

vibe_app = FastAPI(title="Vibe Coding Service")

TASK_SERVICE_URL = os.getenv("TASK_SERVICE_URL", "http://localhost:8001")
SCHEDULE_SERVICE_URL = os.getenv("SCHEDULE_SERVICE_URL", "http://localhost:8002")
GITHUB_SERVICE_URL = os.getenv("GITHUB_SERVICE_URL", "http://localhost:8004")

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "10"))
GITHUB_ANALYSIS_TIMEOUT = int(os.getenv("GITHUB_ANALYSIS_TIMEOUT", "60"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_VERSION = os.getenv("GEMINI_API_VERSION", "v1beta")


class VibeRequest(BaseModel):
    command: str
    github_username: str = "octocat"


def call_json_api(
    method: str,
    url: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: Optional[int] = None
) -> Any:
    method = method.upper()
    timeout = timeout or REQUEST_TIMEOUT

    try:
        if method == "GET":
            res = requests.get(url, timeout=timeout)
        elif method == "POST":
            res = requests.post(url, json=payload or {}, timeout=timeout)
        elif method == "DELETE":
            res = requests.delete(url, timeout=timeout)
        else:
            return {"error": f"Unsupported method: {method}"}

        res.raise_for_status()

        try:
            return res.json()
        except ValueError:
            return {
                "error": "Service returned non-JSON response",
                "status_code": res.status_code,
                "text": res.text[:300]
            }

    except requests.RequestException as e:
        return {"error": str(e)}


def build_vibe_prompt(command: str) -> str:
    return f"""
You are a natural-language controller for a student cloud personal assistant project.

User command:
{command}

Available intents:
1. add_task
2. delete_task
3. add_event
4. delete_event
5. list_tasks
6. list_schedule
7. analyze_github
8. generate_tasks_from_github
9. unknown

Rules:
- If the user wants to create a task, use add_task.
- If the user wants to delete/remove a task, use delete_task.
- If the user wants to create a calendar/schedule event, use add_event.
- If the user wants to delete/remove an event, use delete_event.
- If the user asks to show/list tasks, use list_tasks.
- If the user asks to show/list schedule/events, use list_schedule.
- If the user wants GitHub repo analysis, use analyze_github.
- If the user wants tasks created from GitHub repos, use generate_tasks_from_github.
- If unclear, use unknown.
- For add_task, fill title and description as best as possible.
- For delete_task, use either id if explicitly given, or title if given.
- For add_event, fill title, datetime, and description as best as possible.
- For delete_event, use either id if explicitly given, or title if given.
- For analyze_github and generate_tasks_from_github, keep other fields empty.
- If no datetime is given, use empty string.
- Return ONLY valid JSON.

Return JSON in exactly this shape:
{{
  "intent": "add_task",
  "parameters": {{
    "id": null,
    "title": "string",
    "description": "string",
    "datetime": "string"
  }}
}}
""".strip()


def call_gemini(prompt: str) -> Dict[str, Any]:
    if not GEMINI_API_KEY:
        raise ValueError("Missing GEMINI_API_KEY")

    url = (
        f"https://generativelanguage.googleapis.com/"
        f"{GEMINI_API_VERSION}/models/{GEMINI_MODEL}:generateContent"
    )

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
    }

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }

    res = requests.post(url, headers=headers, json=payload, timeout=25)
    res.raise_for_status()

    data = res.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    parsed = json.loads(text)

    if not isinstance(parsed, dict):
        raise ValueError("Gemini response was not a JSON object")

    return parsed


def build_github_task_prompt(repos: List[Dict[str, Any]]) -> str:
    repo_json = json.dumps(repos[:5], indent=2)

    return f"""
You are helping a student turn GitHub repository data into actionable project tasks.

Repository data:
{repo_json}

Your job:
- Generate exactly 3 practical tasks based on the repositories.
- Focus on useful improvements for a cloud-computing demo project.
- Prefer tasks such as improving documentation, UI, API integration, error handling, deployment, testing, or AI features.
- Keep tasks short and actionable.

Return ONLY valid JSON in this exact format:
{{
  "tasks": [
    {{
      "title": "string",
      "description": "string"
    }},
    {{
      "title": "string",
      "description": "string"
    }},
    {{
      "title": "string",
      "description": "string"
    }}
  ]
}}
""".strip()


def call_gemini_for_task_generation(repos: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    if not GEMINI_API_KEY:
        raise ValueError("Missing GEMINI_API_KEY")

    prompt = build_github_task_prompt(repos)

    url = (
        f"https://generativelanguage.googleapis.com/"
        f"{GEMINI_API_VERSION}/models/{GEMINI_MODEL}:generateContent"
    )

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
    }

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json",
        },
    }

    res = requests.post(url, headers=headers, json=payload, timeout=25)
    res.raise_for_status()

    data = res.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    parsed = json.loads(text)

    tasks = parsed.get("tasks", [])
    if not isinstance(tasks, list):
        raise ValueError("Gemini task generation returned invalid tasks")

    normalized_tasks = []
    for item in tasks[:3]:
        if isinstance(item, dict):
            normalized_tasks.append({
                "title": str(item.get("title", "")).strip() or "Untitled task",
                "description": str(item.get("description", "")).strip()
            })

    if not normalized_tasks:
        raise ValueError("No valid tasks generated")

    return normalized_tasks


def fallback_parse_command(command: str) -> Dict[str, Any]:
    text = command.strip()
    text_lower = text.lower()

    match = re.match(r"^delete\s+task\s+(?:id\s+)?(\d+)$", text_lower)
    if match:
        return {
            "intent": "delete_task",
            "parameters": {
                "id": int(match.group(1)),
                "title": "",
                "description": "",
                "datetime": ""
            },
            "mode": "fallback"
        }

    match = re.match(r"^delete\s+event\s+(?:id\s+)?(\d+)$", text_lower)
    if match:
        return {
            "intent": "delete_event",
            "parameters": {
                "id": int(match.group(1)),
                "title": "",
                "description": "",
                "datetime": ""
            },
            "mode": "fallback"
        }

    match = re.match(r"^delete\s+task\s+(.+)$", text, flags=re.IGNORECASE)
    if match:
        return {
            "intent": "delete_task",
            "parameters": {
                "id": None,
                "title": match.group(1).strip(),
                "description": "",
                "datetime": ""
            },
            "mode": "fallback"
        }

    match = re.match(r"^delete\s+event\s+(.+)$", text, flags=re.IGNORECASE)
    if match:
        return {
            "intent": "delete_event",
            "parameters": {
                "id": None,
                "title": match.group(1).strip(),
                "description": "",
                "datetime": ""
            },
            "mode": "fallback"
        }

    if any(phrase in text_lower for phrase in [
        "create tasks from github",
        "generate tasks from github",
        "make tasks from github",
        "create tasks from my github",
        "generate tasks from my github",
        "make tasks from my github",
        "create tasks based on github",
        "generate tasks based on github"
    ]):
        return {
            "intent": "generate_tasks_from_github",
            "parameters": {
                "id": None,
                "title": "",
                "description": "",
                "datetime": ""
            },
            "mode": "fallback"
        }

    if any(phrase in text_lower for phrase in [
        "analyze github",
        "analyse github",
        "analyze my github",
        "analyse my github",
        "analyze repositories",
        "analyse repositories",
        "analyze repos",
        "analyse repos",
        "review github repos",
        "review my github"
    ]):
        return {
            "intent": "analyze_github",
            "parameters": {
                "id": None,
                "title": "",
                "description": "",
                "datetime": ""
            },
            "mode": "fallback"
        }

    if any(phrase in text_lower for phrase in ["list tasks", "show tasks", "view tasks"]):
        return {
            "intent": "list_tasks",
            "parameters": {
                "id": None,
                "title": "",
                "description": "",
                "datetime": ""
            },
            "mode": "fallback"
        }

    if any(phrase in text_lower for phrase in [
        "list schedule", "show schedule", "view schedule",
        "list events", "show events", "view events"
    ]):
        return {
            "intent": "list_schedule",
            "parameters": {
                "id": None,
                "title": "",
                "description": "",
                "datetime": ""
            },
            "mode": "fallback"
        }

    match = re.match(
        r"^(add|create|make)\s+(a\s+)?task\s+(to\s+)?(.+)$",
        text,
        flags=re.IGNORECASE
    )
    if match:
        title = match.group(4).strip() or "Untitled task"
        return {
            "intent": "add_task",
            "parameters": {
                "id": None,
                "title": title,
                "description": "",
                "datetime": ""
            },
            "mode": "fallback"
        }

    if any(word in text_lower for word in ["schedule", "meeting", "event", "appointment"]):
        cleaned_title = re.sub(
            r"^(add|create|make|schedule)\s+(an?\s+)?(event|meeting|appointment)\s*",
            "",
            text,
            flags=re.IGNORECASE
        ).strip()

        return {
            "intent": "add_event",
            "parameters": {
                "id": None,
                "title": cleaned_title or text.strip(),
                "description": "",
                "datetime": ""
            },
            "mode": "fallback"
        }

    return {
        "intent": "unknown",
        "parameters": {
            "id": None,
            "title": "",
            "description": "",
            "datetime": ""
        },
        "mode": "fallback"
    }


def normalize_parsed_result(result: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return {
            "intent": "unknown",
            "parameters": {
                "id": None,
                "title": "",
                "description": "",
                "datetime": ""
            }
        }

    intent = str(result.get("intent", "unknown")).strip().lower()
    if intent not in {
        "add_task", "delete_task", "add_event",
        "delete_event", "list_tasks", "list_schedule",
        "analyze_github", "generate_tasks_from_github", "unknown"
    }:
        intent = "unknown"

    params = result.get("parameters", {})
    if not isinstance(params, dict):
        params = {}

    parsed_id = params.get("id", None)
    try:
        if parsed_id is not None and parsed_id != "":
            parsed_id = int(parsed_id)
        else:
            parsed_id = None
    except (TypeError, ValueError):
        parsed_id = None

    return {
        "intent": intent,
        "parameters": {
            "id": parsed_id,
            "title": str(params.get("title", "") or "").strip(),
            "description": str(params.get("description", "") or "").strip(),
            "datetime": str(params.get("datetime", "") or "").strip(),
        }
    }


def parse_command(command: str) -> Dict[str, Any]:
    try:
        prompt = build_vibe_prompt(command)
        result = call_gemini(prompt)
        normalized = normalize_parsed_result(result)
        normalized["mode"] = "gemini"
        return normalized
    except Exception as e:
        fallback = fallback_parse_command(command)
        fallback["llm_error"] = str(e)
        return fallback


def find_task_by_title(title: str) -> Optional[Dict[str, Any]]:
    tasks = call_json_api("GET", f"{TASK_SERVICE_URL}/tasks")
    if not isinstance(tasks, list):
        return None

    title_lower = title.strip().lower()
    for task in tasks:
        if str(task.get("title", "")).strip().lower() == title_lower:
            return task
    return None


def find_event_by_title(title: str) -> Optional[Dict[str, Any]]:
    events = call_json_api("GET", f"{SCHEDULE_SERVICE_URL}/schedule")
    if not isinstance(events, list):
        return None

    title_lower = title.strip().lower()
    for event in events:
        if str(event.get("title", "")).strip().lower() == title_lower:
            return event
    return None


def fallback_generated_tasks(repos: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    tasks = []

    for repo in repos[:3]:
        name = repo.get("name", "repository")
        description = str(repo.get("description", "") or "").strip()
        readme_excerpt = str(repo.get("readme_excerpt", "") or "").strip()
        language = str(repo.get("language", "") or "").strip()

        if description:
            tasks.append({
                "title": f"Improve repo: {name}",
                "description": f"Refine {name} ({language or 'project'}) based on its current description: {description[:120]}"
            })
        elif readme_excerpt:
            tasks.append({
                "title": f"Review repo: {name}",
                "description": f"Use the README to improve setup, documentation, or demo flow for {name}."
            })
        else:
            tasks.append({
                "title": f"Polish repo: {name}",
                "description": "Improve README, UI, and project presentation quality."
            })

    if not tasks:
        tasks = [
            {
                "title": "Review GitHub repositories",
                "description": "Inspect project repos and identify missing documentation and demo polish."
            },
            {
                "title": "Improve README files",
                "description": "Add clearer setup instructions and architecture explanation."
            },
            {
                "title": "Refine frontend presentation",
                "description": "Make GitHub analysis easier to understand in the dashboard."
            }
        ]

    return tasks[:3]


def execute_intent(parsed: Dict[str, Any], github_username: str) -> Dict[str, Any]:
    intent = parsed.get("intent", "unknown")
    params = parsed.get("parameters", {}) or {}

    if intent == "add_task":
        payload = {
            "title": params.get("title") or "Untitled task",
            "description": params.get("description", ""),
            "status": "pending",
        }
        result = call_json_api("POST", f"{TASK_SERVICE_URL}/tasks", payload)
        return {
            "action": "add_task",
            "message": "Task created",
            "result": result,
        }

    if intent == "delete_task":
        task_id = params.get("id")
        title = str(params.get("title", "")).strip()

        if task_id is not None:
            result = call_json_api("DELETE", f"{TASK_SERVICE_URL}/tasks/{task_id}")
            return {
                "action": "delete_task",
                "message": f"Delete requested for task id {task_id}",
                "result": result,
            }

        if title:
            matched_task = find_task_by_title(title)
            if not matched_task:
                return {
                    "action": "delete_task",
                    "message": f'No task found with title "{title}"',
                    "result": {},
                }

            result = call_json_api("DELETE", f"{TASK_SERVICE_URL}/tasks/{matched_task['id']}")
            return {
                "action": "delete_task",
                "message": f'Deleted task "{matched_task.get("title", "")}"',
                "result": result,
            }

        return {
            "action": "delete_task",
            "message": "No task id or title provided",
            "result": {},
        }

    if intent == "add_event":
        payload = {
            "title": params.get("title") or "Untitled event",
            "datetime": params.get("datetime", ""),
            "description": params.get("description", ""),
        }
        result = call_json_api("POST", f"{SCHEDULE_SERVICE_URL}/schedule", payload)
        return {
            "action": "add_event",
            "message": "Event created",
            "result": result,
        }

    if intent == "delete_event":
        event_id = params.get("id")
        title = str(params.get("title", "")).strip()

        if event_id is not None:
            result = call_json_api("DELETE", f"{SCHEDULE_SERVICE_URL}/schedule/{event_id}")
            return {
                "action": "delete_event",
                "message": f"Delete requested for event id {event_id}",
                "result": result,
            }

        if title:
            matched_event = find_event_by_title(title)
            if not matched_event:
                return {
                    "action": "delete_event",
                    "message": f'No event found with title "{title}"',
                    "result": {},
                }

            result = call_json_api("DELETE", f"{SCHEDULE_SERVICE_URL}/schedule/{matched_event['id']}")
            return {
                "action": "delete_event",
                "message": f'Deleted event "{matched_event.get("title", "")}"',
                "result": result,
            }

        return {
            "action": "delete_event",
            "message": "No event id or title provided",
            "result": {},
        }

    if intent == "list_tasks":
        result = call_json_api("GET", f"{TASK_SERVICE_URL}/tasks")
        return {
            "action": "list_tasks",
            "message": "Loaded tasks",
            "result": result,
        }

    if intent == "list_schedule":
        result = call_json_api("GET", f"{SCHEDULE_SERVICE_URL}/schedule")
        return {
            "action": "list_schedule",
            "message": "Loaded schedule",
            "result": result,
        }

    if intent == "analyze_github":
        result = call_json_api(
            "GET",
            f"{GITHUB_SERVICE_URL}/repos?username={github_username}&analyze=true",
            timeout=GITHUB_ANALYSIS_TIMEOUT
        )
        return {
            "action": "analyze_github",
            "message": f"Analyzed GitHub repos for {github_username}",
            "result": result,
        }

    if intent == "generate_tasks_from_github":
        repos = call_json_api(
            "GET",
            f"{GITHUB_SERVICE_URL}/repos?username={github_username}&analyze=false",
            timeout=GITHUB_ANALYSIS_TIMEOUT
        )

        if not isinstance(repos, list) or not repos:
            return {
                "action": "generate_tasks_from_github",
                "message": f"No repositories available for {github_username}",
                "result": repos,
            }

        try:
            generated_tasks = call_gemini_for_task_generation(repos)
            generation_mode = "gemini"
            generation_error = None
        except Exception as e:
            generated_tasks = fallback_generated_tasks(repos)
            generation_mode = "fallback"
            generation_error = str(e)

        created = []
        for task in generated_tasks:
            payload = {
                "title": task.get("title") or "Untitled task",
                "description": task.get("description", ""),
                "status": "pending",
            }
            created_result = call_json_api("POST", f"{TASK_SERVICE_URL}/tasks", payload)
            created.append({
                "task": payload,
                "create_result": created_result
            })

        response = {
            "source_repo_count": len(repos),
            "generated_task_count": len(generated_tasks),
            "generation_mode": generation_mode,
            "generated_tasks": generated_tasks,
            "created_tasks": created,
        }

        if generation_error:
            response["generation_error"] = generation_error

        return {
            "action": "generate_tasks_from_github",
            "message": f"Generated and created {len(generated_tasks)} tasks from GitHub repos for {github_username}",
            "result": response,
        }

    return {
        "action": "unknown",
        "message": "Could not understand the command",
        "result": {},
    }


@vibe_app.get("/")
def root():
    return {"message": "Vibe Coding Service Running"}


@vibe_app.post("/vibe")
def vibe_command(request: VibeRequest):
    parsed = parse_command(request.command)
    executed = execute_intent(parsed, request.github_username)

    return {
        "status": "success",
        "command": request.command,
        "parsed_intent": parsed.get("intent", "unknown"),
        "mode": parsed.get("mode", "unknown"),
        "parameters": parsed.get("parameters", {}),
        "execution": executed,
    }
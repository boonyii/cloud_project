from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, Dict, Any
import requests
import base64
import os
import re
import json

github_app = FastAPI()

GITHUB_API = "https://api.github.com"
REQUEST_TIMEOUT = int(os.getenv("GITHUB_TIMEOUT", "10"))
MAX_REPOS = int(os.getenv("MAX_REPOS", "5"))
README_PREVIEW_CHARS = int(os.getenv("README_PREVIEW_CHARS", "800"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_VERSION = os.getenv("GEMINI_API_VERSION", "v1beta")


class RepoAnalyzeRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    language: Optional[str] = ""
    stars: Optional[int] = 0
    url: Optional[str] = ""
    readme_excerpt: Optional[str] = ""


def build_headers() -> dict:
    return {
        "Accept": "application/vnd.github.v3+json"
    }


def clean_readme(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`.*?`", "", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_readme_excerpt(username: str, repo_name: str) -> str:
    url = f"{GITHUB_API}/repos/{username}/{repo_name}/readme"

    try:
        res = requests.get(url, headers=build_headers(), timeout=REQUEST_TIMEOUT)

        if res.status_code != 200:
            return ""

        data = res.json()
        if not isinstance(data, dict):
            return ""

        encoded_content = data.get("content", "")
        encoding = data.get("encoding", "")

        if not encoded_content or encoding != "base64":
            return ""

        encoded_content = encoded_content.replace("\n", "")
        decoded_bytes = base64.b64decode(encoded_content)
        decoded_text = decoded_bytes.decode("utf-8", errors="ignore").strip()

        cleaned = clean_readme(decoded_text)
        return cleaned[:README_PREVIEW_CHARS]

    except Exception:
        return ""


def build_repo_analysis_prompt(repo: RepoAnalyzeRequest) -> str:
    repo_json = json.dumps(repo.model_dump(), indent=2)

    return f"""
You are analyzing a GitHub repository for a student cloud-computing project.

Repository data:
{repo_json}

Your job:
1. Summarize what this repo is about in 1-2 sentences.
2. Identify the likely tech stack.
3. Suggest exactly 3 practical improvements.
4. Keep the answer useful for a project demo.

Return ONLY valid JSON in this exact format:
{{
  "summary": "string",
  "tech_stack": ["item 1", "item 2"],
  "improvements": ["step 1", "step 2", "step 3"]
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
            "temperature": 0.3,
            "responseMimeType": "application/json",
        },
    }

    response = requests.post(url, headers=headers, json=payload, timeout=25)
    response.raise_for_status()

    data = response.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]

    return json.loads(text)


def fallback_repo_analysis(repo: RepoAnalyzeRequest) -> Dict[str, Any]:
    summary = repo.description or repo.readme_excerpt[:150] or "No description available."

    return {
        "summary": summary,
        "tech_stack": [repo.language] if repo.language else [],
        "improvements": [
            "Improve README",
            "Add documentation",
            "Enhance project demo"
        ],
        "mode": "fallback",
    }


def analyze_repo_data(repo_data: Dict[str, Any]) -> Dict[str, Any]:
    repo_obj = RepoAnalyzeRequest(**repo_data)

    try:
        prompt = build_repo_analysis_prompt(repo_obj)
        result = call_gemini(prompt)
        result["mode"] = "gemini"
        return result
    except Exception as e:
        fallback = fallback_repo_analysis(repo_obj)
        fallback["llm_error"] = str(e)
        return fallback


@github_app.get("/repos")
def get_repos(username: str = "octocat", analyze: bool = False):
    url = f"{GITHUB_API}/users/{username}/repos"

    try:
        res = requests.get(url, headers=build_headers(), timeout=REQUEST_TIMEOUT)

        if res.status_code != 200:
            return {"error": f"GitHub API error {res.status_code}"}

        data = res.json()

        results = []

        for repo in data[:MAX_REPOS]:
            repo_name = repo.get("name")
            if not repo_name:
                continue

            readme_excerpt = get_readme_excerpt(username, repo_name)

            repo_data = {
                "name": repo_name,
                "description": repo.get("description"),
                "language": repo.get("language"),
                "stars": repo.get("stargazers_count", 0),
                "url": repo.get("html_url"),
                "readme_excerpt": readme_excerpt,
            }

            if analyze:
                repo_data["analysis"] = analyze_repo_data(repo_data)

            results.append(repo_data)

        return results

    except Exception as e:
        return {"error": str(e)}
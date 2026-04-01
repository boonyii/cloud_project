from fastapi import FastAPI, HTTPException
import requests

github_app = FastAPI()

@github_app.get("/repos")
def get_repos(username: str = "octocat"):
    url = f"https://api.github.com/users/{username}/repos"

    try:
        res = requests.get(url, timeout=10)

        if res.status_code != 200:
            return {
                "error": f"GitHub API returned status {res.status_code}",
                "details": res.json()
            }

        data = res.json()

        if not isinstance(data, list):
            return {
                "error": "Unexpected response format from GitHub",
                "details": data
            }

        simplified = [
            {
                "name": repo.get("name"),
                "url": repo.get("html_url")
            }
            for repo in data[:5]
        ]

        return simplified

    except requests.exceptions.Timeout:
        return {"error": "Request to GitHub timed out"}

    except requests.exceptions.ConnectionError:
        return {"error": "Failed to connect to GitHub"}

    except Exception as e:
        return {"error": str(e)}
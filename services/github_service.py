from fastapi import FastAPI
import requests

github_app = FastAPI()

@github_app.get("/repos")
def get_repos(username: str = "octocat"):
    url = f"https://api.github.com/users/{username}/repos"
    res = requests.get(url).json()

    simplified = [
        {
            "name": repo["name"],
            "url": repo["html_url"]
        }
        for repo in res[:5]
    ]

    return simplified
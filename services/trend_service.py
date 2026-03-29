from fastapi import FastAPI
import requests

trend_app = FastAPI()

@trend_app.get("/trends")
def get_trends():
    url = "https://mastodon.social/api/v1/timelines/public?limit=5"
    res = requests.get(url).json()

    keywords = []
    for post in res:
        content = post.get("content", "")
        words = content.split()
        keywords.extend(words[:3])

    return {"trending_keywords": keywords}
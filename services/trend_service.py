from fastapi import FastAPI
import requests
import re

trend_app = FastAPI()

@trend_app.get("/trends")
def get_trends():
    try:
        url = "https://mastodon.social/api/v1/trends/statuses?limit=10"
        res = requests.get(url, timeout=10).json()

        if not isinstance(res, list):
            return {"error": f"Unexpected response from Mastodon: {res}", "trending_keywords": []}

        keywords = []
        for post in res:
            content = post.get("content", "")
            # Strip HTML tags
            clean = re.sub(r"<[^>]+>", " ", content)
            # Remove non-alphanumeric characters
            clean = re.sub(r"[^a-zA-Z0-9\s]", "", clean)
            words = [w for w in clean.split() if len(w) > 3]
            keywords.extend(words[:3])

        return {"trending_keywords": keywords}
    except Exception as e:
        return {"error": str(e), "trending_keywords": []}
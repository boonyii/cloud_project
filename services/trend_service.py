from fastapi import FastAPI
import requests
import re
import os
import json
from collections import Counter

trend_app = FastAPI()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_VERSION = os.getenv("GEMINI_API_VERSION", "v1beta")

STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "have", "been",
    "they", "will", "what", "about", "just", "your", "more", "when", "also",
    "some", "than", "then", "into", "over", "after", "their", "them", "were",
    "would", "could", "should", "there", "which", "these", "those", "said",
    "like", "time", "very", "much", "only", "make", "even", "such", "most",
    "other", "well", "still", "back", "know", "need", "here", "want", "come",
    "http", "https", "www", "html", "quot", "amp", "span", "class", "href",
}


def extract_keywords(posts: list) -> list[str]:
    word_counts = Counter()
    for post in posts:
        content = post.get("content", "")
        clean = re.sub(r"<[^>]+>", " ", content)
        clean = re.sub(r"[^a-zA-Z0-9\s]", "", clean)
        words = [
            w.lower() for w in clean.split()
            if len(w) > 3 and w.lower() not in STOPWORDS
        ]
        word_counts.update(words)

    return [word for word, _ in word_counts.most_common(20)]


def call_gemini_insight(keywords: list[str]) -> str:
    if not GEMINI_API_KEY or not keywords:
        return ""

    url = (
        f"https://generativelanguage.googleapis.com/"
        f"{GEMINI_API_VERSION}/models/{GEMINI_MODEL}:generateContent"
    )

    prompt = f"""These are the top trending keywords extracted from Mastodon social media posts right now:

{', '.join(keywords[:10])}

Write a single, concise sentence (max 20 words) summarizing what people are talking about today.
Return only the sentence, no extra text."""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4},
    }

    try:
        res = requests.post(
            url,
            headers={"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY},
            json=payload,
            timeout=15,
        )
        res.raise_for_status()
        data = res.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return ""


@trend_app.get("/trends")
def get_trends():
    try:
        url = "https://mastodon.social/api/v1/trends/statuses?limit=20"
        res = requests.get(url, timeout=10).json()

        if not isinstance(res, list):
            return {"error": f"Unexpected response from Mastodon: {res}", "trending_keywords": []}

        keywords = extract_keywords(res)
        insight = call_gemini_insight(keywords)

        result = {"trending_keywords": keywords}
        if insight:
            result["insight"] = insight

        return result

    except Exception as e:
        return {"error": str(e), "trending_keywords": []}

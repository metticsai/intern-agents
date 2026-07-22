"""Shared tools available to all agents in the pipeline."""

import requests
from bs4 import BeautifulSoup
from strands import tool


@tool
def search_business(company_name: str, location: str) -> str:
    """Search DuckDuckGo for a business website and return the top 3 results."""
    query = f"{company_name} {location} official website"
    url = f"https://duckduckgo.com/html/?q={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")
    results = [link.get_text().strip() for link in soup.select(".result__url")[:3]]
    if not results:
        return "No results found."
    return "\n".join(f"{i + 1}. {r}" for i, r in enumerate(results))


@tool
def scrape_website(url: str) -> str:
    """Scrape a website URL and return structured text content: headings, paragraphs, and image URLs."""
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")

    h1s = [t.get_text().strip() for t in soup.find_all("h1")]
    h2s = [t.get_text().strip() for t in soup.find_all("h2")]
    paragraphs = [t.get_text().strip() for t in soup.find_all("p")][:12]
    images = []
    for tag in soup.find_all("img"):
        src = tag.get("src", "")
        if src and not src.endswith(".svg") and ("hero" in src.lower() or "logo" in src.lower()):
            images.append(src)

    lines = [
        f"URL: {url}",
        f"H1 HEADINGS: {h1s}",
        f"H2 HEADINGS: {h2s}",
        f"PAGE CONTENT:\n" + "\n".join(paragraphs),
        f"IMAGE URLS: {images[:5]}",
    ]
    return "\n\n".join(lines)


@tool
def check_character_limit(text: str, field: str, platform: str) -> str:
    """Check whether a piece of ad copy meets the character limit for its field and platform.

    Returns PASS or FAIL with the character count vs limit.
    """
    limits: dict[str, dict[str, int]] = {
        "meta": {"hook": 125, "headline": 40, "body": 500, "cta": 25},
        "tiktok": {"overlay": 34, "caption": 150, "cta": 25},
        "linkedin": {"hook": 150, "body": 1300, "cta": 50},
        "google": {"headline": 30, "description": 90},
    }
    limit = limits.get(platform, {}).get(field)
    if limit is None:
        return f"No limit defined for '{field}' on '{platform}'."
    length = len(text)
    status = "PASS" if length <= limit else "FAIL"
    return f"{status}: {field} on {platform} — {length}/{limit} chars"

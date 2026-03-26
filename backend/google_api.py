"""
Google Search API integration using SerpShot.
Provides an alternative to web scraping for more reliable results.
"""
import os
import re
import html
from typing import List, Dict, Any

try:
    from serpshot import SerpShot
    SERPSHOT_AVAILABLE = True
except ImportError:
    SERPSHOT_AVAILABLE = False
    print("[Warning] SerpShot not installed. Run: pip install serpshot")


SERPSHOT_API_KEY = os.getenv("SERPSHOT_API_KEY", "")


def clean_html_text(text: str) -> str:
    """Clean HTML tags and entities from text."""
    if not text:
        return ""

    # Decode HTML entities like &nbsp;, &amp;, etc.
    text = html.unescape(text)

    # Remove HTML tags like <b>, <strong>, etc.
    text = re.sub(r'<[^>]+>', '', text)

    # Clean up extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def is_api_available() -> bool:
    """Check if Google API is available and configured."""
    return SERPSHOT_AVAILABLE and bool(SERPSHOT_API_KEY)


def search_google(query: str, num_results: int = 10, location: str = "US") -> List[Dict[str, Any]]:
    """
    Search Google using SerpShot API.

    Args:
        query: Search query string
        num_results: Number of results to return
        location: Search location (default: US)

    Returns:
        List of search results with title, link, description (snippet)
    """
    if not is_api_available():
        print("[Google API] SerpShot not available, falling back to scraping")
        return []

    try:
        with SerpShot(api_key=SERPSHOT_API_KEY) as client:
            response = client.search(
                query=query,
                num=num_results,
                page=1,
                location=location
            )

            results = []
            for result in response.results:
                # Clean HTML from title and description
                clean_title = clean_html_text(result.title)
                clean_description = clean_html_text(getattr(result, 'snippet', '') or result.title)

                results.append({
                    "title": clean_title,
                    "url": result.link,
                    "description": clean_description,
                    "source": "google_api"
                })

            return results

    except Exception as e:
        print(f"[Google API Error] {e}")
        return []


def search_youtube_videos(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """Search YouTube videos using Google API."""
    # Try multiple search strategies for better YouTube results
    search_queries = [
        f"{query} site:youtube.com",  # Broader search
        f'"{query}" youtube video',   # Alternative approach
        f"{query} tutorial site:youtube.com"  # Tutorial-focused
    ]

    youtube_results = []
    seen_urls = set()

    for search_query in search_queries:
        if len(youtube_results) >= max_results:
            break

        results = search_google(search_query, num_results=max_results)

        for result in results:
            if len(youtube_results) >= max_results:
                break

            # Check for YouTube URLs (both /watch and other formats)
            if ("youtube.com" in result["url"] and
                result["url"] not in seen_urls):

                seen_urls.add(result["url"])

                try:
                    # Extract video ID for thumbnail
                    video_id = None
                    if "v=" in result["url"]:
                        video_id = result["url"].split("v=")[1].split("&")[0]
                    elif "youtu.be/" in result["url"]:
                        video_id = result["url"].split("youtu.be/")[1].split("?")[0]

                    youtube_results.append({
                        "title": result["title"],
                        "url": result["url"],
                        "description": result["description"],
                        "thumbnail": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg" if video_id else None,
                        "source": "youtube"
                    })
                except Exception as e:
                    # Still add the result even if thumbnail fails
                    youtube_results.append({
                        "title": result["title"],
                        "url": result["url"],
                        "description": result["description"],
                        "thumbnail": None,
                        "source": "youtube"
                    })

    return youtube_results


def search_github_repos(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """Search GitHub repositories using Google API."""
    search_query = f"{query} site:github.com"

    results = search_google(search_query, num_results=max_results)

    # Filter and enhance GitHub results
    github_results = []
    for result in results:
        if "github.com" in result["url"] and "/blob/" not in result["url"]:
            github_results.append({
                "title": clean_html_text(result["title"]),
                "url": result["url"],
                "description": clean_html_text(result["description"]),
                "source": "github",
                "thumbnail": None
            })

    return github_results


def search_reddit_content(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """Search Reddit content using Google API."""
    search_query = f"{query} site:reddit.com"

    results = search_google(search_query, num_results=max_results)

    reddit_results = []
    for result in results:
        if "reddit.com" in result["url"]:
            is_subreddit = "/r/" in result["url"] and "/comments/" not in result["url"]

            reddit_results.append({
                "title": clean_html_text(result["title"]),
                "url": result["url"],
                "description": clean_html_text(result["description"]),
                "source": "reddit",
                "type": "subreddit" if is_subreddit else "post"
            })

    return reddit_results


def search_twitter_content(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """Search Twitter/X content using Google API."""
    search_query = f"{query} site:twitter.com OR site:x.com"

    results = search_google(search_query, num_results=max_results)

    twitter_results = []
    for result in results:
        if "twitter.com" in result["url"] or "x.com" in result["url"]:
            twitter_results.append({
                "title": clean_html_text(result["title"]),
                "url": result["url"].replace("x.com", "twitter.com"),
                "description": clean_html_text(result["description"]),
                "source": "twitter",
                "content_type": "tweet" if "/status/" in result["url"] else "profile"
            })

    return twitter_results


def search_blog_articles(query: str, max_results: int = 15) -> List[Dict[str, Any]]:
    """Search blog articles using Google API."""
    # Search for popular blog platforms
    search_queries = [
        f"{query} site:medium.com",
        f"{query} site:dev.to",
        f"{query} tutorial blog",
    ]

    blog_results = []
    seen_urls = set()

    for search_query in search_queries:
        if len(blog_results) >= max_results:
            break

        results = search_google(search_query, num_results=5)

        for result in results:
            if result["url"] in seen_urls:
                continue

            # Skip non-blog domains
            skip_domains = ["youtube.com", "twitter.com", "x.com", "facebook.com",
                          "instagram.com", "reddit.com", "linkedin.com"]

            if any(domain in result["url"] for domain in skip_domains):
                continue

            seen_urls.add(result["url"])

            # Determine platform
            platform = "blog"
            if "medium.com" in result["url"]:
                platform = "medium"
            elif "dev.to" in result["url"]:
                platform = "dev.to"
            elif "hashnode" in result["url"]:
                platform = "hashnode"

            blog_results.append({
                "title": clean_html_text(result["title"]),
                "url": result["url"],
                "description": clean_html_text(result["description"]),
                "source": "blog",
                "platform": platform
            })

            if len(blog_results) >= max_results:
                break

    return blog_results


def search_linkedin_content(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """Search LinkedIn content using Google API."""
    search_query = f"{query} site:linkedin.com"

    results = search_google(search_query, num_results=max_results)

    linkedin_results = []
    for result in results:
        if "linkedin.com" in result["url"]:
            linkedin_results.append({
                "title": clean_html_text(result["title"]),
                "url": result["url"],
                "description": clean_html_text(result["description"]),
                "source": "linkedin"
            })

    return linkedin_results


def search_quora_content(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """Search Quora content using Google API."""
    search_query = f"{query} site:quora.com"

    results = search_google(search_query, num_results=max_results)

    quora_results = []
    for result in results:
        if "quora.com" in result["url"]:
            quora_results.append({
                "title": clean_html_text(result["title"]),
                "url": result["url"],
                "description": clean_html_text(result["description"]),
                "source": "quora"
            })

    return quora_results


def search_events(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """Search events using Google API."""
    search_query = f"{query} workshop webinar event conference"

    results = search_google(search_query, num_results=max_results)

    event_results = []
    for result in results:
        # Focus on event platforms
        event_domains = ["eventbrite.com", "meetup.com", "lu.ma", "conferences.io"]

        if any(domain in result["url"] for domain in event_domains):
            event_results.append({
                "title": clean_html_text(result["title"]),
                "url": result["url"],
                "description": clean_html_text(result["description"]),
                "source": "events"
            })

    return event_results


def search_all_platforms(topic: str, queries: dict) -> dict:
    """
    Search all platforms using Google API.

    Args:
        topic: The search topic
        queries: Dictionary of platform-specific queries

    Returns:
        Dictionary of results organized by platform
    """
    if not is_api_available():
        return {}

    print("[Google API] Using SerpShot for all searches")

    results = {
        "youtube": search_youtube_videos(queries.get("youtube_query", topic)),
        "github": search_github_repos(queries.get("github_query", topic)),
        "reddit": search_reddit_content(queries.get("reddit_query", topic)),
        "twitter": search_twitter_content(queries.get("twitter_query", topic)),
        "blogs": search_blog_articles(queries.get("blog_query", f"{topic} tutorial")),
        "linkedin": search_linkedin_content(queries.get("linkedin_query", topic)),
        "quora": search_quora_content(queries.get("quora_query", topic)),
        "events": search_events(queries.get("events_query", f"{topic} event")),
        "facebook": [],  # Facebook is difficult via API, keep empty or use scraping
        "instagram": []  # Instagram is difficult via API, keep empty or use scraping
    }

    return results

"""
Twitter/X Scraper using Universal Search Engine approach.
Since Twitter/X is a walled garden, we query search engines to find
expert tweets, threads, and profiles without hitting login walls.
"""
from urllib.parse import urlparse
from .utils import search_google, clean_text


def scrape_twitter(query: str, max_results: int = 15) -> list:
    """
    Scrape Twitter/X content by searching multiple sources.
    Returns expert tweets, viral threads, and influential profiles.
    """
    results = []
    seen_urls = set()

    # Strategy 1: Google search with multiple queries
    google_results = _search_google_twitter(query, max_results, seen_urls)
    results.extend(google_results)

    # Strategy 2: Try finding Twitter content via broader search
    if len(results) < 5:
        broad_results = _search_twitter_broad(query, max_results - len(results), seen_urls)
        results.extend(broad_results)

    return results[:max_results]


def _search_google_twitter(query: str, max_results: int, seen_urls: set) -> list:
    """Search Google specifically for Twitter/X content."""
    results = []

    search_queries = [
        f'"{query}" site:twitter.com',
        f'"{query}" site:x.com',
        f"{query} twitter thread best",
        f"{query} viral tweet",
    ]

    for search_query in search_queries:
        if len(results) >= max_results:
            break

        try:
            # Use Google search
            search_results = search_google(search_query, max_results)

            for result in search_results:
                if len(results) >= max_results:
                    break

                href = result.get("url", "")
                title = result.get("title", "")
                snippet = result.get("description", "")

                if not href or href in seen_urls:
                    continue

                # Check if it's a Twitter/X URL
                parsed = urlparse(href)
                is_twitter = any(d in parsed.netloc.lower() for d in ["twitter.com", "x.com"])

                if not is_twitter:
                    continue

                seen_urls.add(href)

                # Determine content type
                content_type = _determine_content_type(href, title, snippet)

                # Extract username
                username = _extract_username(parsed)

                results.append({
                    "title": clean_text(title) or f"Twitter content about {query}",
                    "url": href.replace("x.com", "twitter.com"),  # Normalize to twitter.com
                    "description": snippet or f"Twitter {content_type} related to {query}",
                    "source": "twitter",
                    "content_type": content_type,
                    "username": username,
                    "thumbnail": None
                })

        except Exception as e:
            print(f"[Twitter Google Error] {e}")
            continue

    return results


def _search_twitter_broad(query: str, max_results: int, seen_urls: set) -> list:
    """Broader search for Twitter content mentioned on other sites."""
    results = []

    search_queries = [
        f"{query} best twitter accounts to follow",
        f"{query} twitter influencers list",
        f"top {query} tweets",
    ]

    for search_query in search_queries:
        if len(results) >= max_results:
            break

        try:
            # Use Google search
            search_results = search_google(search_query, max_results * 2)

            for result in search_results:
                if len(results) >= max_results:
                    break

                href = result.get("url", "")
                title = result.get("title", "")

                if href in seen_urls:
                    continue

                parsed = urlparse(href)
                is_twitter = any(d in parsed.netloc.lower() for d in ["twitter.com", "x.com"])

                if is_twitter:
                    seen_urls.add(href)

                    content_type = _determine_content_type(href, title, "")
                    username = _extract_username(parsed)

                    results.append({
                        "title": clean_text(title)[:100] if title else f"Twitter {content_type}",
                        "url": href.replace("x.com", "twitter.com"),
                        "description": f"Twitter {content_type} about {query}",
                        "source": "twitter",
                        "content_type": content_type,
                        "username": username,
                        "thumbnail": None
                    })

        except Exception as e:
            print(f"[Twitter Broad Search Error] {e}")
            continue

    return results


def _determine_content_type(url: str, title: str, snippet: str) -> str:
    """Determine the type of Twitter content."""
    combined = (title + snippet).lower()

    if "/status/" in url:
        if "thread" in combined:
            return "thread"
        return "tweet"
    elif "/i/lists" in url:
        return "list"
    elif "/search" in url:
        return "search"
    elif "/hashtag/" in url:
        return "hashtag"
    else:
        # Likely a profile
        return "profile"


def _extract_username(parsed_url) -> str:
    """Extract username from Twitter URL."""
    path_parts = [p for p in parsed_url.path.strip("/").split("/") if p]
    if path_parts and path_parts[0] not in ["search", "hashtag", "i", "intent"]:
        return f"@{path_parts[0]}"
    return ""


def scrape_twitter_experts(query: str, max_results: int = 10) -> list:
    """Find Twitter/X experts and influencers on a topic."""
    results = []
    seen_urls = set()

    search_queries = [
        f"{query} expert twitter profile site:twitter.com",
        f"best {query} twitter accounts to follow",
        f"{query} thought leader twitter",
    ]

    for search_query in search_queries:
        if len(results) >= max_results:
            break

        try:
            # Use Google search
            search_results = search_google(search_query, max_results)

            for result in search_results:
                if len(results) >= max_results:
                    break

                href = result.get("url", "")
                title = result.get("title", "")
                snippet = result.get("description", "")

                parsed = urlparse(href)
                is_twitter = any(d in parsed.netloc.lower() for d in ["twitter.com", "x.com"])

                # Look for profile URLs (no /status/ in path)
                if is_twitter and "/status/" not in href and href not in seen_urls:
                    seen_urls.add(href)

                    results.append({
                        "title": clean_text(title),
                        "url": href.replace("x.com", "twitter.com"),
                        "description": snippet or f"Twitter expert on {query}",
                        "source": "twitter",
                        "content_type": "expert_profile",
                        "username": _extract_username(parsed),
                        "thumbnail": None
                    })

        except Exception as e:
            print(f"[Twitter Experts Error] {e}")
            continue

    return results[:max_results]

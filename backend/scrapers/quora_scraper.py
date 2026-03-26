"""
Quora Scraper using Universal Search Engine approach.
Extracts Q&A content, answers from experts, and topic spaces.
"""
from urllib.parse import urlparse
from .utils import search_google, clean_text


def scrape_quora(query: str, max_results: int = 15) -> list:
    """
    Scrape Quora Q&A content using multiple search strategies.
    Returns questions, answers, and topic spaces related to the query.
    """
    results = []
    seen_urls = set()

    # Strategy 1: Google site-specific search
    google_results = _search_quora_google(query, max_results, seen_urls)
    results.extend(google_results)

    # Strategy 2: Broader Google search
    if len(results) < 5:
        broad_results = _search_quora_broad(query, max_results - len(results), seen_urls)
        results.extend(broad_results)

    return results[:max_results]


def _search_quora_google(query: str, max_results: int, seen_urls: set) -> list:
    """Search Google for Quora content."""
    results = []

    search_queries = [
        f'"{query}" site:quora.com',
        f"what is {query} site:quora.com",
        f"how to learn {query} site:quora.com",
        f"{query} best answer quora",
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

                parsed = urlparse(href)
                if "quora.com" not in parsed.netloc.lower():
                    continue

                seen_urls.add(href)

                # Determine content type
                content_type = _determine_quora_type(href)

                # Clean title
                clean_title = title.replace(" - Quora", "").strip()

                results.append({
                    "title": clean_title or f"Quora Q&A about {query}",
                    "url": href,
                    "description": snippet or f"Quora {content_type} related to {query}",
                    "source": "quora",
                    "content_type": content_type,
                    "thumbnail": None
                })

        except Exception as e:
            print(f"[Quora Google Error] {e}")
            continue

    return results


def _search_quora_broad(query: str, max_results: int, seen_urls: set) -> list:
    """Broader search to find Quora links from any source."""
    results = []

    search_queries = [
        f"{query} questions answers quora",
        f"best {query} explanations quora",
        f"{query} guide quora",
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

                if not href or href in seen_urls:
                    continue

                parsed = urlparse(href)
                if "quora.com" not in parsed.netloc.lower():
                    continue

                seen_urls.add(href)

                content_type = _determine_quora_type(href)

                results.append({
                    "title": title.replace(" - Quora", "").strip()[:100] or "Quora Q&A",
                    "url": href,
                    "description": f"Quora {content_type} about {query}",
                    "source": "quora",
                    "content_type": content_type,
                    "thumbnail": None
                })

        except Exception as e:
            print(f"[Quora Broad Error] {e}")
            continue

    return results


def _determine_quora_type(url: str) -> str:
    """Determine the type of Quora content from URL."""
    url_lower = url.lower()

    if "/topic/" in url_lower:
        return "topic"
    elif "/profile/" in url_lower:
        return "profile"
    elif "/space/" in url_lower or "/q/" in url_lower:
        return "space"
    elif "/answer/" in url_lower:
        return "answer"
    else:
        return "question"


def scrape_quora_topics(query: str, max_results: int = 10) -> list:
    """Find Quora topic spaces and communities for a subject."""
    results = []
    seen_urls = set()

    search_queries = [
        f'"{query}" topic site:quora.com',
        f"{query} space site:quora.com",
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
                if "quora.com" not in parsed.netloc.lower():
                    continue

                # Only include topic/space URLs
                if "/topic/" not in href and "/space/" not in href:
                    continue

                if href in seen_urls:
                    continue

                seen_urls.add(href)

                results.append({
                    "title": title.replace(" - Quora", "").strip(),
                    "url": href,
                    "description": snippet or f"Quora topic space for {query}",
                    "source": "quora",
                    "content_type": "topic_space",
                    "thumbnail": None
                })

        except Exception as e:
            print(f"[Quora Topics Error] {e}")
            continue

    return results[:max_results]


def scrape_quora_experts(query: str, max_results: int = 10) -> list:
    """Find Quora experts and top writers on a topic."""
    results = []
    seen_urls = set()

    search_queries = [
        f"{query} expert quora profile",
        f"{query} top writer site:quora.com/profile",
        f"best {query} answers quora",
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
                if "quora.com" not in parsed.netloc.lower():
                    continue

                if href in seen_urls:
                    continue

                seen_urls.add(href)

                # Check if it's a profile or an answer with expert content
                content_type = "expert_answer"
                if "/profile/" in href:
                    content_type = "expert_profile"

                results.append({
                    "title": title.replace(" - Quora", "").strip(),
                    "url": href,
                    "description": snippet or f"Quora expert on {query}",
                    "source": "quora",
                    "content_type": content_type,
                    "thumbnail": None
                })

        except Exception as e:
            print(f"[Quora Experts Error] {e}")
            continue

    return results[:max_results]

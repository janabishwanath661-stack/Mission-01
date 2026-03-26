"""
Universal Search Engine Scraper.
Uses Google search to find content from walled-garden platforms.
"""
from urllib.parse import urlparse
from .utils import search_google, clean_text


def search_google_universal(query: str, max_results: int = 10) -> list:
    """
    Search Google to extract results.
    This is the core of our "Universal Search Engine" approach.
    """
    results = search_google(query, max_results)

    # Add source field if not present
    for result in results:
        if "source" not in result:
            result["source"] = "search"

    return results


def _search_with_multiple_queries(queries: list, domain_filter: str, max_results: int) -> list:
    """Run multiple search queries and filter for a specific domain."""
    results = []
    seen_urls = set()

    for query in queries:
        if len(results) >= max_results:
            break

        try:
            # Use Google search
            search_results = search_google(query, max_results * 2)

            for result in search_results:
                if len(results) >= max_results:
                    break

                href = result.get("url", "")
                title = result.get("title", "")
                snippet = result.get("description", "")

                if not href or href in seen_urls:
                    continue

                # Check if URL matches domain filter
                if domain_filter not in href.lower():
                    continue

                seen_urls.add(href)

                results.append({
                    "title": clean_text(title),
                    "url": href,
                    "description": snippet,
                    "source": "search"
                })

        except Exception as e:
            print(f"[Multi-Query Search Error] {e}")
            continue

    return results


def scrape_linkedin(query: str, max_results: int = 10) -> list:
    """
    Find LinkedIn profiles/groups/companies via search engine.
    """
    search_queries = [
        f'"{query}" site:linkedin.com',
        f"{query} site:linkedin.com/in",
        f"{query} linkedin profile",
        f"{query} linkedin company",
        f"{query} linkedin group",
    ]

    raw_results = _search_with_multiple_queries(search_queries, "linkedin.com", max_results * 2)

    linkedin_results = []
    seen_urls = set()

    for r in raw_results:
        url = r.get("url", "")

        if url in seen_urls:
            continue
        seen_urls.add(url)

        if "linkedin.com" in url.lower():
            # Determine type
            if "/in/" in url:
                r["type"] = "profile"
            elif "/company/" in url:
                r["type"] = "company"
            elif "/groups/" in url:
                r["type"] = "group"
            elif "/pulse/" in url or "/posts/" in url:
                r["type"] = "post"
            else:
                r["type"] = "page"

            r["source"] = "linkedin"
            linkedin_results.append(r)

            if len(linkedin_results) >= max_results:
                break

    return linkedin_results


def scrape_facebook(query: str, max_results: int = 10) -> list:
    """
    Find Facebook groups/pages via search engine.
    """
    search_queries = [
        f'"{query}" site:facebook.com',
        f"{query} facebook group",
        f"{query} facebook community",
        f"{query} site:facebook.com/groups",
        f"best {query} facebook groups",
    ]

    raw_results = _search_with_multiple_queries(search_queries, "facebook.com", max_results * 2)

    facebook_results = []
    seen_urls = set()

    for r in raw_results:
        url = r.get("url", "")

        if url in seen_urls:
            continue
        seen_urls.add(url)

        if "facebook.com" in url.lower():
            if "/groups/" in url:
                r["type"] = "group"
            elif "/events/" in url:
                r["type"] = "event"
            elif "/pages/" in url:
                r["type"] = "page"
            else:
                r["type"] = "page"

            r["source"] = "facebook"
            facebook_results.append(r)

            if len(facebook_results) >= max_results:
                break

    return facebook_results


def scrape_instagram(query: str, max_results: int = 10) -> list:
    """
    Find Instagram accounts/hashtags via search engine.
    """
    search_queries = [
        f'"{query}" site:instagram.com',
        f"{query} instagram account",
        f"{query} instagram profile",
        f"best {query} instagram accounts to follow",
        f"{query} hashtag instagram",
    ]

    raw_results = _search_with_multiple_queries(search_queries, "instagram.com", max_results * 2)

    instagram_results = []
    seen_urls = set()

    for r in raw_results:
        url = r.get("url", "")

        if url in seen_urls:
            continue
        seen_urls.add(url)

        if "instagram.com" in url.lower():
            parsed = urlparse(url)
            path_parts = [p for p in parsed.path.strip("/").split("/") if p]

            if path_parts:
                if path_parts[0] == "explore" and len(path_parts) > 2 and path_parts[1] == "tags":
                    r["type"] = "hashtag"
                    r["handle"] = f"#{path_parts[2]}"
                elif path_parts[0] in ["p", "reel", "reels"]:
                    r["type"] = "post"
                    r["handle"] = ""
                else:
                    r["type"] = "account"
                    r["handle"] = f"@{path_parts[0]}"
            else:
                r["type"] = "account"
                r["handle"] = ""

            r["source"] = "instagram"
            instagram_results.append(r)

            if len(instagram_results) >= max_results:
                break

    return instagram_results


def scrape_blogs(query: str, max_results: int = 10) -> list:
    """
    Find blog articles and tutorials via search engine.
    Excludes major social platforms to get actual blog content.
    """
    search_queries = [
        f"{query} tutorial blog guide",
        f"{query} complete guide",
        f"{query} how to learn",
        f"best {query} resources blog",
    ]

    results = []
    seen_urls = set()

    # Excluded domains
    excluded_domains = [
        "facebook.com", "instagram.com", "linkedin.com",
        "twitter.com", "x.com", "youtube.com", "reddit.com",
        "tiktok.com", "pinterest.com", "quora.com"
    ]

    for query_str in search_queries:
        if len(results) >= max_results:
            break

        try:
            # Use Google search
            search_results = search_google(query_str, max_results * 2)

            for result in search_results:
                if len(results) >= max_results:
                    break

                href = result.get("url", "")
                title = result.get("title", "")
                snippet = result.get("description", "")

                if not href or href in seen_urls:
                    continue

                # Check if it's an excluded domain
                parsed = urlparse(href)
                domain = parsed.netloc.lower()

                if any(excl in domain for excl in excluded_domains):
                    continue

                seen_urls.add(href)

                # Get site name
                domain_parts = domain.replace("www.", "").split(".")
                site_name = domain_parts[0] if domain_parts else "Unknown"

                results.append({
                    "title": clean_text(title),
                    "url": href,
                    "description": snippet or f"Article about {query}",
                    "source": "blog",
                    "site": site_name,
                    "domain": domain
                })

        except Exception as e:
            print(f"[Blog Search Error] {e}")
            continue

    return results

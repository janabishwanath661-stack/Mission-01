"""
Enhanced Blog Article Scraper.
Multi-source approach to find quality blog posts, tutorials, and articles.
"""
from urllib.parse import urlparse
from .utils import search_google, clean_text


def scrape_blog_articles(query: str, max_results: int = 15) -> list:
    """
    Scrape blog articles from multiple sources using search engines.
    Targets Medium, Dev.to, personal blogs, and technical sites.
    """
    results = []

    # Multi-platform search strategies
    search_queries = [
        f"{query} blog tutorial",
        f"{query} site:medium.com",
        f"{query} site:dev.to",
        f"{query} comprehensive guide",
        f"{query} in-depth article",
        f"best {query} tutorial blog",
    ]

    seen_urls = set()

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

                # Filter out non-article URLs
                parsed = urlparse(href)

                # Skip social media, video platforms, and e-commerce
                skip_domains = [
                    "youtube.com", "twitter.com", "x.com", "facebook.com",
                    "instagram.com", "tiktok.com", "amazon.com", "ebay.com",
                    "linkedin.com", "pinterest.com", "reddit.com"
                ]

                if any(domain in parsed.netloc for domain in skip_domains):
                    continue

                seen_urls.add(href)

                # Determine article source/type
                source_type = "blog"
                if "medium.com" in parsed.netloc:
                    source_type = "medium"
                elif "dev.to" in parsed.netloc:
                    source_type = "dev.to"
                elif "hashnode" in parsed.netloc:
                    source_type = "hashnode"
                elif "substack" in parsed.netloc:
                    source_type = "substack"
                elif "towards" in parsed.netloc:
                    source_type = "towardsdatascience"
                elif "freecodecamp" in parsed.netloc:
                    source_type = "freecodecamp"
                elif "hackernoon" in parsed.netloc:
                    source_type = "hackernoon"

                results.append({
                    "title": clean_text(title) or f"Blog article about {query}",
                    "url": href,
                    "description": snippet or f"Article about {query}",
                    "source": "blog",
                    "platform": source_type,
                    "domain": parsed.netloc,
                    "thumbnail": None
                })

        except Exception as e:
            print(f"[Blog Scraper Error] {e}")
            continue

    return results[:max_results]


def scrape_medium_articles(query: str, max_results: int = 10) -> list:
    """
    Specifically scrape Medium articles for a topic.
    """
    results = []

    search_queries = [
        f"{query} site:medium.com",
        f"{query} tutorial site:towardsdatascience.com",
        f"{query} guide site:betterprogramming.pub",
    ]

    seen_urls = set()

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

                # Only include Medium ecosystem
                medium_domains = ["medium.com", "towardsdatascience.com",
                                 "betterprogramming.pub", "levelup.gitconnected.com"]

                if not any(domain in parsed.netloc for domain in medium_domains):
                    continue

                seen_urls.add(href)

                results.append({
                    "title": clean_text(title),
                    "url": href,
                    "description": snippet or f"Medium article about {query}",
                    "source": "blog",
                    "platform": "medium",
                    "domain": parsed.netloc,
                    "thumbnail": None
                })

        except Exception as e:
            print(f"[Medium Scraper Error] {e}")
            continue

    return results[:max_results]


def scrape_dev_articles(query: str, max_results: int = 10) -> list:
    """
    Scrape Dev.to articles using their public API.
    """
    import requests
    from urllib.parse import quote_plus
    from .utils import get_headers, rate_limit

    results = []

    try:
        # Dev.to has a public API
        api_url = f"https://dev.to/api/articles?tag={quote_plus(query.lower().replace(' ', ''))}&per_page={max_results}"

        response = requests.get(api_url, headers=get_headers(), timeout=15)

        if response.status_code == 200:
            articles = response.json()

            for article in articles:
                results.append({
                    "title": article.get("title", ""),
                    "url": article.get("url", ""),
                    "description": article.get("description", "") or article.get("title", ""),
                    "source": "blog",
                    "platform": "dev.to",
                    "domain": "dev.to",
                    "thumbnail": article.get("cover_image") or article.get("social_image"),
                    "author": article.get("user", {}).get("name", ""),
                    "reading_time": article.get("reading_time_minutes", 0),
                    "reactions": article.get("positive_reactions_count", 0)
                })

        rate_limit()

    except Exception as e:
        print(f"[Dev.to API Error] {e}")

    # Fallback to search if API returns few results
    if len(results) < max_results // 2:
        try:
            search_query = f"{query} site:dev.to"
            search_results = search_google(search_query, max_results)

            seen_urls = {r["url"] for r in results}

            for result in search_results:
                if len(results) >= max_results:
                    break

                href = result.get("url", "")
                title = result.get("title", "")
                snippet = result.get("description", "")

                if not href or href in seen_urls or "dev.to" not in href:
                    continue

                seen_urls.add(href)

                results.append({
                    "title": clean_text(title),
                    "url": href,
                    "description": snippet or f"Dev.to article about {query}",
                    "source": "blog",
                    "platform": "dev.to",
                    "domain": "dev.to",
                    "thumbnail": None
                })

        except Exception as e:
            print(f"[Dev.to Search Error] {e}")

    return results[:max_results]


def scrape_technical_blogs(query: str, max_results: int = 10) -> list:
    """
    Find technical blog posts from various high-quality sources.
    """
    results = []

    # Target high-quality tech blog platforms
    search_queries = [
        f"{query} site:freecodecamp.org",
        f"{query} site:hackernoon.com",
        f"{query} site:css-tricks.com",
        f"{query} site:smashingmagazine.com",
        f"{query} site:digitalocean.com/community/tutorials",
    ]

    seen_urls = set()

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

                seen_urls.add(href)

                parsed = urlparse(href)

                results.append({
                    "title": clean_text(title),
                    "url": href,
                    "description": snippet or f"Technical article about {query}",
                    "source": "blog",
                    "platform": parsed.netloc.replace("www.", ""),
                    "domain": parsed.netloc,
                    "thumbnail": None
                })

        except Exception as e:
            print(f"[Technical Blogs Error] {e}")
            continue

    return results[:max_results]

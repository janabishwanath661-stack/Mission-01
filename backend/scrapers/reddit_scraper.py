import requests
from .utils import get_headers, rate_limit, clean_text


def scrape_reddit_communities(query: str, max_results: int = 10) -> list:
    """
    Scrape Reddit for communities (subreddits) and posts using JSON API.
    Reddit allows .json suffix on URLs for raw data.
    """
    results = []

    try:
        # Search for subreddits
        search_url = f"https://www.reddit.com/subreddits/search.json?q={query}&limit={max_results}"
        headers = get_headers()
        headers["Accept"] = "application/json"

        response = requests.get(search_url, headers=headers, timeout=15)

        if response.status_code == 200:
            data = response.json()
            children = data.get("data", {}).get("children", [])

            for child in children:
                sub_data = child.get("data", {})
                name = sub_data.get("display_name", "")
                title = sub_data.get("title", name)
                description = sub_data.get("public_description", "")
                subscribers = sub_data.get("subscribers", 0)

                if name:
                    results.append({
                        "title": f"r/{name}" if not title.startswith("r/") else title,
                        "url": f"https://www.reddit.com/r/{name}/",
                        "description": clean_text(description) or f"Subreddit about {query}",
                        "source": "reddit",
                        "type": "subreddit",
                        "subscribers": subscribers
                    })

        rate_limit()

        # Also search for relevant posts
        posts_url = f"https://www.reddit.com/search.json?q={query}&sort=relevance&limit=5"
        response = requests.get(posts_url, headers=headers, timeout=15)

        if response.status_code == 200:
            data = response.json()
            children = data.get("data", {}).get("children", [])

            for child in children[:5]:
                post_data = child.get("data", {})
                title = post_data.get("title", "")
                subreddit = post_data.get("subreddit", "")
                permalink = post_data.get("permalink", "")
                score = post_data.get("score", 0)

                if title and permalink:
                    results.append({
                        "title": clean_text(title),
                        "url": f"https://www.reddit.com{permalink}",
                        "description": f"Posted in r/{subreddit} • {score} upvotes",
                        "source": "reddit",
                        "type": "post",
                        "subreddit": subreddit,
                        "score": score
                    })

        rate_limit()

    except Exception as e:
        print(f"[Reddit Scraper Error] {e}")

    return results[:max_results]

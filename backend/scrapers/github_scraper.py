import requests
from urllib.parse import quote_plus
from .utils import get_headers, rate_limit, clean_text, search_google


def scrape_github_repos(query: str, max_results: int = 10) -> list:
    """
    Scrape GitHub repositories using the public API.
    No authentication needed for basic search.
    """
    results = []

    try:
        # GitHub Search API
        search_url = f"https://api.github.com/search/repositories?q={quote_plus(query)}&sort=stars&order=desc&per_page={max_results}"

        headers = get_headers()
        headers["Accept"] = "application/vnd.github.v3+json"

        response = requests.get(search_url, headers=headers, timeout=15)

        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])

            for item in items:
                name = item.get("full_name", "")
                description = item.get("description", "")
                url = item.get("html_url", "")
                stars = item.get("stargazers_count", 0)
                language = item.get("language", "")
                forks = item.get("forks_count", 0)

                if name and url:
                    results.append({
                        "title": name,
                        "url": url,
                        "description": clean_text(description) or f"GitHub repository for {query}",
                        "source": "github",
                        "stars": stars,
                        "language": language,
                        "forks": forks,
                        "thumbnail": f"https://opengraph.githubassets.com/1/{name}"
                    })

        rate_limit()

    except Exception as e:
        print(f"[GitHub Scraper Error] {e}")

    # Fallback: use Google search if API fails
    if not results:
        try:
            # Use Google search for GitHub repositories
            search_query = f"{query} site:github.com"
            search_results = search_google(search_query, max_results)

            for result in search_results:
                href = result.get("url", "")
                title = result.get("title", "")
                description = result.get("description", "")

                if href and "github.com" in href:
                    # Extract repo name from URL
                    repo_name = "/".join(href.replace("https://github.com/", "").split("/")[:2])

                    results.append({
                        "title": repo_name or title,
                        "url": href,
                        "description": description or f"GitHub repository related to {query}",
                        "source": "github"
                    })

                    if len(results) >= max_results:
                        break

        except Exception as e:
            print(f"[GitHub Fallback Error] {e}")

    return results[:max_results]

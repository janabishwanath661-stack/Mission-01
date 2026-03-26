"""
YouTube Scraper with multiple fallback strategies.
"""
import requests
import re
import json
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from .utils import get_headers, rate_limit, clean_text, search_google


def scrape_youtube(query: str, max_results: int = 10) -> list:
    """
    Scrape YouTube search results using multiple strategies.
    """
    results = []

    # Strategy 1: Try YouTube direct scraping
    results = _scrape_youtube_direct(query, max_results)

    # Strategy 2: Use Google if direct fails
    if len(results) < 3:
        google_results = _scrape_youtube_via_search(query, max_results)
        # Merge results, avoiding duplicates
        seen_urls = {r["url"] for r in results}
        for r in google_results:
            if r["url"] not in seen_urls:
                results.append(r)
                seen_urls.add(r["url"])

    # Strategy 3: Use Invidious instances as last resort
    if len(results) < 3:
        inv_results = _scrape_invidious(query, max_results)
        seen_urls = {r["url"] for r in results}
        for r in inv_results:
            if r["url"] not in seen_urls:
                results.append(r)

    return results[:max_results]


def _scrape_youtube_direct(query: str, max_results: int = 10) -> list:
    """Try direct YouTube scraping."""
    results = []
    try:
        search_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        headers = get_headers()
        headers["Accept-Language"] = "en-US,en;q=0.9"

        response = requests.get(search_url, headers=headers, timeout=15)

        if response.status_code != 200:
            return results

        html = response.text

        # Try multiple patterns for ytInitialData
        patterns = [
            r'var ytInitialData = ({.*?});',
            r'window\["ytInitialData"\] = ({.*?});',
            r'ytInitialData\s*=\s*({.*?});',
        ]

        data = None
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    break
                except json.JSONDecodeError:
                    continue

        if data:
            # Navigate the nested structure
            try:
                contents = (data.get("contents", {})
                           .get("twoColumnSearchResultsRenderer", {})
                           .get("primaryContents", {})
                           .get("sectionListRenderer", {})
                           .get("contents", []))

                for section in contents:
                    items = section.get("itemSectionRenderer", {}).get("contents", [])
                    for item in items:
                        video = item.get("videoRenderer", {})
                        if video:
                            video_id = video.get("videoId", "")
                            title_runs = video.get("title", {}).get("runs", [])
                            title = title_runs[0].get("text", "") if title_runs else ""

                            owner_runs = video.get("ownerText", {}).get("runs", [])
                            channel = owner_runs[0].get("text", "") if owner_runs else ""

                            # Get view count if available
                            view_text = video.get("viewCountText", {}).get("simpleText", "")

                            if video_id and title:
                                results.append({
                                    "title": clean_text(title),
                                    "url": f"https://www.youtube.com/watch?v={video_id}",
                                    "description": f"Video by {channel}" + (f" • {view_text}" if view_text else ""),
                                    "thumbnail": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                                    "source": "youtube",
                                    "channel": channel
                                })

                            if len(results) >= max_results:
                                break
                    if len(results) >= max_results:
                        break
            except Exception as e:
                print(f"[YouTube Parse Error] {e}")

        rate_limit()

    except Exception as e:
        print(f"[YouTube Direct Error] {e}")

    return results


def _scrape_youtube_via_search(query: str, max_results: int = 10) -> list:
    """Use Google to find YouTube videos."""
    results = []
    try:
        search_query = f"{query} site:youtube.com/watch"

        # Use Google search
        search_results = search_google(search_query, max_results)

        for result in search_results:
            href = result.get("url", "")
            title = result.get("title", "")
            description = result.get("description", "")

            # Extract video ID from URL
            if "youtube.com/watch" in href and "v=" in href:
                try:
                    video_id = href.split("v=")[1].split("&")[0]

                    results.append({
                        "title": clean_text(title),
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "description": description or f"YouTube video about {query}",
                        "thumbnail": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                        "source": "youtube"
                    })

                    if len(results) >= max_results:
                        break
                except:
                    continue

    except Exception as e:
        print(f"[YouTube Google Error] {e}")

    return results


def _scrape_invidious(query: str, max_results: int = 10) -> list:
    """Use Invidious API as fallback."""
    results = []

    # List of public Invidious instances
    instances = [
        "https://vid.puffyan.us",
        "https://invidious.snopyta.org",
        "https://yewtu.be",
        "https://invidious.kavin.rocks",
    ]

    for instance in instances:
        if len(results) >= max_results:
            break
        try:
            api_url = f"{instance}/api/v1/search?q={quote_plus(query)}&type=video"
            response = requests.get(api_url, headers=get_headers(), timeout=10)

            if response.status_code == 200:
                data = response.json()

                for item in data:
                    if item.get("type") == "video":
                        video_id = item.get("videoId", "")
                        title = item.get("title", "")
                        author = item.get("author", "")

                        if video_id and title:
                            results.append({
                                "title": clean_text(title),
                                "url": f"https://www.youtube.com/watch?v={video_id}",
                                "description": f"Video by {author}",
                                "thumbnail": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                                "source": "youtube",
                                "channel": author
                            })

                        if len(results) >= max_results:
                            break

                # If we got results, don't try other instances
                if results:
                    break

            rate_limit()

        except Exception as e:
            print(f"[Invidious {instance} Error] {e}")
            continue

    return results

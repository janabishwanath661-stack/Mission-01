import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from .utils import get_headers, rate_limit, clean_text, search_google


def scrape_eventbrite(query: str, max_results: int = 10) -> list:
    """
    Scrape Eventbrite for workshops and events.
    """
    results = []

    try:
        # Eventbrite search URL
        search_url = f"https://www.eventbrite.com/d/online/{quote_plus(query)}/"
        response = requests.get(search_url, headers=get_headers(), timeout=15)

        if response.status_code != 200:
            return results

        soup = BeautifulSoup(response.text, "lxml")

        # Find event cards
        event_cards = soup.find_all("div", {"data-testid": "event-card"})

        if not event_cards:
            # Alternative selector
            event_cards = soup.find_all("article", class_=lambda x: x and "event" in x.lower() if x else False)

        if not event_cards:
            # Try finding links to events
            event_links = soup.find_all("a", href=lambda x: x and "/e/" in x if x else False)

            seen_urls = set()
            for link in event_links:
                href = link.get("href", "")
                if href and href not in seen_urls:
                    seen_urls.add(href)

                    # Get title from link text or nearby elements
                    title = link.get_text(strip=True)
                    if not title or len(title) < 5:
                        title_elem = link.find("h2") or link.find("h3") or link.find("span")
                        title = title_elem.get_text(strip=True) if title_elem else ""

                    if title and len(title) > 5:
                        full_url = href if href.startswith("http") else f"https://www.eventbrite.com{href}"
                        results.append({
                            "title": clean_text(title),
                            "url": full_url,
                            "description": f"Event/Workshop about {query}",
                            "source": "eventbrite",
                            "type": "event"
                        })

                        if len(results) >= max_results:
                            break
        else:
            for card in event_cards[:max_results]:
                try:
                    title_elem = card.find("h2") or card.find("h3") or card.find(class_=lambda x: x and "title" in x.lower() if x else False)
                    title = clean_text(title_elem.get_text()) if title_elem else ""

                    link_elem = card.find("a", href=True)
                    url = link_elem.get("href", "") if link_elem else ""
                    if url and not url.startswith("http"):
                        url = f"https://www.eventbrite.com{url}"

                    date_elem = card.find(class_=lambda x: x and "date" in x.lower() if x else False)
                    date_text = clean_text(date_elem.get_text()) if date_elem else ""

                    if title and url:
                        results.append({
                            "title": title,
                            "url": url,
                            "description": date_text or f"Event about {query}",
                            "source": "eventbrite",
                            "type": "event"
                        })
                except Exception:
                    continue

        rate_limit()

    except Exception as e:
        print(f"[Eventbrite Scraper Error] {e}")

    # Fallback: search via Google if no results
    if not results:
        search_query = f"{query} workshop webinar eventbrite OR meetup"
        search_results = search_google(search_query, max_results)

        for result in search_results:
            url = result.get("url", "")
            if "eventbrite" in url or "meetup" in url:
                result["source"] = "eventbrite" if "eventbrite" in url else "meetup"
                result["type"] = "event"
                results.append(result)

    return results[:max_results]

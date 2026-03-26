import requests
import time
import random
import os
import urllib.request
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
from DrissionPage import ChromiumPage
import pydub
import speech_recognition as sr

ua = UserAgent()

# Global driver instance for reuse
_driver_instance = None


def get_headers() -> dict:
    """Generate random browser headers to avoid detection."""
    return {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def rate_limit(min_delay: float = 0.5, max_delay: float = 2.0):
    """Add random delay between requests to avoid rate limiting."""
    time.sleep(random.uniform(min_delay, max_delay))


def safe_request(url: str, timeout: int = 10) -> requests.Response | None:
    """Make a safe HTTP request with error handling."""
    try:
        response = requests.get(url, headers=get_headers(), timeout=timeout)
        response.raise_for_status()
        return response
    except requests.RequestException as e:
        print(f"[Request Error] {url}: {e}")
        return None


def clean_text(text: str) -> str:
    """Clean and normalize text content."""
    if not text:
        return ""
    return " ".join(text.split()).strip()


def get_browser_driver():
    """Get or create a persistent browser driver instance."""
    global _driver_instance
    if _driver_instance is None:
        from DrissionPage import ChromiumOptions

        # Configure Chrome for Docker with Xvfb (virtual display)
        # NOT running headless - using Xvfb virtual display instead
        options = ChromiumOptions()

        # Keep headed mode (Xvfb provides the display)
        # options.headless(True)  # DO NOT use headless!

        # Docker-specific arguments
        options.set_argument('--no-sandbox')
        options.set_argument('--disable-dev-shm-usage')
        options.set_argument('--disable-gpu')
        options.set_argument('--disable-software-rasterizer')
        options.set_argument('--window-size=1920,1080')

        # Anti-detection measures
        options.set_argument('--disable-blink-features=AutomationControlled')
        options.set_pref('excludeSwitches', ['enable-automation'])
        options.set_pref('useAutomationExtension', False)

        _driver_instance = ChromiumPage(addr_or_opts=options)
    return _driver_instance


def close_browser_driver():
    """Close the persistent browser driver instance."""
    global _driver_instance
    if _driver_instance is not None:
        try:
            _driver_instance.quit()
        except:
            pass
        _driver_instance = None


def check_and_solve_captcha(driver):
    """Checks if a CAPTCHA is on the page and solves it using audio bypass."""
    if "detected unusual traffic" in driver.html:
        print("CAPTCHA detected! Bypassing...")

        iframe = driver('t:iframe')
        if not iframe:
            print("No CAPTCHA iframe found.")
            return False

        time.sleep(1)

        try:
            checkbox = driver.ele('@class=recaptcha-checkbox-border', timeout=5)
            if checkbox:
                checkbox.click()
                print("Clicked reCAPTCHA checkbox.")
        except Exception as e:
            print(f"Could not click checkbox: {e}")

        time.sleep(3)

        try:
            audio_btn = driver.ele('@id=recaptcha-audio-button', timeout=5)
            if audio_btn:
                audio_btn.click()
                print("Clicked audio challenge button.")
        except Exception as e:
            print(f"Could not click audio button: {e}")

        time.sleep(2)

        try:
            audio_source = driver.ele('@id=audio-source').link
            print(f"Audio link: {audio_source}")

            audio_file = os.path.join(os.getcwd(), 'captcha.mp3')
            wav_file = os.path.join(os.getcwd(), 'captcha.wav')

            urllib.request.urlretrieve(audio_source, audio_file)

            sound = pydub.AudioSegment.from_mp3(audio_file)
            sound.export(wav_file, format="wav")

            r = sr.Recognizer()
            with sr.AudioFile(wav_file) as source:
                audio = r.record(source)
            text = r.recognize_google(audio)

            print(f"Transcribed Text: {text}")

            input_field = driver.ele('@id=audio-response')
            input_field.input(text)

            time.sleep(1)

            verify_btn = driver.ele('@id=recaptcha-verify-button')
            verify_btn.click()
            print("Submitted CAPTCHA!")

            time.sleep(3)

            # Cleanup audio files
            for f_name in [audio_file, wav_file]:
                if os.path.exists(f_name):
                    try:
                        os.remove(f_name)
                    except OSError:
                        pass

            return True
        except Exception as e:
            print(f"Audio bypass failed: {e}")
            # Cleanup on error
            for f_name in ['captcha.mp3', 'captcha.wav']:
                if os.path.exists(f_name):
                    try:
                        os.remove(f_name)
                    except OSError:
                        pass
            return False
    else:
        return False


def search_google(query: str, max_results: int = 10, site_filter: str = None) -> list:
    """
    Search Google using DrissionPage with CAPTCHA handling.

    Args:
        query: Search query string
        max_results: Maximum number of results to return (will fetch in batches of 20)
        site_filter: Optional site filter (e.g., 'twitter.com')

    Returns:
        List of search results with title, url, and description
    """
    driver = get_browser_driver()
    results = []

    # Build search query
    search_query = query
    if site_filter:
        search_query = f"{query} site:{site_filter}"

    print(f"[Google Search] Searching for: {search_query}")

    try:
        # Calculate number of pages needed (20 results per page)
        pages_needed = (max_results + 19) // 20

        for page_num in range(pages_needed):
            start_param = page_num * 20
            url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}&hl=en&num=20&start={start_param}"

            print(f"[Google Search] Fetching page {page_num + 1}...")
            driver.get(url)
            time.sleep(2)

            # Check and solve CAPTCHA if prompted
            captcha_solved = check_and_solve_captcha(driver)
            if captcha_solved:
                print(f"[Google Search] CAPTCHA was solved successfully")

            # Double check in case the first solve failed
            if "detected unusual traffic" in driver.html:
                print("[Google Search] CAPTCHA still present, trying to solve again...")
                time.sleep(2)
                check_and_solve_captcha(driver)

            # Parse page contents
            html = driver.html
            soup = BeautifulSoup(html, 'html.parser')

            page_results_count = 0
            for h3 in soup.select('h3'):
                if len(results) >= max_results:
                    break

                result_container = h3.find_parent('div', class_='g') or h3.find_parent('div')
                link_tag = result_container.select_one('a') if result_container else h3.find_parent('a')

                snippet_tag = None
                if result_container:
                    snippet_tag = result_container.select_one('div.VwiC3b, div.kb0980, .yXOvgc')

                if h3 and link_tag:
                    title = h3.get_text()
                    link = link_tag.get('href')
                    snippet = snippet_tag.get_text() if snippet_tag else "No snippet available"

                    # Filter out valid search result links
                    if link and link.startswith('http'):
                        results.append({
                            'title': clean_text(title),
                            'url': link,
                            'description': clean_text(snippet)
                        })
                        page_results_count += 1

            print(f"[Google Search] Page {page_num + 1}: Found {page_results_count} results (Total: {len(results)})")

            if len(results) >= max_results:
                break

        print(f"[Google Search] Completed: {len(results)} total results for '{search_query}'")

    except Exception as e:
        print(f"[Google Search Error] {e}")

    return results[:max_results]

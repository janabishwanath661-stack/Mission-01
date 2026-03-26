import time
import json
import urllib.request
import os
from bs4 import BeautifulSoup

from DrissionPage import ChromiumPage
import pydub
import speech_recognition as sr

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
            return True
        except Exception as e:
            print(f"Audio bypass failed: {e}")
            return False
    else:
        return False

def scrape_google_recaptcha(query: str, pages: int = 4):
    driver = ChromiumPage()
    
    print(f"Searching for: {query} across {pages} pages...")
    
    all_results = []

    for page_num in range(pages):
        start_param = page_num * 20
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}&hl=en&num=20&start={start_param}"
        print(f"\n--- Scraping Page {page_num + 1} ---")
        driver.get(url)
        time.sleep(2)
        
        # Check and solve CAPTCHA if prompted
        check_and_solve_captcha(driver)
        
        # Double check in case the first solve failed or required a second challenge
        if "detected unusual traffic" in driver.html:
            print("CAPTCHA still present, trying to solve again...")
            time.sleep(2)
            check_and_solve_captcha(driver)

        # Parse page contents
        html = driver.html
        soup = BeautifulSoup(html, 'html.parser')

        page_results = []
        for h3 in soup.select('h3'):
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
                    page_results.append({
                        'title': title,
                        'link': link,
                        'snippet': snippet
                    })
        
        print(f"Found {len(page_results)} results on page {page_num + 1}.")
        all_results.extend(page_results)

    print(f"\nSuccessfully scraped {len(all_results)} total results.")

    # Save aggregated results
    with open('results.json', 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=4, ensure_ascii=False)
    
    print("Data saved to results.json")
    
    # Cleanup dummy audio files
    for f_name in ['captcha.mp3', 'captcha.wav']:
        if os.path.exists(f_name):
            try:
                os.remove(f_name)
            except OSError:
                pass

    driver.quit()

if __name__ == "__main__":
    scrape_google_recaptcha("Rohit Sharma ", pages=4)
